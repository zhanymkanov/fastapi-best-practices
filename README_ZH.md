# Fast Api最佳实践指南

这是我在初创公司使用的一系列最佳实践和约定。

在过去几年的生产实践中，我们做过一些好的和不好的决策，这些决策极大地影响了开发者体验。其中一些经验值得分享。

## 目录
- [Fast Api最佳实践指南](#fast-api最佳实践指南)
  - [目录](#目录)
  - [项目结构](#项目结构)
  - [异步路由](#异步路由)
    - [I/O密集型任务](#io密集型任务)
    - [CPU密集型任务](#cpu密集型任务)
  - [Pydantic](#pydantic)
    - [大量使用Pydantic](#大量使用pydantic)
    - [自定义基础模型](#自定义基础模型)
    - [拆分Pydantic BaseSettings](#拆分pydantic-basesettings)
  - [依赖项](#依赖项)
    - [超越依赖注入](#超越依赖注入)
    - [链式依赖](#链式依赖)
    - [拆分并复用依赖项。依赖调用会被缓存](#拆分并复用依赖项依赖调用会被缓存)
    - [优先使用`async`依赖项](#优先使用async依赖项)
  - [其他](#其他)
    - [遵循REST规范](#遵循rest规范)
    - [FastAPI响应序列化](#fastapi响应序列化)
    - [如果必须使用同步SDK，请在线程池中运行它。](#如果必须使用同步sdk请在线程池中运行它)
    - [ValueErrors可能会变成Pydantic ValidationError](#valueerrors可能会变成pydantic-validationerror)
    - [文档](#文档)
    - [迁移工具Alembic](#迁移工具alembic)
    - [设置数据库键命名约定](#设置数据库键命名约定)
    - [SQL优先，Pydantic次之](#sql优先pydantic次之)
    - [从一开始就设置异步测试客户端](#从一开始就设置异步测试客户端)
    - [使用ruff](#使用ruff)
  - [额外部分](#额外部分)
  
## 项目结构

项目结构有很多种，但最好的结构是一致、直观且没有意外的。

许多示例项目和教程按文件类型（如crud、routers、models）划分项目，这种方式对于微服务或范围较小的项目很有效。但是，这种方法并不适合我们这个包含许多领域和模块的单体应用。

我发现对于这类情况，更具可扩展性和可演进性的结构是受Netflix的[Dispatch](https://github.com/Netflix/dispatch)启发，并做了一些小修改。

```
fastapi-project
├── alembic/
├── src
│   ├── auth
│   │   ├── router.py
│   │   ├── schemas.py  # pydantic模型
│   │   ├── models.py  # 数据库模型
│   │   ├── dependencies.py
│   │   ├── config.py  # 本地配置
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── aws
│   │   ├── client.py  # 用于外部服务通信的客户端模型
│   │   ├── schemas.py
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   ├── posts
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── models.py
│   │   ├── dependencies.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── service.py
│   │   └── utils.py
│   ├── config.py  # 全局配置
│   ├── models.py  # 全局模型
│   ├── exceptions.py  # 全局异常
│   ├── pagination.py  # 全局模块，如分页
│   ├── database.py  # 数据库连接相关内容
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


1. 将所有领域目录存储在`src`文件夹中
   1. `src/` - 应用的最高级别，包含通用模型、配置和常量等。
   2. `src/main.py` - 项目的根文件，用于初始化FastAPI应用

2. 每个包都有自己的路由、模式、模型等。
   1. `router.py` - 每个模块的核心，包含所有端点
   2. `schemas.py` - 用于pydantic模型
   3. `models.py` - 用于数据库模型
   4. `service.py` - 模块特定的业务逻辑
   5. `dependencies.py` - 路由依赖项
   6. `constants.py` - 模块特定的常量和错误代码
   7. `config.py` - 例如环境变量
   8. `utils.py` - 非业务逻辑函数，例如响应规范化、数据丰富等
   9. `exceptions.py` - 模块特定的异常，例如`PostNotFound`、`InvalidUserData`

3. 当包需要其他包的服务、依赖项或常量时，使用显式的模块名导入
```python
from src.auth import constants as auth_constants
from src.notifications import service as notification_service
from src.posts.constants import ErrorCode as PostsErrorCode  # 以防每个包的constants模块中都有标准的ErrorCode
```

## 异步路由

FastAPI首先是一个异步框架。它设计用于处理异步I/O操作，这也是它如此快速的原因。

然而，FastAPI并不限制你只能使用`async`路由，开发者也可以使用同步路由。这可能会让初学者误以为它们是一样的，但实际上并非如此。

### I/O密集型任务

在底层，FastAPI可以有效地处理异步和同步I/O操作。

- FastAPI在线程池中运行同步路由，阻塞的I/O操作不会阻止事件循环执行任务。
- 如果路由定义为`async`，那么它会通过`await`正常调用，FastAPI相信你只会执行非阻塞的I/O操作。

需要注意的是，如果你违反了这种信任，在异步路由中执行阻塞操作，事件循环将无法在阻塞操作完成之前运行后续任务。

```python
import asyncio
import time

from fastapi import APIRouter

router = APIRouter()

@router.get("/terrible-ping")
async def terrible_ping():
    time.sleep(10) # 10秒的I/O阻塞操作，整个进程都会被阻塞

    return {"pong": True}

@router.get("/good-ping")
def good_ping():
    time.sleep(10) # 10秒的I/O阻塞操作，但在单独的线程中运行整个`good_ping`路由

    return {"pong": True}

@router.get("/perfect-ping")
async def perfect_ping():
    await asyncio.sleep(10) # 非阻塞I/O操作

    return {"pong": True}
```

**当我们调用时会发生什么：**

1. `GET /terrible-ping`
    1. FastAPI服务器接收请求并开始处理
    2. 服务器的事件循环和队列中的所有任务都将等待`time.sleep()`完成
        1. 服务器认为`time.sleep()`不是I/O任务，所以会等待它完成
        2. 等待期间，服务器不会接受任何新请求
    3. 服务器返回响应。
        1. 响应之后，服务器开始接受新请求
2. `GET /good-ping`
    1. FastAPI服务器接收请求并开始处理
    2. FastAPI将整个路由`good_ping`发送到线程池，工作线程将在那里运行该函数
    3. 在`good_ping`执行期间，事件循环从队列中选择下一个任务并处理它们（例如接受新请求、调用数据库）
        - 独立于主线程（即我们的FastAPI应用），工作线程将等待`time.sleep`完成。
        - 同步操作只阻塞子线程，而不是主线程。
    4. 当`good_ping`完成工作后，服务器向客户端返回响应
3. `GET /perfect-ping`
    1. FastAPI服务器接收请求并开始处理
    2. FastAPI等待`asyncio.sleep(10)`
    3. 事件循环从队列中选择下一个任务并处理它们（例如接受新请求、调用数据库）
    4. 当`asyncio.sleep(10)`完成后，服务器完成路由的执行并向客户端返回响应

> [!WARNING]
关于线程池的注意事项：
> 
> - 线程比协程需要更多资源，因此它们不像异步I/O操作那样轻量。
> - 线程池的线程数量是有限的，也就是说，你可能会耗尽线程，导致应用变慢。[了解更多](https://github.com/Kludex/fastapi-tips?tab=readme-ov-file#2-be-careful-with-non-async-functions)（外部链接）

### CPU密集型任务

第二个需要注意的是，非阻塞的可等待对象或发送到线程池的操作必须是I/O密集型任务（例如打开文件、数据库调用、外部API调用）。

- 等待CPU密集型任务（例如繁重的计算、数据处理、视频转码）是没有意义的，因为CPU必须工作才能完成这些任务，而I/O操作是外部的，服务器在等待这些操作完成时什么也不做，因此它可以处理下一个任务。
- 在其他线程中运行CPU密集型任务也不是有效的，因为[GIL（全局解释器锁）](https://realpython.com/python-gil/)的存在。简而言之，GIL只允许一个线程同时工作，这使得它对CPU任务毫无用处。
- 如果你想优化CPU密集型任务，你应该将它们发送到另一个进程中的工作节点。

**困惑用户的相关StackOverflow问题**

1. [https://stackoverflow.com/questions/62976648/architecture-flask-vs-fastapi/70309597#70309597](https://stackoverflow.com/questions/62976648/architecture-flask-vs-fastapi/70309597#70309597)
    - 在这里你也可以查看[我的回答](https://stackoverflow.com/a/70309597/6927498)
2. [https://stackoverflow.com/questions/65342833/fastapi-uploadfile-is-slow-compared-to-flask](https://stackoverflow.com/questions/65342833/fastapi-uploadfile-is-slow-compared-to-flask)
3. [https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion](https://stackoverflow.com/questions/71516140/fastapi-runs-api-calls-in-serial-instead-of-parallel-fashion)

## Pydantic

### 大量使用Pydantic

Pydantic有丰富的功能来验证和转换数据。

除了常规功能（如带有默认值的必填和非必填字段），Pydantic还有内置的综合数据处理工具，如正则表达式、枚举、字符串操作、电子邮件验证等。

```python
from enum import Enum
from pydantic import AnyUrl, BaseModel, EmailStr, Field

class MusicBand(str, Enum):
   AEROSMITH = "AEROSMITH"
   QUEEN = "QUEEN"
   ACDC = "AC/DC"

class UserBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128, pattern="^[A-Za-z0-9-_]+$")
    email: EmailStr
    age: int = Field(ge=18)  # 必须大于或等于18
    favorite_band: MusicBand | None = None  # 只允许输入"AEROSMITH"、"QUEEN"、"AC/DC"值
    website: AnyUrl | None = None
```

### 自定义基础模型

拥有一个可控制的全局基础模型允许我们自定义应用中的所有模型。例如，我们可以强制使用标准的 datetime 格式，或者为基础模型的所有子类引入一个通用方法。

```python
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, field_serializer

class CustomModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value

    def serializable_dict(self, **kwargs):
        """返回仅包含可序列化字段的字典。"""
        default_dict = self.model_dump()

        return jsonable_encoder(default_dict)
```

在上面的例子中，我们决定创建一个全局基础模型，它：

- 将所有datetime字段序列化为具有显式时区的标准格式
- 提供一个方法来返回仅包含可序列化字段的字典

### 拆分Pydantic BaseSettings

BaseSettings是读取环境变量的一项伟大创新，但为整个应用使用单个BaseSettings随着时间的推移可能会变得混乱。为了提高可维护性和组织性，我们将BaseSettings拆分到不同的模块和领域中。

```python
# src.auth.config
from datetime import timedelta

from pydantic_settings import BaseSettings

class AuthConfig(BaseSettings):
    JWT_ALG: str
    JWT_SECRET: str
    JWT_EXP: int = 5  # 分钟

    REFRESH_TOKEN_KEY: str
    REFRESH_TOKEN_EXP: timedelta = timedelta(days=30)

    SECURE_COOKIES: bool = True

auth_settings = AuthConfig()

# src.config
from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings

from src.constants import Environment

class Config(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    SITE_DOMAIN: str = "myapp.com"

    ENVIRONMENT: Environment = Environment.PRODUCTION

    SENTRY_DSN: str | None = None

    CORS_ORIGINS: list[str]
    CORS_ORIGINS_REGEX: str | None = None
    CORS_HEADERS: list[str]

    APP_VERSION: str = "1.0"

settings = Config()
```

## 依赖项

### 超越依赖注入

Pydantic是一个很棒的模式验证器，但对于涉及调用数据库或外部服务的复杂验证，它还不够。

FastAPI文档主要将依赖项展示为端点的依赖注入，但它们也非常适合请求验证。

依赖项可用于根据数据库约束验证数据（例如，检查电子邮件是否已存在、确保找到用户等）。

```python
# dependencies.py
async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post

# router.py
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post_by_id(post: dict[str, Any] = Depends(valid_post_id)):
    return post

@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    update_data: PostUpdate,  
    post: dict[str, Any] = Depends(valid_post_id), 
):
    updated_post = await service.update(id=post["id"], data=update_data)
    return updated_post

@router.get("/posts/{post_id}/reviews", response_model=list[ReviewsResponse])
async def get_post_reviews(post: dict[str, Any] = Depends(valid_post_id)):
    post_reviews = await reviews_service.get_by_post_id(post["id"])
    return post_reviews
```

如果我们没有将数据验证放入依赖项中，我们将不得不为每个端点验证`post_id`是否存在，并为每个端点编写相同的测试。

### 链式依赖

依赖项可以使用其他依赖项，避免类似逻辑的代码重复。

```python
# dependencies.py
from fastapi.security import OAuth2PasswordBearer
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post

async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except InvalidTokenError:
        raise InvalidCredentials()

    return {"user_id": payload["id"]}

async def valid_owned_post(
    post: dict[str, Any] = Depends(valid_post_id), 
    token_data: dict[str, Any] = Depends(parse_jwt_data),
) -> dict[str, Any]:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()

    return post

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(post: dict[str, Any] = Depends(valid_owned_post)):
    return
```

### 拆分并复用依赖项。依赖调用会被缓存

依赖项可以多次复用，并且它们不会被重新计算——FastAPI默认在请求的范围内缓存依赖项的结果，也就是说，如果`valid_post_id`在一个路由中被多次调用，它只会被调用一次。

了解这一点后，我们可以将依赖项拆分为多个更小的函数，这些函数在更小的领域上运行，并且更容易在其他路由中复用。

例如，在下面的代码中，我们三次使用`parse_jwt_data`：

1. `valid_owned_post`
2. `valid_active_creator`
3. `get_user_post`

但`parse_jwt_data`只在第一次调用时被调用一次。

```python
# dependencies.py
from fastapi import BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

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
    except InvalidTokenError:
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
    
    if not user["is_creator"]:
       raise UserNotCreator()
    
    return user
        

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    worker: BackgroundTasks,
    post: Mapping = Depends(valid_owned_post),
    user: Mapping = Depends(valid_active_creator),
):
    """Get post that belong the active user."""
    worker.add_task(notifications_service.send_email, user["id"])
    return post
```

### 优先使用`async`依赖项

FastAPI同时支持同步和异步依赖项，当你不需要等待任何东西时，很容易会想使用同步依赖项，但这可能不是最佳选择。

与路由一样，同步依赖项在线程池中运行。这里的线程也有代价和限制，如果只是进行小的非I/O操作，这些代价和限制是多余的。

[了解更多](https://github.com/Kludex/fastapi-tips?tab=readme-ov-file#9-your-dependencies-may-be-running-on-threads)（外部链接）

## 其他

### 遵循REST规范

开发RESTful API可以更轻松地在如下路由中复用依赖项：

1. `GET /courses/:course_id`
2. `GET /courses/:course_id/chapters/:chapter_id/lessons`
3. `GET /chapters/:chapter_id`

唯一需要注意的是必须在路径中使用相同的变量名：

- 如果你有两个端点`GET /profiles/:profile_id`和`GET /creators/:creator_id`，它们都验证给定的`profile_id`是否存在，但`GET /creators/:creator_id`还检查该个人资料是否是创作者，那么最好将`creator_id`路径变量重命名为`profile_id`并链接这两个依赖项。

```python
# src.profiles.dependencies
async def valid_profile_id(profile_id: UUID4) -> Mapping:
    profile = await service.get_by_id(profile_id)
    if not profile:
        raise ProfileNotFound()

    return profile

# src.creators.dependencies
async def valid_creator_id(profile: Mapping = Depends(valid_profile_id)) -> Mapping:
    if not profile["is_creator"]:
       raise ProfileNotCreator()

    return profile

# src.profiles.router.py
@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_user_profile_by_id(profile: Mapping = Depends(valid_profile_id)):
    """Get profile by id."""
    return profile

# src.creators.router.py
@router.get("/creators/{profile_id}", response_model=ProfileResponse)
async def get_user_profile_by_id(
     creator_profile: Mapping = Depends(valid_creator_id)
):
    """Get creator's profile by id."""
    return creator_profile

```

### FastAPI响应序列化

你可能认为可以返回与路由的`response_model`匹配的Pydantic对象来进行一些优化，但你错了。

FastAPI首先使用其`jsonable_encoder`将该pydantic对象转换为字典，然后使用你的`response_model`验证数据，最后才将你的对象序列化为JSON。

这意味着你的Pydantic模型对象会被创建两次：

- 第一次，当你显式创建它以从路由返回时。
- 第二次，FastAPI隐式创建它以根据response_model验证响应数据。

```python
from fastapi import FastAPI
from pydantic import BaseModel, root_validator

app = FastAPI()

class ProfileResponse(BaseModel):
    @model_validator(mode="after")
    def debug_usage(self):
        print("created pydantic model")

        return self

@app.get("/", response_model=ProfileResponse)
async def root():
    return ProfileResponse()

```

**日志输出：**

```
[INFO] [2022-08-28 12:00:00.000000] created pydantic model
[INFO] [2022-08-28 12:00:00.000020] created pydantic model

```

### 如果必须使用同步SDK，请在线程池中运行它。

如果你必须使用一个库与外部服务交互，并且它不是异步的，那么在外部工作线程中进行HTTP调用。

我们可以使用starlette中著名的`run_in_threadpool`。

```python
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from my_sync_library import SyncAPIClient 

app = FastAPI()

@app.get("/")
async def call_my_sync_library():
    my_data = await service.get_my_data()

    client = SyncAPIClient()
    await run_in_threadpool(client.make_request, data=my_data)
```

### ValueErrors可能会变成Pydantic ValidationError

如果你在直接面向客户端的Pydantic模式中引发`ValueError`，它将向用户返回一个详细的响应。

```python
# src.profiles.schemas
from pydantic import BaseModel, field_validator

class ProfileCreate(BaseModel):
    username: str
    
    @field_validator("password", mode="after")
    @classmethod
    def valid_password(cls, password: str) -> str:
        if not re.match(STRONG_PASSWORD_PATTERN, password):
            raise ValueError(
                "Password must contain at least "
                "one lower character, "
                "one upper character, "
                "digit or "
                "special symbol"
            )

        return password

# src.profiles.routes
from fastapi import APIRouter

router = APIRouter()

@router.post("/profiles")
async def get_creator_posts(profile_data: ProfileCreate):
   pass
```

**响应示例：**

<img src="images/value_error_response.png" width="400" height="auto">

### 文档

1. 除非你的API是公共的，否则默认隐藏文档。只在选定的环境中显式显示它。

```python
from fastapi import FastAPI
from starlette.config import Config

config = Config(".env")  # parse .env file for env variables

ENVIRONMENT = config("ENVIRONMENT")  # get current env name
SHOW_DOCS_ENVIRONMENT = ("local", "staging")  # explicit list of allowed envs

app_configs = {"title": "My Cool API"}
if ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
   app_configs["openapi_url"] = None  # set url for docs as null

app = FastAPI(**app_configs)
```

1. 帮助FastAPI生成易于理解的文档
    1. 设置`response_model`、`status_code`、`description`等。
    2. 如果模型和状态不同，使用`responses`路由属性为不同的响应添加文档

```python
from fastapi import APIRouter, status

router = APIRouter()

@router.post(
    "/endpoints",
    response_model=DefaultResponseModel,  # default response pydantic model 
    status_code=status.HTTP_201_CREATED,  # default status code
    description="Description of the well documented endpoint",
    tags=["Endpoint Category"],
    summary="Summary of the Endpoint",
    responses={
        status.HTTP_200_OK: {
            "model": OkResponse, # custom pydantic model for 200 response
            "description": "Ok Response",
        },
        status.HTTP_201_CREATED: {
            "model": CreatedResponse,  # custom pydantic model for 201 response
            "description": "Creates something from user request",
        },
        status.HTTP_202_ACCEPTED: {
            "model": AcceptedResponse,  # custom pydantic model for 202 response
            "description": "Accepts request and handles it later",
        },
    },
)
async def documented_route():
    pass
```

将生成如下文档：

<img src="images/custom_responses.png" width="400" height="auto">

**设置数据库键命名约定**

根据数据库的约定显式设置索引命名比使用sqlalchemy的默认命名方式更好。

```jsx
from sqlalchemy import MetaData

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)
```

### 迁移工具Alembic

1. 迁移必须是静态的且可回滚的。如果你的迁移依赖于动态生成的数据，那么确保只有数据本身是动态的，而不是其结构。
2. 生成具有描述性名称和slug的迁移。slug是必需的，应该解释所做的更改。
3. 为新迁移设置人类可读的文件模板。我们使用`date*_*slug*.py`模式，例如`2022-08-24_post_content_idx.py`

```
# alembic.ini
file_template = %%(year)d-%%(month).2d-%%(day).2d_%%(slug)s
```

### 设置数据库键命名约定

保持名称的一致性很重要。我们遵循的一些规则：

1. 小写蛇形命名（lower_case_snake）
2. 单数形式（例如`post`、`post_like`、`user_playlist`）
3. 用模块前缀对类似的表进行分组，例如`payment_account`、`payment_bill`、`post`、`post_like`
4. 在表之间保持一致，但具体命名也可以，例如
    1. 在所有表中使用`profile_id`，但如果其中一些表只需要作为创作者的个人资料，则使用`creator_id`
    2. 在`post_like`、`post_view`等抽象表中使用`post_id`，但在相关模块中使用具体命名，如`chapters.course_id`中的`course_id`
5. datetime类型字段使用`_at`后缀
6. date类型字段使用`_date`后缀

### SQL优先，Pydantic次之

- 通常，数据库处理数据的速度比CPython快得多，也更简洁。
- 最好使用SQL进行所有复杂的连接和简单的数据操作。
- 最好在数据库中为具有嵌套对象的响应聚合JSON。

```python
# src.posts.service
from typing import Any

from pydantic import UUID4
from sqlalchemy import desc, func, select, text
from sqlalchemy.sql.functions import coalesce

from src.database import database, posts, profiles, post_review, products

async def get_posts(
    creator_id: UUID4, *, limit: int = 10, offset: int = 0
) -> list[dict[str, Any]]: 
    select_query = (
        select(
            (
                posts.c.id,
                posts.c.slug,
                posts.c.title,
                func.json_build_object(
                   text("'id', profiles.id"),
                   text("'first_name', profiles.first_name"),
                   text("'last_name', profiles.last_name"),
                   text("'username', profiles.username"),
                ).label("creator"),
            )
        )
        .select_from(posts.join(profiles, posts.c.owner_id == profiles.c.id))
        .where(posts.c.owner_id == creator_id)
        .limit(limit)
        .offset(offset)
        .group_by(
            posts.c.id,
            posts.c.type,
            posts.c.slug,
            posts.c.title,
            profiles.c.id,
            profiles.c.first_name,
            profiles.c.last_name,
            profiles.c.username,
            profiles.c.avatar,
        )
        .order_by(
            desc(coalesce(posts.c.updated_at, posts.c.published_at, posts.c.created_at))
        )
    )
    
    return await database.fetch_all(select_query)

# src.posts.schemas
from typing import Any

from pydantic import BaseModel, UUID4

   
class Creator(BaseModel):
    id: UUID4
    first_name: str
    last_name: str
    username: str

class Post(BaseModel):
    id: UUID4
    slug: str
    title: str
    creator: Creator

    
# src.posts.router
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/creators/{creator_id}/posts", response_model=list[Post])
async def get_creator_posts(creator: dict[str, Any] = Depends(valid_creator_id)):
   posts = await service.get_posts(creator["id"])

   return posts
```

### 从一开始就设置异步测试客户端

使用数据库编写集成测试很可能在将来导致混乱的事件循环错误。立即设置异步测试客户端，例如[httpx](https://github.com/encode/starlette/issues/652)

```python
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app  # inited FastAPI app

@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_post(client: AsyncClient):
    resp = await client.post("/posts")

    assert resp.status_code == 201
```

除非你有同步数据库连接（抱歉？）或者不打算编写集成测试。

### 使用ruff

有了代码检查工具，你可以忘记代码格式化，专注于编写业务逻辑。

[Ruff](https://github.com/astral-sh/ruff)是一个“速度极快”的新代码检查工具，它替代了black、autoflake、isort，并支持600多个检查规则。

使用pre-commit钩子是一种流行的最佳实践，但对我们来说，只使用脚本就足够了。

```bash
#!/bin/sh -e
set -x

ruff check --fix src
ruff format src
```

## 额外部分

一些非常善良的人分享了他们自己的经验和最佳实践，绝对值得一读。

查看项目的[issues（问题）](https://github.com/zhanymkanov/fastapi-best-practices/issues)部分。

例如，[lowercase00](https://github.com/zhanymkanov/fastapi-best-practices/issues/4)详细描述了他们在权限和认证、基于类的服务和视图、任务队列、自定义响应序列化器、使用dynaconf进行配置等方面的最佳实践。

如果你有关于使用FastAPI的经验要分享，无论是好是坏，都非常欢迎创建一个新的issue。我们很乐意阅读它。
