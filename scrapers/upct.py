"""
Scraper UPCT – Universidad Politécnica de Cartagena
====================================================
La UPCT publica las convocatorias PDI en HTML estático, separadas en:
  · Personal Funcionario → listado.php?id_cat=1
  · Personal Laboral     → listado.php?id_cat=2

Filtra por áreas de interés configurables en AREAS_INTERES.
Las convocatorias de "diversas áreas" siempre se incluyen porque
pueden contener plazas relevantes que no son visibles en el título.
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .base import Plaza

BASE_URL = "https://www.upct.es/convocatorias/actpdi"
HOME_URL = "https://www.upct.es/recursos_humanos/secciones2.php?id_categoria=20&ambito=1&op=2"

# Áreas que te interesan (se buscan en el título, sin distinción mayúsculas)
AREAS_INTERES = [
    "econom",          # cubre Economía, Economía Aplicada, Economía Agraria, etc.
    "empresa",         # por si acaso
]

<<<<<<< HEAD
# ── Filtro de áreas ───────────────────────────────────────────────────────────
# Añade o quita términos según tus intereses. Se buscan como subcadena
# del título (sin distinguir mayúsculas/minúsculas).
AREAS_INTERES = [
    "econom",       # Economía, Economía Aplicada, Economía Agraria, Econometría…
    "empresa",      # Organización de Empresas, Economía de la Empresa…
    "hacienda",     # Hacienda Pública
    "finanzas",     # Economía Financiera
    "contabilidad", # Contabilidad
    "marketing",
    "comercializ",  # Comercialización e Investigación de Mercados
]

=======
def _area_relevante(titulo: str) -> bool:
    """Devuelve True si el título menciona un área de interés O si es de 'diversas áreas'."""
    titulo_lower = titulo.lower()
    # "diversas áreas" lo dejamos pasar: no sabemos si incluye la tuya
    if "diversas" in titulo_lower:
        return True
    return any(area in titulo_lower for area in AREAS_INTERES)

# Headers de navegador real para evitar bloqueos por User-Agent
>>>>>>> a9245fcc5c87125e0f9f7bffdc151653606d429b
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

_REF = re.compile(r"(RR-\d+/(\d{2}))", re.IGNORECASE)
_TIPO = re.compile(
    r"\b(Catedr[aá]tico|Titular|Permanente\s+Laboral|PPL|Contratado\s+Doctor|"
    r"Ayudante\s+Doctor|AYUDOC|Asociado|Sustituto|Interino)\b",
    re.IGNORECASE,
)
_TIPO_ABREV = {
    "catedrático": "CU", "titular": "TU", "permanente laboral": "PPL",
    "ppl": "PPL", "contratado doctor": "PCD", "ayudante doctor": "AYUDOC",
    "ayudoc": "AYUDOC", "asociado": "ASO", "sustituto": "SUST", "interino": "INT",
}


def _normalizar_tipo(s: str) -> str:
    key = s.lower().strip()
    for patron, abrev in _TIPO_ABREV.items():
        if patron in key:
            return abrev
    return s.upper()


def _año_de_ref(s: str) -> int:
    return 2000 + int(s)


def _area_relevante(titulo: str) -> bool:
    """
    True si el título menciona un área de interés.
    Las convocatorias de 'diversas áreas' siempre pasan: pueden
    incluir economía aunque no lo diga el título.
    """
    t = titulo.lower()
    if "diversas" in t:
        return True
    return any(area in t for area in AREAS_INTERES)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get(HOME_URL, timeout=15)
    except Exception:
        pass
    return session


def scrape_upct() -> list[Plaza]:
    plazas: list[Plaza] = []
    session = _make_session()

    for fuente, url in FUENTES:
        try:
            r = session.get(url, headers={"Referer": HOME_URL}, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[UPCT] Error al obtener {url}: {e}")
            continue

        soup = BeautifulSoup(r.text, "lxml")

        for li in soup.select("li"):
            a = li.find("a", href=lambda h: h and "detalle.php" in h)
            if not a:
                continue

            titulo = a.get_text(strip=True)

            # ── Filtro por área ───────────────────────────────────────────
            if not _area_relevante(titulo):
                continue

            href = a["href"]
            enlace = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

            ref_m = _REF.search(titulo)
            referencia = ref_m.group(1) if ref_m else None
            año = _año_de_ref(ref_m.group(2)) if ref_m else datetime.now().year

            tipo_m = _TIPO.search(titulo)
            tipo = _normalizar_tipo(tipo_m.group(1)) if tipo_m else None

            fecha = datetime(año, 1, 1, tzinfo=timezone.utc)

            # Filtra por área de interés
            if not _area_relevante(titulo):
                continue

            plazas.append(Plaza(
                universidad="UPCT",
                titulo=titulo,
                referencia=referencia,
                tipo=tipo,
                fecha=fecha,
                enlace=enlace,
                fuente=fuente,
            ))

    return plazas
