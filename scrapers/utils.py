"""
utils.py – Utilidades compartidas entre scrapers
=================================================
"""

import io
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Áreas de interés compartidas por TODOS los scrapers
AREAS_INTERES = [
    "econom",        # Economía, Economía Aplicada, Economía Agraria…
    "empresa",       # Organización de Empresas, Economía de la Empresa…
    "hacienda",
    "finanzas",
    "financ",        # Economía Financiera
    "contabilidad",
    "marketing",
    "comercializ",   # Comercialización e Investigación de Mercados
]


def area_en_texto(texto: str) -> bool:
    if not texto:
        return False
    t = texto.lower()
    return any(area in t for area in AREAS_INTERES)


def extraer_snippet_area(texto: str, ventana: int = 100) -> str | None:
    if not texto:
        return None
    t = texto.lower()
    for area in AREAS_INTERES:
        idx = t.find(area)
        if idx >= 0:
            inicio = max(0, idx - 25)
            fin = min(len(texto), idx + ventana)
            snippet = texto[inicio:fin].strip()
            snippet = re.sub(r"\s+", " ", snippet)
            return snippet
    return None


def nueva_sesion() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_html(url: str, session: requests.Session, referer: str | None = None) -> BeautifulSoup | None:
    try:
        headers = {"Referer": referer} if referer else {}
        r = session.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml")
    except Exception as e:
        print(f"[utils] Error al obtener {url}: {e}")
        return None


def fetch_texto_contenido(url: str, session: requests.Session) -> str:
    """Devuelve el texto del cuerpo principal de una página."""
    soup = fetch_html(url, session)
    if not soup:
        return ""
    contenido = (
        soup.select_one(".entry-content")
        or soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one("#contenido")
        or soup.body
    )
    return contenido.get_text(" ", strip=True) if contenido else ""


def fetch_texto_pdf(url: str, session: requests.Session, max_paginas: int = 8) -> str:
    """Descarga un PDF y extrae su texto con pdfplumber."""
    try:
        import pdfplumber
        r = session.get(url, timeout=30)
        r.raise_for_status()
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages[:max_paginas])
    except ImportError:
        print("[utils] pdfplumber no instalado")
    except Exception as e:
        print(f"[utils] Error al leer PDF {url}: {e}")
    return ""


def area_en_pagina_y_pdfs(url: str, session: requests.Session,
                          patron_pdf: str = r"\.pdf") -> tuple[bool, str | None]:
    """
    Comprueba si una página de detalle (o sus PDFs enlazados) menciona
    alguna de las áreas de interés.
    Devuelve (encontrada, snippet).
    """
    soup = fetch_html(url, session)
    if not soup:
        return False, None

    # 1. Buscar en el texto de la propia página
    texto_pagina = soup.get_text(" ", strip=True)
    if area_en_texto(texto_pagina):
        return True, extraer_snippet_area(texto_pagina)

    # 2. Buscar en los PDFs enlazados
    re_pdf = re.compile(patron_pdf, re.IGNORECASE)
    pdfs_revisados = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re_pdf.search(href):
            if not href.startswith("http"):
                # Resolver URL relativa respecto al dominio de la página
                from urllib.parse import urljoin
                href = urljoin(url, href)
            texto_pdf = fetch_texto_pdf(href, session)
            if area_en_texto(texto_pdf):
                return True, extraer_snippet_area(texto_pdf)
            pdfs_revisados += 1
            if pdfs_revisados >= 4:  # límite para no tardar demasiado
                break

    return False, None
