"""
Scraper BOE - Boletin Oficial del Estado
=========================================
Cubre TODAS las universidades publicas espanolas en un solo scraper.
Logica:
  1. Descarga el sumario diario de los ultimos N dias
  2. Filtra la seccion II.B (Oposiciones y concursos) -> UNIVERSIDADES
  3. Para cada anuncio de universidad descarga el texto completo
  4. Filtra por areas de interes (economia agraria, agroalimentaria...)
  5. Extrae: universidad, area, categoria, plazo

API BOE: https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD
Documento: https://www.boe.es/diario_boe/txt.php?id=BOE-A-YYYY-NNNNN
"""

import re
import time
from datetime import datetime, timezone, timedelta

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_texto, extraer_snippet_area

BOE_API   = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
BOE_TXT   = "https://www.boe.es/diario_boe/txt.php?id={id}"
DIAS_ATRAS = 7   # cuantos dias hacia atras revisar

# Keywords que identifican la seccion de universidades en el sumario
_K_UNIVERSIDAD = re.compile(r"universidad", re.IGNORECASE)
_K_PDI = re.compile(
    r"(plaza|plazas|concurso|concursos|acceso|provisi[oó]n|"
    r"profesorado|profesor|docente|investigador)",
    re.IGNORECASE,
)
# Extraer nombre de universidad del titulo del anuncio
_UNIV_RE = re.compile(
    r"de la (Universidad[^,\.]+|Universitat[^,\.]+|Universidad Polit[^,\.]+)",
    re.IGNORECASE,
)
# Extraer categoria (TU, CU, Ayudante Doctor, Asociado...)
_TIPO_RE = re.compile(
    r"\b(Catedr[aá]tico[s]? de Universidad|Titular[es]? de Universidad|"
    r"Ayudante[s]? Doctor[es]?|Contratado[s]? Doctor[es]?|"
    r"Permanente[s]? Laboral|Asociado[s]?|Sustituto[s]?|Interino[s]?)\b",
    re.IGNORECASE,
)
# Extraer plazo de solicitudes
_PLAZO_RE = re.compile(
    r"plazo[^.]*?hasta[^.]*?(\d{1,2}\s+de\s+\w+\s+de\s+\d{4}|"
    r"\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)


def _fechas_a_revisar() -> list[str]:
    """Devuelve los ultimos DIAS_ATRAS dias habiles en formato YYYYMMDD."""
    fechas = []
    d = datetime.now(tz=timezone.utc)
    intentos = 0
    while len(fechas) < DIAS_ATRAS and intentos < 14:
        if d.weekday() < 5:  # lunes-viernes
            fechas.append(d.strftime("%Y%m%d"))
        d -= timedelta(days=1)
        intentos += 1
    return fechas


def _sumario_ids_universidades(fecha: str, session) -> list[dict]:
    """
    Descarga el sumario del BOE y devuelve los items de universidades
    que parecen convocatorias de PDI.
    """
    url = BOE_API.format(fecha=fecha)
    try:
        r = session.get(url, timeout=20, headers={"Accept": "application/json"})
        if r.status_code != 200:
            return []
        data = r.json()
    except Exception as e:
        print(f"[BOE] Error sumario {fecha}: {e}")
        return []

    items = []
    try:
        # Navegar la estructura: data -> sumario -> diario -> seccion -> departamento -> epigrafe -> item
        diario = data.get("data", {}).get("sumario", {}).get("diario", [])
        if isinstance(diario, dict):
            diario = [diario]

        for bloque in diario:
            secciones = bloque.get("seccion", [])
            if isinstance(secciones, dict):
                secciones = [secciones]
            for sec in secciones:
                # Solo seccion 2 (II - Autoridades y Personal, subseccion B oposiciones)
                num_sec = str(sec.get("@num", ""))
                if num_sec not in ("2", "2B"):
                    continue
                deptos = sec.get("departamento", [])
                if isinstance(deptos, dict):
                    deptos = [deptos]
                for depto in deptos:
                    nom_depto = depto.get("@nombre", "")
                    if not _K_UNIVERSIDAD.search(nom_depto):
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
                            if not doc_id or not _K_PDI.search(titulo):
                                continue
                            items.append({
                                "id": doc_id,
                                "titulo": titulo,
                                "fecha": fecha,
                            })
    except Exception as e:
        print(f"[BOE] Error parseando sumario {fecha}: {e}")

    return items


def _procesar_documento(item: dict, session) -> Plaza | None:
    """
    Descarga el texto del anuncio BOE y comprueba si hay areas de interes.
    """
    doc_id = item["id"]
    url_txt = BOE_TXT.format(id=doc_id)
    soup = fetch_html(url_txt, session)
    if not soup:
        return None

    # El texto util esta en el cuerpo del documento BOE
    contenido = (
        soup.select_one(".texto")
        or soup.select_one("#diario_boe_texto")
        or soup.select_one("article")
        or soup.body
    )
    texto = contenido.get_text(" ", strip=True) if contenido else ""

    if not area_en_texto(texto):
        return None

    # Extraer datos
    titulo = item["titulo"]
    univ_m = _UNIV_RE.search(titulo)
    universidad = univ_m.group(1).strip() if univ_m else "Desconocida"
    # Abreviar nombre largo
    universidad = re.sub(r"^Universidad de ", "", universidad)
    universidad = re.sub(r"^Universidad ", "", universidad)

    tipo_m = _TIPO_RE.search(texto)
    tipo = tipo_m.group(1) if tipo_m else None
    if tipo:
        tipo = re.sub(r"\s+", " ", tipo).strip()[:20]

    descripcion = extraer_snippet_area(texto, ventana=140)

    # Plazo
    plazo_m = _PLAZO_RE.search(texto)
    fecha_plazo = plazo_m.group(1) if plazo_m else None

    try:
        anio = int(item["fecha"][:4])
        mes  = int(item["fecha"][4:6])
        dia  = int(item["fecha"][6:8])
        fecha_pub = datetime(anio, mes, dia, tzinfo=timezone.utc)
    except Exception:
        fecha_pub = datetime.now(tz=timezone.utc)

    titulo_completo = titulo
    if fecha_plazo:
        titulo_completo += f" [Plazo: {fecha_plazo}]"

    return Plaza(
        universidad=universidad[:40],
        titulo=titulo_completo[:250],
        referencia=doc_id,
        tipo=tipo,
        fecha=fecha_pub,
        enlace=url_txt,
        descripcion=descripcion,
        fuente="BOE II.B Universidades",
    )


def scrape_boe() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()
    session = nueva_sesion()

    fechas = _fechas_a_revisar()
    print(f"[BOE] Revisando {len(fechas)} dias: {fechas[0]} a {fechas[-1]}")

    for fecha in fechas:
        items = _sumario_ids_universidades(fecha, session)
        print(f"[BOE] {fecha}: {len(items)} anuncios de universidades PDI")
        for item in items:
            doc_id = item["id"]
            if doc_id in vistos:
                continue
            vistos.add(doc_id)
            plaza = _procesar_documento(item, session)
            if plaza:
                plazas.append(plaza)
            time.sleep(0.3)  # ser amables con el servidor

    print(f"[BOE] Total plazas relevantes encontradas: {len(plazas)}")
    return plazas
