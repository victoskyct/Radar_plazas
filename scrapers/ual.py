"""
Scraper UAL – Universidad de Almería
=====================================
TODO: Inspeccionar la web de la UAL y completar este scraper.

Punto de partida probable:
  https://cms.ual.es/UAL/universidad/serviciosgenerales/
        recursoshumanos/pdi/convocatorias/index.htm

La UAL usa un CMS propio (no WordPress), pero las convocatorias
suelen aparecer como un listado de links a PDFs o páginas internas.

Patrón típico:
  - Listado HTML con fecha + título + link al PDF de la resolución
  - En ese caso: requests + BS4 para sacar título, fecha y enlace
  - El PDF puede contener el detalle de las plazas (área, departamento,
    categoría, dedicación…). Si quieres extraer esos datos:
    pip install pdfplumber → lee el PDF y parsea el texto.

Ejemplo con pdfplumber (para cuando el detalle esté en PDF):
    import pdfplumber, io
    import requests

    def extraer_texto_pdf(url: str) -> str:
        r = requests.get(url, timeout=30)
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\\n".join(p.extract_text() or "" for p in pdf.pages)
"""

from datetime import datetime
from .base import Plaza


def scrape_ual() -> list[Plaza]:
    # ⚠️  Pendiente de implementar – ver instrucciones en el docstring
    print("[UAL] Scraper pendiente de implementar")
    return []
