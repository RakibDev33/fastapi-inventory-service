# fastapi-inventory-service

![CI](https://github.com/RakibDev33/fastapi-inventory-service/actions/workflows/ci.yml/badge.svg)

An inventory management API built with **FastAPI**, **SQLAlchemy 2** (typed ORM) and **Pydantic v2**. Products have a stock level that can only change through an append-only **stock movement ledger**, so every unit received, shipped or corrected is auditable.

## Features

- Product catalogue with unique SKUs, prices, reorder levels and a low-stock filter
- Stock movements (`receipt`, `shipment`, `adjustment`) that update stock atomically and record `quantity_after`
- Business rules enforced in a service layer: no negative stock, positive quantities, non-zero adjustments
- **Optimistic locking** with SQLAlchemy's `version_id_col`: concurrent updates to the same product return `409` instead of overwriting each other
- Money stored as integer cents and exposed as exact decimal strings (`"89.90"`), never floats
- Timezone-aware UTC timestamps, even on SQLite
- Typed end to end: `mypy --strict`, Ruff linting and formatting
- Pytest suite with an isolated in-memory database per test, plus a real two-session concurrency test

## Project structure

```
app/
├── main.py       # App factory, lifespan, exception handlers
├── api.py        # HTTP routes (thin): validate, call the service, map to response models
├── services.py   # Business rules and transactions, no HTTP knowledge
├── schemas.py    # Pydantic request/response models and validation
├── models.py     # SQLAlchemy 2 ORM models
└── database.py   # Engine/session setup, request-scoped session dependency, UTC datetime type
tests/            # API tests (TestClient) and service-level concurrency test
```

## API

| Method | Path                                  | Description                                  |
| ------ | ------------------------------------- | -------------------------------------------- |
| POST   | `/products`                           | Create a product                             |
| GET    | `/products?low_stock=&limit=&offset=` | List products                                |
| GET    | `/products/{id}`                      | Get a product                                |
| PATCH  | `/products/{id}`                      | Update name, price or reorder level          |
| POST   | `/products/{id}/stock-movements`      | Record a receipt, shipment or adjustment     |
| GET    | `/products/{id}/stock-movements`      | Movement history (audit trail)               |
| GET    | `/health`                             | Health check                                 |

Interactive documentation is available at `/docs` once the app is running.

```bash
curl -X POST localhost:8000/products -H 'content-type: application/json' \
  -d '{"sku": "KB-01", "name": "Mechanical keyboard", "unit_price": "89.90", "reorder_level": 5}'

curl -X POST localhost:8000/products/1/stock-movements -H 'content-type: application/json' \
  -d '{"type": "receipt", "quantity": 20, "note": "PO-1042"}'
```

Shipping more than is on hand:

```json
{ "detail": "Insufficient stock for KB-01: 20 on hand, 25 requested." }
```

## Getting started

Requires Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

uvicorn app.main:app --reload     # http://localhost:8000/docs
pytest                            # tests
ruff check . && mypy app tests    # lint and type-check
```

Configuration: `DATABASE_URL` (default `sqlite:///./inventory.db`). Any SQLAlchemy URL works, for example `postgresql+psycopg://user:pass@host/inventory` with the driver installed.

### Docker

```bash
docker build -t inventory-service .
docker run -p 8000:8000 inventory-service
```

## Design notes

- **Ledger, not a mutable counter.** `quantity_on_hand` is a cached total; the movements table is the source of truth for how it got there. Each movement stores the signed delta and the resulting quantity.
- **Optimistic concurrency.** Two requests that read the same product version cannot both write: the second `UPDATE ... WHERE version = ?` matches no row, SQLAlchemy raises `StaleDataError`, and the API returns `409`. A database `CHECK (quantity_on_hand >= 0)` constraint backs up the service-level rule.
- **Service layer owns transactions.** Routes stay declarative, and the business rules can be tested without HTTP, as the concurrency test does.
- **Schema management.** Tables are created at startup to keep the sample self-contained. A production deployment would use Alembic migrations.

## License

MIT
