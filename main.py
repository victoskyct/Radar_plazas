"""
main.py – Orquestador del escáner de plazas PDI
================================================
Flujo:
  1. Scraping de todas las universidades configuradas
  2. Carga del estado anterior (qué plazas ya habíamos visto)
  3. Detección de plazas nuevas
  4. Generación del HTML estático (GitHub Pages)
  5. Envío de email si hay novedades
  6. Guardado del nuevo estado
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from scrapers import Plaza, scrape_umh, scrape_umu, scrape_upct, scrape_ual

# ── Rutas ────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
STATE_FILE = ROOT / "state" / "plazas.json"
OUTPUT_HTML = ROOT / "docs" / "index.html"
TEMPLATES   = ROOT / "templates"

# ── Scrapers activos (comenta los que aún no estén implementados) ─────────────
SCRAPERS = [
    scrape_umh,
    # scrape_umu,    # descomentar cuando esté listo
    scrape_upct,
    # scrape_ual,    # descomentar cuando esté listo
]


# ── Estado ───────────────────────────────────────────────────────────────────

def cargar_ids_vistos() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return set(data.get("ids", []))


def guardar_estado(plazas: list[Plaza]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "ids": [p.uid() for p in plazas],
                "ultima_actualizacion": datetime.now(tz=timezone.utc).isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ── HTML ─────────────────────────────────────────────────────────────────────

def generar_html(plazas: list[Plaza], nuevas: list[Plaza]) -> None:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    tpl = env.get_template("index.html.j2")
    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(
        tpl.render(
            plazas=plazas,
            nuevas_ids={p.uid() for p in nuevas},
            ultima_actualizacion=datetime.now(tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
            universidades=sorted({p.universidad for p in plazas}),
        ),
        encoding="utf-8",
    )
    print(f"[HTML] Generado → {OUTPUT_HTML}")


# ── Email ─────────────────────────────────────────────────────────────────────

def enviar_email(nuevas: list[Plaza]) -> None:
    if not nuevas:
        print("[EMAIL] Sin novedades, no se envía email.")
        return

    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    mail_to   = os.environ.get("MAIL_TO")

    if not all([smtp_user, smtp_pass, mail_to]):
        print("[EMAIL] Variables de entorno SMTP no configuradas, se omite el email.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"[Plazas PDI] {len(nuevas)} nueva{'s' if len(nuevas) > 1 else ''}"
    msg["From"]    = smtp_user
    msg["To"]      = mail_to

    # Cuerpo en texto plano
    lineas = [
        f"Se han detectado {len(nuevas)} nueva(s) convocatoria(s) de plazas PDI:\n",
    ]
    for p in nuevas:
        lineas.append(f"{'─'*60}")
        lineas.append(f"🏫  {p.universidad}")
        lineas.append(f"📋  {p.titulo}")
        if p.tipo:
            lineas.append(f"🔖  Tipo: {p.tipo}")
        if p.referencia:
            lineas.append(f"🔢  Ref: {p.referencia}")
        lineas.append(f"📅  {p.fecha.strftime('%d/%m/%Y')}")
        lineas.append(f"🔗  {p.enlace}")
    lineas.append(f"\n{'─'*60}")
    lineas.append("Este email ha sido generado automáticamente por el escáner PDI.")

    msg.set_content("\n".join(lineas))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        print(f"[EMAIL] Enviado a {mail_to} con {len(nuevas)} plaza(s) nueva(s).")
    except Exception as e:
        print(f"[EMAIL] Error al enviar: {e}", file=sys.stderr)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[INICIO] {datetime.now(tz=timezone.utc).isoformat()}")

    # 1. Scraping
    todas: list[Plaza] = []
    for scraper in SCRAPERS:
        try:
            resultado = scraper()
            print(f"[{scraper.__name__}] {len(resultado)} plaza(s) encontrada(s)")
            todas.extend(resultado)
        except Exception as e:
            print(f"[{scraper.__name__}] ERROR: {e}", file=sys.stderr)

    # Ordenar por fecha descendente
    todas.sort(key=lambda p: p.fecha, reverse=True)

    # 2. Estado anterior
    ids_vistos = cargar_ids_vistos()

    # 3. Novedades
    nuevas = [p for p in todas if p.uid() not in ids_vistos]
    print(f"[RESUMEN] Total: {len(todas)} · Nuevas: {len(nuevas)}")

    # 4. HTML
    generar_html(todas, nuevas)

    # 5. Email
    enviar_email(nuevas)

    # 6. Guardar estado (SOLO si el scraping fue exitoso)
    if todas:
        guardar_estado(todas)
        print("[ESTADO] Guardado correctamente.")
    else:
        print("[ESTADO] No se guarda: ningún scraper devolvió resultados.")

    print("[FIN]")


if __name__ == "__main__":
    main()
