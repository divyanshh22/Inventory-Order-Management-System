# Inventory & Order Management System

A multi-vendor inventory and order management system built with Django, Django REST Framework, PostgreSQL/SQLite, and Celery. It tracks products across vendors, manages the full order lifecycle, generates PDF invoices, audits stock movements, and sends low-stock alerts.

## Features

- **Vendor & product management** — multi-vendor catalog with SKU, pricing, and reorder levels
- **Order lifecycle** — pending → processed → shipped / cancelled, with real-time stock deduction and automatic restock on cancel
- **Atomic inventory control** — order items validate against available stock; stock movements are audited on every change
- **PDF invoices** — auto-generated per order via ReportLab
- **Low-stock alerts** — email notifications triggered by Celery tasks, with in-app resolution workflow
- **Role-based access control** — Admins, Managers, Staff, and Vendors (Django Groups)
- **REST API** — full CRUD, order status transitions, reports, and auth via DRF Token auth
- **Dashboard UI** — responsive HTML/CSS/JS interface consuming the REST API
- **Reporting** — inventory summary, top products, and per-vendor revenue reports
- **Admin panel** — fully configured Django admin for all models

## Tech Stack

- Python / Django 6
- Django REST Framework
- PostgreSQL (SQLite used as a fallback when no DB is configured)
- Celery + Redis (with sync/fallback mode)
- django-celery-beat for scheduled low-stock checks
- ReportLab for PDF invoice generation

## Getting Started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the database (optional)
#    Create a .env file in the project root with your PostgreSQL credentials:
#    DB_ENGINE=django.db.backends.postgresql
#    DB_NAME=inventory
#    DB_USER=postgres
#    DB_PASSWORD=yourpassword
#    DB_HOST=localhost
#    DB_PORT=5432
#    If no .env is present, the app falls back to SQLite.

# 4. Apply migrations
python manage.py migrate

# 5. Create role groups and a superuser
python manage.py seed_roles
python manage.py createsuperuser

# 6. (Optional) Load demo data so the UI is populated
python manage.py seed_demo_data

# 7. (Optional) Create demo accounts so anyone can log in
python manage.py seed_demo_users

# 8. Run the server
python manage.py runserver
```

Open http://127.0.0.1:8000/ — you'll be redirected to the public login page at `/login/`. Visitors can either create their own account (`/register/`) or use the demo accounts:

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `Admin@123` | Superuser / Admins |
| `staff` | `Staff@123` | Staff (read-only) |
| `vendor` | `Vendor@123` | Vendors |

New registrations are added to the `Staff` group (read-only) by default; change this via the `DEFAULT_REGISTRATION_GROUP` env var.

## Celery (optional)

By default `CELERY_TASK_ALWAYS_EAGER=True`, so low-stock tasks run synchronously and no broker is required. To use a real Redis broker, set it to `false` and run:

```bash
celery -A inventory worker -B -l info
```

## API Overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/auth/register/` | POST | Register a user |
| `/api/auth/login/` | POST | Obtain an auth token |
| `/api/vendors/` | GET/POST | List / create vendors |
| `/api/vendors/<id>/` | GET/PUT/DELETE | Vendor detail |
| `/api/products/` | GET/POST | List / create products |
| `/api/orders/` | GET/POST | List / create orders |
| `/api/orders/<id>/process/` `ship/` `cancel/` | POST | Order status transitions |
| `/api/orders/<id>/invoice/` | GET | Download PDF invoice |
| `/api/alerts/` | GET | List low-stock alerts |
| `/api/alerts/<id>/resolve/` | POST | Resolve an alert |
| `/api/stock-movements/` | GET | Audit log of stock changes |
| `/api/reports/summary/` | GET | Inventory KPIs |
| `/api/reports/top-products/` | GET | Best-selling products |
| `/api/reports/vendors/` | GET | Per-vendor revenue |

## Deploy to Render

A `render.yaml` blueprint is included. Deploy via **Render Dashboard → New → Blueprint**, select this repo, and Render will provision the web service plus a managed PostgreSQL database. Key environment variables (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DATABASE_URL`, etc.) are wired up automatically. After the first deploy, run `seed_roles` and `createsuperuser` from the service's Shell tab.

To use an existing PostgreSQL database instead of the managed one, set the `DATABASE_URL` env var (e.g. `postgres://user:pass@host:5432/dbname`) on the service.

## Testing

```bash
python manage.py test
```

The test suite covers the order lifecycle, stock integrity, invoice generation, alerts, and the dashboard UI.
