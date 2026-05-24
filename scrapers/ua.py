"""
Scraper UA - Universidad de Alicante
=====================================
Paginas de listado en ssp.ua.es por categoria. Las convocatorias no llevan
el area en el titulo: hay que entrar al detalle y revisar los PDFs adjuntos.
"""

import re
from datetime import datetime, timezone

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_pagina_y_pdfs

BASE = "https://ssp.ua.es"

FUENTES = [
    ("UA Funcionario",  f"{BASE}/es/accesopdi/funcionarios/convocatorias-profesorado-funcionario-concurso-de-acceso-promocion-interna.html"),
    ("UA Permanente",   f"{BASE}/es/accesopdi/profesorado-permamente-laboral/convocatorias-profesorado-permanente-laboral.html"),
    ("UA Contratado",   f"{BASE}/es/accesopdi/contratacion-temporal/convocatorias-profesorado-contratado-laboral-profesor-ayudante-doctor-profesor-asociado.html"),
]

_FECHA_TXT = re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parse_fecha(texto: str) -> datetime:
    m = _FECHA_TXT.search(texto)
    if m:
        dia, mes_txt, anio = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mes = _MESES.get(mes_txt, 1)
        try:
            return datetime(anio, mes, dia, tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def scrape_ua() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()
    session = nueva_sesion()

    for fuente, url in FUENTES:
        soup = fetch_html(url, session)
        if not soup:
            continue

        for a in soup.find_all("a", href=True):
            titulo = a.get_text(" ", strip=True)
            if "resoluci" not in titulo.lower() or "convoca" not in titulo.lower():
                continue

            enlace = a["href"]
            if not enlace.startswith("http"):
                from urllib.parse import urljoin
                enlace = urljoin(url, enlace)

            if enlace in vistos:
                continue
            vistos.add(enlace)

            print(f"[UA] Revisando: {titulo[:60]}...")
            encontrada, snippet = area_en_pagina_y_pdfs(enlace, session)
            if not encontrada:
                continue

            plazas.append(Plaza(
                universidad="UA",
                titulo=titulo,
                fecha=_parse_fecha(titulo),
                enlace=enlace,
                descripcion=snippet,
                fuente=fuente,
            ))

    return plazas
