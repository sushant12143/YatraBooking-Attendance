# Fingerprint Attendance Dashboard (Django)

Django backend + dashboard for the NodeMCU ESP8266 / R307S attendance device.
The device API is the same as before, so **the ESP8266 sketch does not change** – only set
`SERVER_URL` (your site) and `DEVICE_KEY` (same value as the server's `DEVICE_KEY`).

Features: KPI cards, donut + trend charts, department absence, tardiness pattern, month calendar,
live check-in feed, leave and manual-adjustment approvals, employee enroll/remove (sent to the device),
CSV / Excel / PDF export, office-hours settings.

> Written without a Django install available, so it was syntax-checked and the analytics/export code
> was unit-tested (`python -m unittest attendance.tests`), but the web pages have not been run.
> If `check`, `migrate` or any page prints an error, send it to me and I will fix it.

## Run locally

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt

# Windows (cmd):   set DJANGO_DEBUG=1 & set DEVICE_KEY=change-me & set ADMIN_USERNAME=admin & set ADMIN_PASSWORD=ChangeMe123
# PowerShell:      $env:DJANGO_DEBUG="1"; $env:DEVICE_KEY="change-me"; $env:ADMIN_USERNAME="admin"; $env:ADMIN_PASSWORD="ChangeMe123"
# Linux/Mac:       export DJANGO_DEBUG=1 DEVICE_KEY=change-me ADMIN_USERNAME=admin ADMIN_PASSWORD=ChangeMe123

python manage.py check
python manage.py migrate
python manage.py ensure_admin
python manage.py seed_demo       # optional: demo employees + 30 days of punches (remove: seed_demo --clear)
python manage.py runserver
```

Open http://127.0.0.1:8000 and sign in. Without `DATABASE_URL` it uses a local SQLite file.

## Deploy on Render (free) with a free external Postgres

Render's free disk is wiped on every restart/deploy and its own free Postgres expires after 30 days,
so use a free Postgres from Neon or Supabase and paste its connection string as `DATABASE_URL`.

1. Push this folder to GitHub, then Render → New → Web Service → pick the repo.
2. Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
3. Start command: `python manage.py migrate && python manage.py ensure_admin && gunicorn config.wsgi --bind 0.0.0.0:$PORT`
4. Environment variables:

| Name | Value |
|------|-------|
| `SECRET_KEY` | long random string |
| `DEVICE_KEY` | secret shared with the ESP8266 sketch |
| `DATABASE_URL` | Neon/Supabase Postgres URL |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | your login (created on first start) |
| `PYTHON_VERSION` | `3.12.3` (recommended) |

`ALLOWED_HOSTS` is filled automatically from Render; add `ALLOWED_HOSTS=your.domain` for a custom domain.
The device polls every 10 s, which also keeps the free service awake while the device is on.

## PythonAnywhere (always on, SQLite)

Upload the folder, create a virtualenv, `pip install -r requirements.txt`, set env vars in the WSGI file
(`DJANGO_DEBUG` unset, `SECRET_KEY`, `DEVICE_KEY`), point WSGI at `config.wsgi`, run `migrate`,
`ensure_admin`, `collectstatic`. Use `https://<you>.pythonanywhere.com` as `SERVER_URL`.

## Device API (unchanged contract)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/device/commands` | `none` \| `enroll|<id>|<name>` \| `delete|<id>|<fingerId>` |
| `POST /api/device/result` | `command_id, ok, finger_id, message` |
| `POST /api/device/punch` | `ts, finger_id, confidence` |

All need header `X-API-Key: <DEVICE_KEY>`.

## Notes
- Late = first punch after office start + grace (Settings). Default week: Sun–Fri working, Saturday off.
- Approved leave and approved manual adjustments are counted in every chart and report.
- PDF export uses a built-in font, so Nepali names show as `?` in PDF only (CSV/Excel are fine).
- Export CSV neutralises cells starting with `= + - @`.
