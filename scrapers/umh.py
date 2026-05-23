"""
Scraper UMH – Universidad Miguel Hernández de Elche
====================================================
Fuentes HTML:
  · PDI Contratado  → servicioprofesorado.umh.es/concursos-acceso/pdi-contratado/
  · PDI Funcionario → servicioprofesorado.umh.es/concursos-acceso/funcionarios/
"""

import re
from datetime import datetime, timezone, timedelta

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

# ── Filtro de áreas (igual que UPCT) ─────────────────────────────────────────
AREAS_INTERES = [
    "econom",        # Economía, Economía Aplicada, Economía Agraria…
    "empresa",       # Organización de Empresas, Economía de la Empresa…
    "hacienda",
    "finanzas",
    "contabilidad",
    "marketing",
    "comercializ",
]

# Solo convocatorias nuevas (no actas, listas provisionales, citaciones…)
_ES_CONVOCATORIA = re.compile(
    r"convocatoria.*(plaza|concurso|proceso\s+de\s+selecci[oó]n|provisi[oó]n)",
    re.IGNORECASE,
)
_REF   = re.compile(r"referencia[:\s]+([0-9A-Z]+/[0-9]+)", re.IGNORECASE)
_TIPO  = re.compile(
    r"\b(ASO(?:CCS)?|AYUDOC|AYU|PPL|PCD|TU|CU|PI[FP]|SUSTITUT\w*|ASOCIADO|AYUDANTE\s+DOCTOR)\b",
    re.IGNORECASE,
)
_FECHA = re.compile(r"(\d{2}/\d{2}/\d{4})")

# Solo plazas publicadas en los últimos N días
DIAS_MAX = 180


def _area_relevante(titulo: str) -> bool:
    t = titulo.lower()
    # "proceso de selección urgente" sin área especificada → siempre pasa
    # (el área concreta está en el PDF adjunto, no en el título)
    if "proceso de selecci" in t and "urgente" in t:
        return True
    # "diversas" → puede incluir el área aunque no lo diga
    if "diversas" in t or "varias" in t:
        return True
    return any(area in t for area in AREAS_INTERES)


def scrape_umh() -> list[Plaza]:
    plazas: list[Plaza] = []
    vistos: set[str] = set()          # para deduplicar por URL
    fecha_limite = datetime.now(tz=timezone.utc) - timedelta(days=DIAS_MAX)

    for fuente, url in FUENTES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[UMH] Error al obtener {url}: {e}")
            continue

        soup = BeautifulSoup(r.text, "lxml")

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

            # ── Deduplicar ────────────────────────────────────────────────
            if enlace in vistos:
                continue
            vistos.add(enlace)

            # ── Fecha ─────────────────────────────────────────────────────
            fecha_m = _FECHA.search(texto)
            if fecha_m:
                try:
                    fecha = datetime.strptime(fecha_m.group(1), "%d/%m/%Y").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    fecha = datetime.now(tz=timezone.utc)
            else:
                # Intenta extraer del path de la URL (formato /YYYY/MM/DD/)
                url_fecha = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", enlace)
                if url_fecha:
                    fecha = datetime(
                        int(url_fecha.group(1)),
                        int(url_fecha.group(2)),
                        int(url_fecha.group(3)),
                        tzinfo=timezone.utc,
                    )
                else:
                    fecha = datetime.now(tz=timezone.utc)

            # ── Filtro por antigüedad ─────────────────────────────────────
            if fecha < fecha_limite:
                continue

            # ── Filtro por área ───────────────────────────────────────────
            titulo = _FECHA.sub("", texto).strip().lstrip("-·/ ").strip()
            if not _area_relevante(titulo):
                continue

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
