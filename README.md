## WIP: FastAPI Best Practices

### 1. Project Structure. Group files by module domain, not file types.
I didn't like the project structure presented by @tiangolo, 
where we separate files by their type (e.g. api, crud, models, schemas).
Structure that I find more scalable and evolvable is inspired by Netflix's [Dispatch](https://github.com/Netflix/dispatch) with some little modifications.
```
fastapi-project
├── alembic/
├── src
│   ├── auth
│   │   ├── router.py
│   │   ├── schemas.py  # pydantic models
│   │   ├── models.py  # db models
│   │   ├── dependencies.py
│   │   ├── config.py  # local configs
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── aws
│   │   ├── client.py  # client model for external service communication
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   └── posts
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── dependencies.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── config.py  # global configs
│   ├── models.py  # global models
│   ├── exceptions.py  # global exceptions
│   ├── pagination.py  # global module e.g. pagination
│   ├── database.py  # db connection related stuff
│   └── main.py
├── tests/
│   ├── auth
│   ├── aws
│   └── posts
├── templates/
│   └── index.html
├── requirements
│   ├── base.txt
│   ├── dev.txt
│   └── prod.txt
├── .env
├── .gitignore
├── logging.ini
└── alembic.ini
```
1. Store all the module directories inside src folder
   1. `src/` - highest level of an app, contains common models, configs, and constants, etc.
   2. `src/main.py` - root of the project, which inits the FastAPI app
2. Each module has its own router, schemas, models, etc.
   1. `router.py` - is a core of each module with all the endpoints
   2. `schemas.py` - for pydantic models
   3. `models.py` - for db models
   4. `service.py` - module specific business logic  
   5. `dependencies.py` - router dependencies
   6. `constants.py` - module specific constants and error codes
   7. `config.py` - e.g. env vars
   8. `utils.py` - non-business logic functions, e.g. response normalization, data enrichment, etc.
   9. `exceptions` - module specific exceptions, e.g. `PostNotFound`, `InvalidUserData`

### 2. Excessively use Pydantic
Pydantic has a rich set of features to validate and transform data. 

In addition to regular features like required, non-required fields and default data, 
it has built-in comprehensive data processing params like regex, enums for limited allowed options, length validation, email validation, etc.
```python3
from enum import Enum
from pydantic import BaseModel, constr, EmailStr, Field, AnyUrl

class MusicBand(str, Enum):
   AEROSMITH = "AEROSMITH"
   QUEEN = "QUEEN"
   ACDC = "AC/DC"


class UserBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: constr(regex="^[A-Za-z0-9-_]+$", to_lower=True, strip_whitespace=True)
    email: EmailStr
    age: int = Field(ge=18, default=None)  # must be greater or equal to 18
    favorite_band: MusicBand = None. # only "AEROSMITH", "QUEEN", "AC/DC" values are allowed to be inputted
    website: AnyUrl = None

```
### 3. Use dependencies for data validation vs DB
Pydantic can only validate the values of client input. 
Use dependencies to validate data against database requirements like email already exists, user not found, etc. 
```python3
# dependencies.py
async def valid_post_id(post_id: UUID4) -> Mapping:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


# router.py
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post_by_id(post: Mapping = Depends(valid_post_id)):
    return post


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    update_data: PostUpdate,  
    post: Mapping = Depends(valid_post_id), 
):
    updated_post: Mapping = await service.update(id=post["id"], data=update_data)
    return updated_post


@router.get("/posts/{post_id}/reviews", response_model=list[ReviewsResponse])
async def get_post_reviews(post: Mapping = Depends(valid_post_id)):
    post_reviews: list[Mapping] = await reviews_service.get_by_post_id(post["id"])
    return post_reviews
```
If we didn't put data validation to dependency, we would have to add post_id validation
for every endpoint and write the same tests for each of them. 

### 5. Chain dependencies
Dependencies can use other dependencies and avoid code repetition for similar logic.
```python3
# dependencies.py
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

async def valid_post_id(post_id: UUID4) -> Mapping:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except JWTError:
        raise InvalidCredentials()

    return {"user_id": payload["id"]}


async def valid_owned_post(
    post: Mapping = Depends(valid_post_id), 
    token_data: dict = Depends(parse_jwt_data),
) -> Mapping:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()

    return post

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(post: Mapping = Depends(valid_owned_post)):
    """Get post that belong the user."""
    return post

```
### 6. Decouple & Reuse dependencies. Dependency calls are cached.
Depdencies can be reused multiple times and they won't be recalculated - FastAPI caches their result by default,
i.e. if we have dependency which calls service `get_post_by_id`,
we won't be visiting DB each time we call this dependency - only the first time.
   1. If attr is better to be validated through several dependencies - do it, don't make monster dependencies
```python3
# dependencies.py
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

async def valid_post_id(post_id: UUID4) -> Mapping:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except JWTError:
        raise InvalidCredentials()

    return {"user_id": payload["id"]}


async def valid_owned_post(
    post: Mapping = Depends(valid_post_id), 
    token_data: dict = Depends(parse_jwt_data),
) -> Mapping:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()

    return post


async def valid_active_creator(
    token_data: dict = Depends(parse_jwt_data),
):
    user = await users_service.get_by_id(token_data["user_id"])
    if not user["is_active"]:
        raise UserIsBanned()
    
    return user
        

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    post: Mapping = Depends(valid_owned_post),
    user: Mapping = Depends(valid_active_creator),
):
    """Get post that belong the active user."""
    
    return post

```

### 7. Follow REST
1. Developing RESTfull API makes it easier to reuse dependencies e.g. /users/:user_id, /users/:user_id/posts/:post_id
2. Add /me endpoint for users own posts 
   1. No need to validate that user id exists - it's already checked via auth
   2. No need to check user id belongs to the requester

### 8. DON'T MAKE YOUR ROUTE ASYNC IF YOU CONNECT TO DB OR MAKE EXTERNAL REQUESTS SYNC
### 9. Custom base model model from day 0, 
convert datetime to common standard
### 10. Hide docs by default. Show it explicitly on the selected envs
### 11. Use Starlette's Config object, instead of 3rd party ones - it's decent enough
### 12. Set DB keys naming convention immediately, from day 0
### 13. Set DB table naming convention immediately, from day 0
### 14. Set uuids within the app
it's easier to test
### 15. Set tests client async from day 0
1. Unless you aren't planning to add integrational tests with db
2. If you do, then do it. Problems with event loop will appear once you want to prepare objects
### 16. Set postgres identity from day 0
### 17. take use of background workers - they are stable enough
good for both async and sync routes
### 18. take use of response model, response status, responses
### 19. typing is important - use it everywhere
### 20. save files in chunk
### 21. use smart union or add explicit invalidation
### 22. do a lot of logic in db, use pydantic to parse it (show the way we evolved creator field)
### 23. validate file formats
### 24. validate url source (if users are able to send files)
### 25. root_validator if multiple columns
### 26. pre if data need to be pre-handled before validation
### 27. you can just raise a ValueError in pydantic schemas, if that's it faces user request. 
it will return a nice response
### 28. don't forget that fastapi converts response Model to Dict then to Model then to JSON
### 29. if no async lib, and poor documentation, then use asgiref
### 30. use linters (black, isort, autoflake)
### 31. set logs from day 0
