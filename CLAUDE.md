# FastAPI Best Practices

## Project Structure
Organize by domain (`src/auth/`, `src/posts/`), not file type. Each domain has: `router.py`, `schemas.py`, `models.py`, `service.py`, `dependencies.py`, `config.py`, `exceptions.py`.

## Async Routes
- `async def` → non-blocking I/O only
- `def` (sync) → blocking operations (runs in threadpool)
- CPU-intensive → offload to worker processes (Celery, multiprocessing)
- Sync SDK? Use `run_in_threadpool` from Starlette

## Pydantic
- Use extensively: regex, enums, Field constraints, EmailStr
- Split BaseSettings per domain
- Create custom base model for app-wide serialization
- ValueError in schema → returns ValidationError to client

## Dependencies
- Use for DB/service validations, not just DI
- Chain dependencies to avoid repetition
- Prefer `async` dependencies
- Dependencies are cached per request

## Follow the REST
- Consistent path variable names enable dependency reuse
- `/profiles/{profile_id}` and `/creators/{profile_id}` can share `valid_profile_id` dependency

## Database
- Explicit naming conventions for indexes/constraints
- `lower_case_snake`, singular table names
- SQL-first for joins and aggregations
- Aggregate nested JSON in DB, not Python

## Migrations (Alembic)
- Keep migrations static and reversible
- Use descriptive slugs: `2022-08-24_post_content_idx.py`

## Testing
- Async test client from day 0 (httpx)
