# FastAPI Best Practices

## Project Structure
Organize by domain (`src/auth/`, `src/posts/`), not file type. Each domain has: `router.py`, `schemas.py`, `models.py`, `service.py`, `dependencies.py`, `config.py`, `exceptions.py`.

## Async Routes
- `async def` → non-blocking I/O only
- `def` (sync) → blocking operations (runs in threadpool)
- CPU-intensive → offload to worker processes (Celery, multiprocessing)

## Pydantic
- Use extensively: regex, enums, Field constraints, EmailStr
- Split BaseSettings per domain

## Dependencies
- Use for DB/service validations, not just DI
- Chain dependencies to avoid repetition
- Prefer `async` dependencies

## Database
- Explicit naming conventions for indexes/constraints
- `lower_case_snake`, singular table names
- SQL-first for joins and aggregations

## Testing
- Async test client from day 0 (httpx)
