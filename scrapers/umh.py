"""
Scraper UMH - Universidad Miguel Hernandez de Elche
====================================================
Para convocatorias urgentes/diversas: entra al detalle del post,
extrae el link al PDF del BOUMH, intenta leerlo para filtrar por area.
Si el PDF no es accesible, incluye la plaza con link al PDF para revision manual.
"""

import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_texto, extraer_snippet_area, fetch_texto_pdf

BASE = "https://servicioprofesorado.umh.es"

FUENTES = [
    ("UMH Contratado",  f"{BASE}/concursos-acceso/pdi-contratado/"),
    ("UMH Funcionario", f"{BASE}/concursos-acceso/funcionarios/"),
]

_ES_CONVOCATORIA = re.compile(
    r"convocatoria.*(plaza|concurso|proceso\s+de\s+selecci[oó]n|provisi[oó]n)",
    re.IGNORECASE,
)
_REF   = re.compile(r"referencia[:\s]+([0-9A-Z/]+)", re.IGNORECASE)
_TIPO  = re.compile(
    r"\b(ASO(?:CCS)?|AYUDOC|PPL|PCD|TU|CU|SUSTITUT\w*|ASOCIADO|AYUDANTE\s+DOCTOR)\b",
    re.IGNORECASE,
)
_FECHA = re.compile(r"(\d{2}/\d{2}/\d{4})")
DIAS_MAX = 180

# Regex para detectar titulos que no tienen area en el titulo
_TITULO_GENERICO = re.compile(
    r"proceso\s+de\s+selecci[oó]n\s+urgente|diversas|varias\s+[aá]reas",
    re.IGNORECASE,
)


def _get_boumh_pdf(enlace: str, session) -> str | None:
    """Visita la pagina de detalle del post y devuelve el link al PDF del BOUMH."""
    soup = fetch_html(enlace, session, referer=BASE)
    if not soup:
        return None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt = a.get_text(strip=True).lower()
        # El link suele decir "BOUMH" o "publicacion" y apunta a boumh.umh.es
        if "boumh" in href or "boumh" in txt or "boletin" in txt:
            return href if href.startswith("http") else urljoin(BASE, href)
        # Tambien puede ser un PDF directo en el post
        if href.endswith(".pdf") and "umh.es" in href:
            return href
    return None


def scrape_umh() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()
    fecha_limite = datetime.now(tz=timezone.utc) - timedelta(days=DIAS_MAX)
    session = nueva_sesion()

    for fuente, url in FUENTES:
        soup = fetch_html(url, session)
        if not soup:
            continue

        for li in soup.select("li"):
            a = li.find("a", href=True)
            if not a:
                continue

            texto = a.get_text(" ", strip=True)
            if not _ES_CONVOCATORIA.search(texto):
                continue

            enlace = a["href"]
            if not enlace.startswith("http"):
                enlace = BASE + enlace
            if enlace in vistos:
                continue
            vistos.add(enlace)

            # Fecha
            fecha_m = _FECHA.search(texto)
            if fecha_m:
                try:
                    fecha = datetime.strptime(fecha_m.group(1), "%d/%m/%Y").replace(tzinfo=timezone.utc)
                except ValueError:
                    fecha = datetime.now(tz=timezone.utc)
            else:
                uf = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", enlace)
                fecha = (datetime(int(uf.group(1)), int(uf.group(2)), int(uf.group(3)), tzinfo=timezone.utc)
                         if uf else datetime.now(tz=timezone.utc))

            if fecha < fecha_limite:
                continue

            titulo = _FECHA.sub("", texto).strip().lstrip("-·/ ").strip()
            descripcion = None

            if area_en_texto(titulo):
                # Area ya visible en el titulo → incluir
                pass

            elif _TITULO_GENERICO.search(titulo):
                # Titulo generico: buscar PDF del BOUMH en el detalle
                print(f"[UMH] Buscando PDF BOUMH: {titulo[:50]}...")
                pdf_url = _get_boumh_pdf(enlace, session)

                if pdf_url:
                    # Intentar leer el PDF para filtrar por area
                    texto_pdf = fetch_texto_pdf(pdf_url, session)
                    if texto_pdf:
                        if not area_en_texto(texto_pdf):
                            continue  # PDF accesible pero sin nuestras areas → descartar
                        descripcion = extraer_snippet_area(texto_pdf, ventana=120)
                    else:
                        # PDF bloqueado: incluir con link para revision manual
                        descripcion = f"Ver areas en BOUMH: {pdf_url}"
                else:
                    # Sin PDF encontrado: incluir con nota
                    descripcion = "Ver areas en PDF adjunto (acceder al enlace)"
            else:
                continue  # Sin area y sin patron generico → descartar

            ref_m  = _REF.search(titulo)
            tipo_m = _TIPO.search(titulo)
            plazas.append(Plaza(
                universidad="UMH",
                titulo=titulo,
                referencia=ref_m.group(1) if ref_m else None,
                tipo=tipo_m.group(1).upper() if tipo_m else None,
                fecha=fecha,
                enlace=enlace,
                descripcion=descripcion,
                fuente=fuente,
            ))

    return plazas
