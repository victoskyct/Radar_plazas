"""
Scraper UMU – Universidad de Murcia
=====================================
UMU publica sus convocatorias en la aplicación dinámica ConvocUM
(convocum.um.es), que carga el contenido con JavaScript y NO se puede
scrapear con requests.

Esta implementación hace un intento "best-effort":
  1. Lee la página estática de oposiciones/concursos (um.es/web/pdi/...)
  2. Si encuentra enlaces a convocatorias, los procesa

Si UMU no devuelve resultados de forma fiable, la alternativa es usar
Playwright (navegador automatizado). Ver instrucciones al final.
"""

import re
from datetime import datetime, timezone

from .base import Plaza
from .utils import nueva_sesion, fetch_html, area_en_texto, area_en_pagina_y_pdfs

# Página estática de listado (no la app ConvocUM dinámica)
URL_LISTADO = "https://www.um.es/web/pdi/oposiciones-concursos"

_FECHA = re.compile(r"(\d{2}/\d{2}/\d{4})")


def scrape_umu() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()
    session = nueva_sesion()

    soup = fetch_html(URL_LISTADO, session)
    if not soup:
        print("[UMU] No se pudo acceder a la página de listado")
        return []

    # Buscar enlaces que parezcan convocatorias de plazas
    for a in soup.find_all("a", href=True):
        titulo = a.get_text(" ", strip=True)
        t = titulo.lower()
        if not titulo or len(titulo) < 15:
            continue
        if not any(k in t for k in ["plaza", "convocatoria", "concurso", "profesor"]):
            continue

        enlace = a["href"]
        if not enlace.startswith("http"):
            from urllib.parse import urljoin
            enlace = urljoin(URL_LISTADO, enlace)
        if enlace in vistos:
            continue
        vistos.add(enlace)

        descripcion = None
        if area_en_texto(titulo):
            pass
        else:
            encontrada, descripcion = area_en_pagina_y_pdfs(enlace, session)
            if not encontrada:
                continue

        plazas.append(Plaza(
            universidad="UMU",
            titulo=titulo[:200],
            fecha=datetime.now(tz=timezone.utc),
            enlace=enlace,
            descripcion=descripcion,
            fuente="UMU PDI",
        ))

    if not plazas:
        print("[UMU] Sin resultados. La app ConvocUM es dinámica; "
              "considera usar Playwright (ver docstring de umu.py)")

    return plazas


# ─────────────────────────────────────────────────────────────────────────────
# ALTERNATIVA CON PLAYWRIGHT (si la versión estática no funciona):
#
# 1. Añade a requirements.txt:  playwright
# 2. En el workflow, antes de ejecutar:
#       - run: playwright install --with-deps chromium
# 3. Implementa:
#
#   from playwright.sync_api import sync_playwright
#   def scrape_umu():
#       with sync_playwright() as p:
#           browser = p.chromium.launch()
#           page = browser.new_page()
#           page.goto("https://convocum.um.es/convocum2/paginas/pdi/home.seam")
#           page.wait_for_selector(".tabla-convocatorias")  # ajustar selector
#           filas = page.query_selector_all("tr")
#           ... extraer datos ...
#           browser.close()
# ─────────────────────────────────────────────────────────────────────────────
