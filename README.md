# Escáner Plazas PDI

Vigilancia automatizada de convocatorias de plazas PDI en universidades españolas.
Corre cada día via GitHub Actions y publica un visor web en GitHub Pages.

## Universidades cubiertas

| Universidad | Estado | Método |
|-------------|--------|--------|
| UMH – Miguel Hernández | ✅ Funcional | RSS (WordPress) |
| UMU – Murcia | 🔧 Pendiente | Por implementar |
| UPCT – Politécnica de Cartagena | 🔧 Pendiente | Por implementar |
| UAL – Almería | 🔧 Pendiente | Por implementar |

## Puesta en marcha

### 1. Crear el repo en GitHub

Haz fork o sube este código a un repo nuevo (puede ser público o privado).
Si es público, el plan gratuito de GitHub Actions es ilimitado.

### 2. Configurar los secrets de email

En el repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|--------|-------|
| `SMTP_USER` | Tu cuenta de Gmail (p.ej. `tuemail@gmail.com`) |
| `SMTP_PASS` | [App Password de Google](https://myaccount.google.com/apppasswords) (16 caracteres, sin espacios) |
| `MAIL_TO` | Dirección donde quieres recibir los avisos |

> **¿Por qué App Password?** Google no permite usar la contraseña normal
> para SMTP. Ve a tu cuenta → Seguridad → Verificación en 2 pasos (actívala)
> → App passwords → genera una para "Correo / Otra app".

### 3. Activar GitHub Pages

**Settings → Pages → Source: Deploy from a branch**
- Branch: `main`
- Folder: `/docs`

Tu visor web estará en: `https://<tu-usuario>.github.io/<nombre-repo>/`

### 4. Lanzar la primera ejecución

Ve a **Actions → Escáner Plazas PDI → Run workflow**.
La primera vez te llegará un email con todas las plazas encontradas
(porque el estado está vacío). A partir de ahí, solo las nuevas.

## Estructura del proyecto

```
escaner-pdi/
├── scrapers/
│   ├── base.py        # Dataclass Plaza compartida
│   ├── umh.py         # ✅ UMH via RSS
│   ├── umu.py         # 🔧 Stub con instrucciones
│   ├── upct.py        # 🔧 Stub con instrucciones
│   └── ual.py         # 🔧 Stub con instrucciones
├── templates/
│   └── index.html.j2  # Plantilla Jinja2 del visor
├── state/
│   └── plazas.json    # Estado anterior (gestionado por el bot)
├── docs/
│   └── index.html     # HTML generado → servido por GitHub Pages
├── .github/workflows/
│   └── scan.yml       # Cron diario + push automático
├── main.py            # Orquestador
├── requirements.txt
└── .gitignore
```

## Añadir una universidad nueva

1. Copia `scrapers/umu.py` como base.
2. Sigue las instrucciones del docstring para inspeccionar la web.
3. Implementa la función `scrape_xxx() -> list[Plaza]`.
4. Descomenta la línea correspondiente en `main.py`.
5. Haz commit y el próximo día el bot ya la incluirá.

## Cambiar la frecuencia de ejecución

Edita el cron en `.github/workflows/scan.yml`:
```yaml
- cron: '0 7 * * *'    # cada día a las 7:00 UTC
- cron: '0 7 * * 1,4'  # lunes y jueves
- cron: '0 7 * * 1'    # solo los lunes
```

[Generador de cron expressions](https://crontab.guru/)
