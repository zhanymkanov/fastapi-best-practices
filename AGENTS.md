# FastAPI Best Practices for AI Agents

This document provides guidelines for AI agents working on FastAPI projects. Follow these conventions when writing or modifying code.

## Project Structure

Organize code by domain, not by file type.

```
src/
├── {domain}/           # e.g., auth/, posts/, aws/
│   ├── router.py       # API endpoints
│   ├── schemas.py      # Pydantic models
│   ├── models.py       # Database models
│   ├── service.py      # Business logic
│   ├── dependencies.py # Route dependencies
│   ├── config.py       # Environment variables
│   ├── constants.py    # Constants and error codes
│   ├── exceptions.py   # Domain-specific exceptions
│   └── utils.py        # Helper functions
├── config.py           # Global configuration
├── models.py           # Global models
├── exceptions.py       # Global exceptions
├── database.py         # Database connection
└── main.py             # FastAPI app initialization
```

**Import Convention**: Use explicit module names when importing across domains:
```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
```

## Async Routes

### Rules
- `async def` routes: Use ONLY non-blocking I/O (`await` calls)
- `def` routes (sync): Use for blocking I/O (runs in threadpool automatically)
- CPU-intensive work: Offload to Celery or multiprocessing

### Common Mistakes to Avoid
```python
# WRONG: Blocking call in async route
@router.get("/bad")
async def bad_route():
    time.sleep(10)  # Blocks entire event loop
    return {"status": "done"}

# CORRECT: Non-blocking in async route
@router.get("/good")
async def good_route():
    await asyncio.sleep(10)
    return {"status": "done"}

# CORRECT: Sync route for blocking operations
@router.get("/also-good")
def sync_route():
    time.sleep(10)  # Runs in threadpool
    return {"status": "done"}
```

### Using Sync Libraries in Async Context
```python
from fastapi.concurrency import run_in_threadpool

@router.get("/")
async def call_sync_library():
    result = await run_in_threadpool(sync_client.make_request, data=my_data)
    return result
```

## Pydantic

### Use Built-in Validators
```python
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=128, pattern="^[A-Za-z0-9-_]+$")
    email: EmailStr
    age: int = Field(ge=18)
```

### Custom Base Model
Create a shared base model for consistent serialization:
```python
from pydantic import BaseModel, ConfigDict

class CustomModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: datetime_to_gmt_str},
        populate_by_name=True,
    )
```

### Split BaseSettings by Domain
```python
# src/auth/config.py
class AuthConfig(BaseSettings):
    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP: int = 5

auth_settings = AuthConfig()
```

## Dependencies

### Use for Validation, Not Just DI
```python
async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()
    return post

@router.get("/posts/{post_id}")
async def get_post(post: dict[str, Any] = Depends(valid_post_id)):
    return post
```

### Chain Dependencies
```python
async def valid_owned_post(
    post: dict[str, Any] = Depends(valid_post_id),
    token_data: dict[str, Any] = Depends(parse_jwt_data),
) -> dict[str, Any]:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()
    return post
```

### Key Rules
- Dependencies are cached per request (same dependency called multiple times = one execution)
- Prefer `async` dependencies to avoid threadpool overhead
- Use consistent path variable names to enable dependency reuse

## REST Conventions

Use consistent path variable names for dependency reuse:
```python
# Both use profile_id, enabling shared valid_profile_id dependency
GET /profiles/{profile_id}
GET /creators/{profile_id}
```

## Database

### Naming Conventions
- Use `lower_case_snake` format
- Singular table names: `post`, `user`, `post_like`
- Group related tables with prefix: `payment_account`, `payment_bill`
- DateTime suffix: `_at` (e.g., `created_at`)
- Date suffix: `_date` (e.g., `birth_date`)

### Set Explicit Index Names
```python
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
```

### SQL-First Approach
Prefer database-level operations for:
- Complex joins
- Data aggregation
- Building nested JSON responses

## Migrations (Alembic)

- Keep migrations static and reversible
- Use descriptive file names: `2022-08-24_post_content_idx.py`
- Configure in alembic.ini:
  ```ini
  file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
  ```

## API Documentation

### Hide Docs in Production
```python
SHOW_DOCS_ENVIRONMENT = ("local", "staging")

app_configs = {"title": "My API"}
if ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)
```

### Document Endpoints Properly
```python
@router.post(
    "/endpoints",
    response_model=DefaultResponseModel,
    status_code=status.HTTP_201_CREATED,
    description="Description of the endpoint",
    tags=["Category"],
    responses={
        status.HTTP_201_CREATED: {"model": CreatedResponse},
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    },
)
```

## Testing

Use async test client from the start:
```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_endpoint(client: AsyncClient):
    resp = await client.post("/posts")
    assert resp.status_code == 201
```

## Linting

Use ruff for formatting and linting:
```shell
ruff check --fix src
ruff format src
```

## Quick Reference

| Scenario | Solution |
|----------|----------|
| Non-blocking I/O | `async def` route with `await` |
| Blocking I/O | `def` route (sync) |
| Sync library in async | `run_in_threadpool()` |
| CPU-intensive | Celery/multiprocessing |
| Request validation | Dependencies with DB checks |
| Shared validation | Chain dependencies |
| Config per domain | Separate `BaseSettings` classes |
| Complex DB queries | SQL with JSON aggregation |
