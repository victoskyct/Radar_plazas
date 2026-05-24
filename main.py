"""
main.py - Orquestador del escaner de plazas PDI
================================================
Flujo:
  1. Scraping principal (universidades configuradas: UMH, UPCT, UA, UAL, UMU)
  2. Scraping BOE (todas las universidades espanolas)
  3. Carga del estado anterior
  4. Deteccion de plazas nuevas en ambos grupos
  5. Generacion del HTML estatico (GitHub Pages)
  6. Envio de email con dos secciones si hay novedades
  7. Guardado del nuevo estado
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scrapers import Plaza, scrape_umh, scrape_umu, scrape_upct, scrape_ua, scrape_ual, scrape_boe

ROOT        = Path(__file__).parent
STATE_FILE  = ROOT / "state" / "plazas.json"
OUTPUT_HTML = ROOT / "docs" / "index.html"
TEMPLATES   = ROOT / "templates"

# Scrapers principales (universidades con seguimiento detallado)
SCRAPERS_PRINCIPALES = [
    scrape_umh,
    scrape_upct,
    scrape_ua,
    scrape_ual,
    scrape_umu,
]

# Scrapers secundarios (aparecen al final del email como "Otras plazas")
SCRAPERS_BOE = [
    scrape_boe,
]


# -- Estado -------------------------------------------------------------------

def cargar_ids_vistos() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return set(data.get("ids", []))


def guardar_estado(principales: list[Plaza], boe: list[Plaza]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    todas = principales + boe
    STATE_FILE.write_text(
        json.dumps(
            {
                "ids": [p.uid() for p in todas],
                "ultima_actualizacion": datetime.now(tz=timezone.utc).isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# -- HTML ---------------------------------------------------------------------

def generar_html(principales: list[Plaza], boe: list[Plaza],
                 nuevas_principales: list[Plaza], nuevas_boe: list[Plaza]) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    tpl = env.get_template("index.html.j2")
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    todas = principales + boe
    nuevas_ids = {p.uid() for p in nuevas_principales + nuevas_boe}
    OUTPUT_HTML.write_text(
        tpl.render(
            plazas=todas,
            nuevas_ids=nuevas_ids,
            ultima_actualizacion=datetime.now(tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
            universidades=sorted({p.universidad for p in todas}),
        ),
        encoding="utf-8",
    )
    print(f"[HTML] Generado -> {OUTPUT_HTML}")


# -- Email --------------------------------------------------------------------

def _bloque_plaza(p: Plaza) -> list[str]:
    lineas = [
        f"{'─'*60}",
        f"🏫  {p.universidad}",
        f"📋  {p.titulo}",
    ]
    if p.tipo:
        lineas.append(f"🔖  Tipo: {p.tipo}")
    if p.referencia:
        lineas.append(f"🔢  Ref: {p.referencia}")
    if p.descripcion:
        lineas.append(f"📍  Area: {p.descripcion}")
    lineas.append(f"📅  {p.fecha.strftime('%d/%m/%Y')}")
    lineas.append(f"🔗  {p.enlace}")
    return lineas


def enviar_email(nuevas_principales: list[Plaza], nuevas_boe: list[Plaza],
                 boe_ejecutado: bool = False) -> None:
    if not nuevas_principales and not nuevas_boe and not boe_ejecutado:
        print("[EMAIL] Sin novedades, no se envia email.")
        return

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    mail_to   = os.environ.get("MAIL_TO")

    if not all([smtp_user, smtp_pass, mail_to]):
        print("[EMAIL] Variables de entorno SMTP no configuradas, se omite el email.")
        return

    total = len(nuevas_principales) + len(nuevas_boe)
    msg = EmailMessage()
    msg["Subject"] = f"[Plazas PDI] {total} nueva{'s' if total > 1 else ''}"
    msg["From"]    = smtp_user
    msg["To"]      = mail_to

    lineas = []

    # -- Seccion principal --
    if nuevas_principales:
        lineas.append(f"Se han detectado {len(nuevas_principales)} plaza(s) en universidades monitorizadas:\n")
        for p in nuevas_principales:
            lineas.extend(_bloque_plaza(p))
    else:
        lineas.append("Sin novedades en las universidades monitorizadas.\n")

    # -- Seccion BOE --
    lineas.append(f"\n\n{'═'*60}")
    if nuevas_boe:
        lineas.append(f"📰  OTRAS PLAZAS (BOE) — {len(nuevas_boe)} nueva(s)")
        lineas.append(f"{'═'*60}")
        lineas.append("Plazas en otras universidades espanolas de interes:\n")
        for p in nuevas_boe:
            lineas.extend(_bloque_plaza(p))
    else:
        lineas.append("📰  OTRAS PLAZAS (BOE)")
        lineas.append(f"{'═'*60}")
        lineas.append("No se encontraron plazas nuevas de interes en el BOE en los ultimos 7 dias.")

    lineas.append(f"\n{'─'*60}")
    lineas.append("Este email ha sido generado automaticamente por el escaner PDI.")

    msg.set_content("\n".join(lineas))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        print(f"[EMAIL] Enviado a {mail_to} ({len(nuevas_principales)} principales + {len(nuevas_boe)} BOE).")
    except Exception as e:
        print(f"[EMAIL] Error al enviar: {e}", file=sys.stderr)


# -- Main ---------------------------------------------------------------------

def _ejecutar_scrapers(scrapers: list) -> list[Plaza]:
    todas = []
    for scraper in scrapers:
        try:
            resultado = scraper()
            print(f"[{scraper.__name__}] {len(resultado)} plaza(s)")
            todas.extend(resultado)
        except Exception as e:
            print(f"[{scraper.__name__}] ERROR: {e}", file=sys.stderr)
    return todas


def main() -> None:
    print(f"[INICIO] {datetime.now(tz=timezone.utc).isoformat()}")

    # 1. Scraping
    principales = _ejecutar_scrapers(SCRAPERS_PRINCIPALES)
    principales.sort(key=lambda p: p.fecha, reverse=True)

    boe = _ejecutar_scrapers(SCRAPERS_BOE)
    boe.sort(key=lambda p: p.fecha, reverse=True)

    # 2. Estado anterior
    ids_vistos = cargar_ids_vistos()

    # 3. Novedades
    nuevas_principales = [p for p in principales if p.uid() not in ids_vistos]
    nuevas_boe         = [p for p in boe         if p.uid() not in ids_vistos]

    print(f"[RESUMEN] Principales: {len(principales)} total, {len(nuevas_principales)} nuevas")
    print(f"[RESUMEN] BOE:         {len(boe)} total, {len(nuevas_boe)} nuevas")

    # 4. HTML
    generar_html(principales, boe, nuevas_principales, nuevas_boe)

    # 5. Email
    enviar_email(nuevas_principales, nuevas_boe, boe_ejecutado=len(SCRAPERS_BOE) > 0)

    # 6. Guardar estado
    if principales or boe:
        guardar_estado(principales, boe)
        print("[ESTADO] Guardado correctamente.")
    else:
        print("[ESTADO] No se guarda: ningun scraper devolvio resultados.")

    print("[FIN]")


if __name__ == "__main__":
    main()
