"""
Scraper UPCT – Universidad Politécnica de Cartagena
====================================================
Para "diversas áreas" se descarga el PDF de datos de plazas y se buscan áreas.
"""

import re
from datetime import datetime, timezone

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_texto, area_en_pagina_y_pdfs

BASE_URL = "https://www.upct.es/convocatorias/actpdi"
HOME_URL = "https://www.upct.es/recursos_humanos/secciones2.php?id_categoria=20&ambito=1&op=2"

FUENTES = [
    ("UPCT Funcionario", f"{BASE_URL}/listado.php?id_cat=1"),
    ("UPCT Laboral",     f"{BASE_URL}/listado.php?id_cat=2"),
]

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


def scrape_upct() -> list[Plaza]:
    plazas: list[Plaza] = []
    session = nueva_sesion()
    fetch_html(HOME_URL, session)  # cookies

    for fuente, url in FUENTES:
        soup = fetch_html(url, session, referer=HOME_URL)
        if not soup:
            continue

        for li in soup.select("li"):
            a = li.find("a", href=lambda h: h and "detalle.php" in h)
            if not a:
                continue

            titulo = a.get_text(strip=True)
            href = a["href"]
            enlace = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"

            ref_m = _REF.search(titulo)
            referencia = ref_m.group(1) if ref_m else None
            año = 2000 + int(ref_m.group(2)) if ref_m else datetime.now().year
            tipo_m = _TIPO.search(titulo)
            tipo = _normalizar_tipo(tipo_m.group(1)) if tipo_m else None
            fecha = datetime(año, 1, 1, tzinfo=timezone.utc)
            descripcion = None

            if area_en_texto(titulo):
                pass
            elif "diversas" in titulo.lower():
                print(f"[UPCT] Revisando PDF: {titulo[:55]}…")
                encontrada, descripcion = area_en_pagina_y_pdfs(enlace, session)
                if not encontrada:
                    continue
            else:
                continue

            plazas.append(Plaza(
                universidad="UPCT",
                titulo=titulo,
                referencia=referencia,
                tipo=tipo,
                fecha=fecha,
                enlace=enlace,
                descripcion=descripcion,
                fuente=fuente,
            ))

    return plazas
