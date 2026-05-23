"""
Scraper UMU – Universidad de Murcia
=====================================
TODO: Inspeccionar la web de UMU y completar este scraper.

Punto de partida probable:
  https://www.um.es/web/pdi/convocatorias

Pasos sugeridos para completar:
  1. Abre la URL en el navegador y mira si hay listado de convocatorias
     con links directos a cada plaza.
  2. Usa las DevTools (F12 → Network) para ver si la página carga datos
     via XHR/fetch (API interna) o si el HTML ya contiene el listado.
  3. Si es HTML estático → usar requests + BeautifulSoup (ver patrón abajo).
  4. Si carga con JavaScript → usar playwright (ver nota al final).
  5. Ajusta _ES_CONVOCATORIA y _TIPO según los títulos reales que aparezcan.

Ejemplo con BeautifulSoup (ajusta los selectores CSS a la web real):

    import requests
    from bs4 import BeautifulSoup

    URL = "https://www.um.es/web/pdi/convocatorias"

    def scrape_umu() -> list[Plaza]:
        r = requests.get(URL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        plazas = []
        for item in soup.select("ul.convocatorias li"):   # ← selector real a buscar
            titulo = item.select_one("a").get_text(strip=True)
            enlace = item.select_one("a")["href"]
            fecha_str = item.select_one(".fecha").get_text(strip=True)
            fecha = datetime.strptime(fecha_str, "%d/%m/%Y")
            plazas.append(Plaza(
                universidad="UMU",
                titulo=titulo,
                fecha=fecha,
                enlace=enlace,
                fuente="UMU PDI",
            ))
        return plazas

Nota sobre Playwright (solo si la web usa JavaScript para renderizar):
  - Instalar: pip install playwright && playwright install chromium
  - Añadir a requirements.txt: playwright
  - En el workflow de GitHub Actions añadir el paso:
      - run: playwright install --with-deps chromium
"""

from datetime import datetime
from .base import Plaza


def scrape_umu() -> list[Plaza]:
    # ⚠️  Pendiente de implementar – ver instrucciones en el docstring
    print("[UMU] Scraper pendiente de implementar")
    return []
