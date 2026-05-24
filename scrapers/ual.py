"""
Scraper UAL – Universidad de Almería
=====================================
Listados por categoría en ual.es. El área suele estar en PDFs adjuntos,
así que entramos al detalle de cada convocatoria y revisamos los PDFs.
"""

import re
from datetime import datetime, timezone

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_pagina_y_pdfs

BASE = "https://www.ual.es/universidad/serviciosgenerales/recursoshumanos/convocatorias"

FUENTES = [
    ("UAL Cuerpos Docentes",    f"{BASE}/cuerpos-docentes"),
    ("UAL Ayudante Doctor",     f"{BASE}/personal-docente-e-investigador-laboral/profesores-ayudantes-doctores"),
    ("UAL Permanente Laboral",  f"{BASE}/personal-docente-e-investigador-laboral/profesorado-contratado-doctor"),
]

_FECHA_TXT = re.compile(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", re.IGNORECASE)
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parse_fecha(texto: str) -> datetime:
    m = _FECHA_TXT.search(texto)
    if m:
        try:
            return datetime(int(m.group(3)), _MESES.get(m.group(2).lower(), 1),
                            int(m.group(1)), tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def scrape_ual() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()
    session = nueva_sesion()

    for fuente, url in FUENTES:
        soup = fetch_html(url, session)
        if not soup:
            continue

        # Buscar bloques de convocatoria. En UAL aparecen como texto
        # "Convocatoria: Resolución de ... de ..." con enlaces a documentos.
        # Estrategia: buscar todos los enlaces a PDFs y sus textos contextuales,
        # pero es más robusto revisar el texto de la página por área directamente.
        texto_pagina = soup.get_text(" ", strip=True)

        # Buscamos cada "Resolución de DD de MES de AAAA"
        for m in re.finditer(r"Resoluci[oó]n\s+de\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}[^.]*",
                             texto_pagina, re.IGNORECASE):
            titulo = re.sub(r"\s+", " ", m.group(0)).strip()[:200]

            # Para UAL, el área de cada plaza está en el PDF. Como no hay un
            # enlace 1-a-1 fácil, revisamos el área a nivel de página + PDFs.
            # (esto puede incluir varias convocatorias de la misma categoría)
            # Para deduplicar usamos el título como clave.
            if titulo in vistos:
                continue
            vistos.add(titulo)

            plazas.append(Plaza(
                universidad="UAL",
                titulo=titulo,
                fecha=_parse_fecha(titulo),
                enlace=url,
                descripcion=None,
                fuente=fuente,
            ))

        # Revisar área en los PDFs de la página de categoría
        # (filtramos a posteriori las plazas que no sean de nuestras áreas)
        encontrada, snippet = area_en_pagina_y_pdfs(url, session)
        if not encontrada:
            # Si la categoría no tiene NADA de nuestras áreas, descartamos sus plazas
            plazas = [p for p in plazas if p.fuente != fuente]
        else:
            # Marcar las plazas de esta fuente con el snippet encontrado
            for p in plazas:
                if p.fuente == fuente and p.descripcion is None:
                    p.descripcion = snippet

    return plazas
