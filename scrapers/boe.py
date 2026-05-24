"""
Scraper BOE - Boletin Oficial del Estado
=========================================
Cubre TODAS las universidades publicas espanolas en un solo scraper.
Logica:
  1. Descarga el sumario JSON de los ultimos 7 dias habiles
     API: https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD
  2. Filtra seccion II.B (Oposiciones y concursos) -> UNIVERSIDADES
  3. Para cada anuncio descarga el texto completo
  4. Filtra por areas de interes (economia agraria, agroalimentaria...)
"""

import re
import time
from datetime import datetime, timezone, timedelta

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_texto, extraer_snippet_area

BOE_API   = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
BOE_TXT   = "https://www.boe.es/diario_boe/txt.php?id={id}"
DIAS_ATRAS = 7

_K_UNIVERSIDAD = re.compile(r"universidad", re.IGNORECASE)
_K_PDI = re.compile(
    r"(plaza|plazas|concurso|acceso|provisi[oó]n|"
    r"profesorado|profesor|docente|investigador)",
    re.IGNORECASE,
)
_UNIV_RE = re.compile(
    r"de la (Universidad[^,\.]{3,50}|Universitat[^,\.]{3,50})",
    re.IGNORECASE,
)
_TIPO_RE = re.compile(
    r"\b(Catedr[aá]tico[s]? de Universidad|Titular[es]? de Universidad|"
    r"Ayudante[s]? Doctor[es]?|Contratado[s]? Doctor[es]?|"
    r"Permanente[s]? Laboral|Asociado[s]?|Sustituto[s]?)\b",
    re.IGNORECASE,
)
_PLAZO_RE = re.compile(
    r"plazo[^.]{0,60}?hasta[^.]*?(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|"
    r"\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def _fechas_habiles() -> list[str]:
    fechas, d, intentos = [], datetime.now(tz=timezone.utc), 0
    while len(fechas) < DIAS_ATRAS and intentos < 15:
        if d.weekday() < 5:
            fechas.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
        intentos += 1
    return fechas


def _get_sumario_json(fecha: str, session) -> dict:
    """Descarga el sumario del BOE en formato JSON."""
    url = BOE_API.format(fecha=fecha)
    try:
        r = session.get(url, timeout=20, headers={"Accept": "application/json"})
        if r.status_code == 200:
            return r.json()
        print(f"[BOE] Sumario {fecha}: HTTP {r.status_code}")
    except Exception as e:
        print(f"[BOE] Error sumario {fecha}: {e}")
    return {}


def _extraer_items(data: dict) -> list[dict]:
    """Navega la estructura JSON del BOE y devuelve items de universidades PDI."""
    items = []
    try:
        diario = data.get("data", {}).get("sumario", {}).get("diario", [])
        if isinstance(diario, dict):
            diario = [diario]

        for bloque in diario:
            secciones = bloque.get("seccion", [])
            if isinstance(secciones, dict):
                secciones = [secciones]

            for sec in secciones:
                # Seccion 2 = II (Autoridades y Personal)
                num = str(sec.get("@num", ""))
                if num not in ("2", "2B", "IIB", "II"):
                    continue

                deptos = sec.get("departamento", [])
                if isinstance(deptos, dict):
                    deptos = [deptos]

                for depto in deptos:
                    nombre_depto = depto.get("@nombre", "")
                    if not _K_UNIVERSIDAD.search(nombre_depto):
                        continue

                    epigrafes = depto.get("epigrafe", [])
                    if isinstance(epigrafes, dict):
                        epigrafes = [epigrafes]

                    for epi in epigrafes:
                        its = epi.get("item", [])
                        if isinstance(its, dict):
                            its = [its]

                        for it in its:
                            titulo = it.get("titulo", "")
                            doc_id = it.get("@id", "")
                            if doc_id and _K_PDI.search(titulo):
                                items.append({
                                    "id": doc_id,
                                    "titulo": titulo,
                                })
    except Exception as e:
        print(f"[BOE] Error parseando JSON: {e}")

    return items


def _procesar_doc(item: dict, fecha: str, session) -> "Plaza | None":
    doc_id = item["id"]
    soup = fetch_html(BOE_TXT.format(id=doc_id), session)
    if not soup:
        return None

    contenido = (
        soup.select_one(".texto")
        or soup.select_one("#diario_boe_texto")
        or soup.select_one("article")
        or soup.body
    )
    texto = contenido.get_text(" ", strip=True) if contenido else ""

    if not area_en_texto(texto):
        return None

    titulo  = item["titulo"]
    univ_m  = _UNIV_RE.search(titulo)
    univ    = univ_m.group(1).strip() if univ_m else "Universidad"
    univ    = re.sub(r"^Universidad(?:d)? de ", "", univ).strip()

    tipo_m  = _TIPO_RE.search(texto)
    tipo    = re.sub(r"\s+", " ", tipo_m.group(1)).strip()[:25] if tipo_m else None

    plazo_m = _PLAZO_RE.search(texto)
    plazo   = plazo_m.group(1) if plazo_m else None

    titulo_email = titulo
    if plazo:
        titulo_email += f" [Plazo: {plazo}]"

    try:
        anio, mes, dia = int(fecha[:4]), int(fecha[4:6]), int(fecha[6:8])
        fecha_pub = datetime(anio, mes, dia, tzinfo=timezone.utc)
    except Exception:
        fecha_pub = datetime.now(tz=timezone.utc)

    return Plaza(
        universidad=univ[:40],
        titulo=titulo_email[:250],
        referencia=doc_id,
        tipo=tipo,
        fecha=fecha_pub,
        enlace=BOE_TXT.format(id=doc_id),
        descripcion=extraer_snippet_area(texto, ventana=140),
        fuente="BOE II.B Universidades",
    )


def scrape_boe() -> list[Plaza]:
    plazas:  list[Plaza] = []
    vistos:  set[str]    = set()
    session = nueva_sesion()
    fechas  = _fechas_habiles()

    print(f"[BOE] Revisando {len(fechas)} dias: {fechas[-1]} → {fechas[0]}")

    total_anuncios = 0
    for fecha in fechas:
        data  = _get_sumario_json(fecha, session)
        items = _extraer_items(data)
        total_anuncios += len(items)

        for item in items:
            doc_id = item["id"]
            if doc_id in vistos:
                continue
            vistos.add(doc_id)

            plaza = _procesar_doc(item, fecha, session)
            if plaza:
                plazas.append(plaza)
            time.sleep(0.3)

    print(f"[BOE] {total_anuncios} anuncios de universidades revisados, "
          f"{len(plazas)} con areas de interes")
    return plazas
