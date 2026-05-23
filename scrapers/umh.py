"""
Scraper UMH – Universidad Miguel Hernández de Elche
====================================================
La UMH tiene dos páginas HTML con listados de convocatorias PDI:
  · PDI Contratado  → servicioprofesorado.umh.es/concursos-acceso/pdi-contratado/
  · PDI Funcionario → servicioprofesorado.umh.es/concursos-acceso/funcionarios/

Cada página lista entradas con formato: "DD/MM/YYYY Título, referencia XXXXX/YYYY"
Cada entrada enlaza a una página de detalle individual.
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .base import Plaza

BASE = "https://servicioprofesorado.umh.es"

FUENTES = [
    ("UMH Contratado",  f"{BASE}/concursos-acceso/pdi-contratado/"),
    ("UMH Funcionario", f"{BASE}/concursos-acceso/funcionarios/"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

# Solo convocatorias nuevas, no actas ni listas
_ES_CONVOCATORIA = re.compile(
    r"convocatoria.*(plaza|concurso|proceso\s+de\s+selecci[oó]n|provisi[oó]n)",
    re.IGNORECASE,
)
_REF     = re.compile(r"referencia[:\s]+([0-9]+/[0-9]+)", re.IGNORECASE)
_TIPO    = re.compile(
    r"\b(ASO(?:CCS)?|AYUDOC|AYU|PPL|PCD|TU|CU|PI[FP]|SUSTITUT\w*|ASOCIADO|AYUDANTE\s+DOCTOR)\b",
    re.IGNORECASE,
)
_FECHA   = re.compile(r"(\d{2}/\d{2}/\d{4})")


def scrape_umh() -> list[Plaza]:
    plazas: list[Plaza] = []

    for fuente, url in FUENTES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[UMH] Error al obtener {url}: {e}")
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # Las entradas son <li> con un <a> que contiene fecha + título
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

            # Extraer fecha del texto (formato DD/MM/YYYY)
            fecha_m = _FECHA.search(texto)
            if fecha_m:
                try:
                    fecha = datetime.strptime(fecha_m.group(1), "%d/%m/%Y").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    fecha = datetime.now(tz=timezone.utc)
            else:
                fecha = datetime.now(tz=timezone.utc)

            # Limpiar título (quitar la fecha del principio si la hay)
            titulo = _FECHA.sub("", texto).strip().lstrip("-·/ ").strip()

            ref_m  = _REF.search(titulo)
            tipo_m = _TIPO.search(titulo)

            plazas.append(Plaza(
                universidad="UMH",
                titulo=titulo,
                referencia=ref_m.group(1) if ref_m else None,
                tipo=tipo_m.group(1).upper() if tipo_m else None,
                fecha=fecha,
                enlace=enlace,
                fuente=fuente,
            ))

    return plazas
