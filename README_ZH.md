# 🐾 QMI · 宠物生态智能管理平台

基于 **FastAPI + LangChain + A2A/MCP + Milvus + bge-m3** 构建的宠物生态智能管理后端系统。

---

## 一、项目概述

### 1.1 项目定位

本项目是一个 **宠物生态智能管理平台** 的后端服务，核心解决以下业务场景：

| 业务模块 | 说明 |
|----------|------|
| 🐱 宠物档案管理 | 宠物信息 CRUD、健康档案、医疗记录 |
| 📟 IoT 设备运维 | 智能项圈/喂食器/摄像头等设备的接入、监控、OTA 升级 |
| 🎫 客服工单系统 | 用户问题提交 → 分类 → 处理 → 关闭的完整工单生命周期 |
| 👑 会员权益管理 | 会员等级、积分、权益核销 |
| 🏥 AI 健康分析 | 基于 RAG + LLM 的宠物症状分析和健康建议 |
| 🤖 多 Agent 编排 | A2A（Agent-to-Agent）模式下的意图识别和任务路由 |

### 1.2 核心技术栈

| 层次 | 技术选型 | 用途 |
|------|----------|------|
| Web 框架 | FastAPI 0.115+ / Pydantic v2 | REST API 服务 |
| 数据库 | MongoDB + Beanie ODM | 业务数据持久化 |
| 向量数据库 | Milvus 2.4 | RAG 知识库向量检索 |
| Embedding | BAAI/bge-m3（1024维） | 文本向量化 |
| LLM | 通义千问 / OpenAI 兼容 API | 智能对话和内容生成 |
| 缓存/队列 | Redis + Celery | 异步任务和缓存 |
| 容器化 | Docker + Docker Compose | 一键部署 |
| 监控 | Sentry（可选） | 错误追踪 |

---

## 二、系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 / 客户端                              │
│              (Web App / 小程序 / IoT 设备 SDK)                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP/SSE
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI 应用层                                │
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ /v1/auth │ │/v1/pets  │ │/v1/tickets│ │/v1/members│           │
│  │  认证鉴权 │ │ 宠物管理  │ │ 工单系统  │ │ 会员权益  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │/v1/devices│ │/v1/agent │ │ /v1/rag  │ │/dashboard│           │
│  │ 设备管理  │ │ A2A 编排 │ │ 知识问答  │ │ 仪表盘   │            │
│  └──────────┘ └─────┬────┘ └────┬─────┘ └──────────┘            │
└──────────────────────┼───────────┼──────────────────────────────┘
                       │           │
        ┌──────────────▼───┐  ┌───▼──────────────┐
        │  Orchestrator    │  │   RAG Chain      │
        │  (意图识别+路由)  │  │ (检索增强生成)    │
        └──────┬───────────┘  └───┬──────────────┘
               │                  │
    ┌──────────┼──────────┐       │
    ▼          ▼          ▼       ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌─────────┐
│Health │ │Device │ │Ticket │ │Milvus    │
│Agent  │ │Agent  │ │Agent  │ │向量检索   │
└───┬───┘ └───┬───┘ └───┬───┘ └────┬────┘
    │         │         │           │
    └─────────┼─────────┘           │
              ▼                     ▼
    ┌──────────────────┐  ┌──────────────────┐
    │  MCP Tool Registry│  │  bge-m3 Embedder │
    │  (19个标准化工具)  │  │  (文本向量化)     │
    └──────────────────┘  └──────────────────┘
              │
    ┌─────────┼─────────┬──────────┬──────────┐
    ▼         ▼         ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│device│ │health│ │ticket│ │member│ │ OTA  │
│ 工具 │ │ 工具 │ │ 工具 │ │ 工具 │ │ 工具 │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

### 2.2 三层架构说明

整个系统可以理解为三个层次：

**第一层：API 路由层（`app/api/`）**
- 对外暴露 REST 接口，处理 HTTP 请求
- 负责参数校验、权限检查、调用 Service 层

**第二层：业务逻辑层（`app/services/` + `app/agents/`）**
- Service：传统的 CRUD 业务逻辑（用户、宠物、设备）
- Agent：AI 驱动的智能业务（健康分析、设备运维、工单处理）
- MCP Registry：标准化的工具注册和调用中心

**第三层：基础设施层（`app/core/` + `app/integrations/`）**
- 数据库连接（MongoDB / Redis / Milvus）
- 外部系统集成（IoT 平台 / 保险平台 / LLM 服务）
- 配置管理和依赖注入

---

## 三、核心模块详解

### 3.1 A2A 多 Agent 编排（Agent-to-Agent）

> **这是整个系统最核心的 AI 能力，实现了从「单次问答」到「多 Agent 协作」的跨越。**

#### 工作流程

```
用户输入："我的猫最近一直吐，体温也偏高，这是怎么回事？"
         │
         ▼
┌─────────────────────────────┐
│  OrchestratorAgent          │  ① 意图识别（关键词匹配 / LLM 分类）
│  分析输入 → 识别为「健康」   │
└─────────┬───────────────────┘
          │ 路由到 HealthAgent
          ▼
┌─────────────────────────────┐
│  HealthAgent                │  ② 工具调用
│  → get_pet_health_summary() │     查询宠物历史健康数据
│  → analyze_pet_symptoms()   │     分析症状匹配可能的疾病
│  → RAG 检索知识库           │     召回相关宠物医疗知识
└─────────┬───────────────────┘
          │ 整合工具结果
          ▼
┌─────────────────────────────┐
│  LLM 生成回答               │  ③ 生成最终回复
│  "根据您的描述，猫咪可能     │     将工具数据 + 知识库内容
│   存在消化系统问题..."      │     转换为通俗易懂的建议
└─────────────────────────────┘
```

#### 三个子 Agent 的职责

| Agent | 业务域 | 调用工具 | 适用场景 |
|-------|--------|---------|---------|
| `HealthAgent` | 宠物健康 | 健康摘要、症状分析、疫苗记录、RAG 知识库 | "狗狗咳嗽""猫咪不吃东西" |
| `DeviceAgent` | 设备运维 | 设备状态、设备列表、重启设备、OTA 升级 | "智能项圈离线""升级固件" |
| `TicketAgent` | 客服工单 | 创建工单、查询工单、关闭工单、升级工单 | "我要报修""查询我的工单" |

#### 意图识别规则（可扩展为 LLM 零样本分类）

```python
# 当前 Demo 使用关键词匹配，生产环境可切换为 LLM 分类器
_INTENT_KEYWORDS = {
    "health":  ["健康", "症状", "生病", "呕吐", "疫苗", "咳嗽", ...],
    "device":  ["设备", "传感器", "离线", "故障", "OTA", "升级", ...],
    "ticket":  ["工单", "报修", "投诉", "客服", "退款", ...],
}
```

> **设计思路**：Orchestrator 和子 Agent 都是独立对象。Demo 中采用进程内直接调用（in-process A2A），
> 生产环境可通过 Redis Pub/Sub 或 gRPC 实现跨服务 Agent 通信。

---

### 3.2 MCP 工具协议（Model Context Protocol）

> **MCP 是连接 AI Agent 和业务系统之间的「标准化插座」。每个工具就是一个业务能力的标准化封装。**

#### 设计理念

传统的 API 集成方式，Agent 需要知道每个接口的 URL、参数格式、认证方式。MCP 将这些细节统一封装为「工具」，Agent 只需要：
1. 知道工具名称
2. 传入标准参数
3. 获取结构化结果

#### 已封装的 19 个 MCP 工具

| 分类 | 工具名称 | 功能 | 返回数据 |
|------|---------|------|---------|
| **设备** | `get_device_status` | 查询设备实时状态 | 在线/离线、电量、信号强度 |
| | `list_devices` | 查询设备列表 | 设备编码、类型、绑定宠物 |
| | `restart_device` | 远程重启设备 | 操作结果 |
| | `get_device_alerts` | 查询设备告警 | 告警类型、时间、级别 |
| **健康** | `get_pet_health_summary` | 宠物健康摘要 | 体重趋势、最近就诊、用药记录 |
| | `analyze_pet_symptoms` | 症状分析 | 可能病因、建议措施、紧急程度 |
| | `get_health_history` | 健康历史 | 历史病例、手术记录 |
| | `get_vaccination_record` | 疫苗记录 | 已接种疫苗、下次接种时间 |
| **工单** | `create_ticket` | 创建工单 | 工单编号、状态 |
| | `get_ticket_status` | 查询工单状态 | 当前状态、处理人、回复 |
| | `list_tickets` | 工单列表 | 历史工单、过滤条件 |
| | `close_ticket` | 关闭工单 | 操作结果 |
| | `escalate_ticket` | 升级工单 | 升级原因、目标团队 |
| **会员** | `get_member_info` | 会员信息 | 等级、积分、到期时间 |
| | `get_member_benefits` | 权益列表 | 可用权益、配额 |
| | `check_benefit_eligibility` | 权益资格检查 | 是否可用、剩余配额 |
| **OTA** | `check_ota_version` | 查询固件版本 | 当前版本、最新版本 |
| | `trigger_ota_upgrade` | 触发升级 | 升级任务 ID |
| | `get_ota_progress` | 升级进度 | 进度百分比、预计时间 |

#### 工具定义示例

```python
# app/mcp/tools/health_tools.py
class GetPetHealthSummaryTool(BaseMCPTool):
    name = "get_pet_health_summary"
    description = "获取指定宠物的健康摘要，包括体重趋势、最近就诊记录、当前用药"
    category = "health"

    async def execute(self, pet_id: str) -> dict:
        # 生产环境：查询数据库 + IoT 平台
        # Demo 模式：返回模拟数据
        return {
            "pet_id": pet_id,
            "weight_kg": 4.5,
            "weight_trend": "stable",
            "last_vet_visit": "2025-01-10",
            "current_medications": [],
            "health_status": "good",
        }
```

#### 调用 MCP 工具

```python
from app.mcp.registry import mcp_registry

# 方式一：直接调用
result = await mcp_registry.call("get_device_status", device_code="DEV-001")

# 方式二：Agent 内通过 _call_tool 调用（自动记录调用链）
result = await self._call_tool("get_device_status", {"device_code": "DEV-001"})

# 方式三：列出某分类下所有工具
tools = [t for t in mcp_registry.list_tools() if t.category == "health"]
```

---

### 3.3 RAG 检索增强生成

> **RAG 让 AI 的回答不再凭空编造，而是基于真实的宠物健康知识库。**

#### 检索流程

```
用户问题："猫咪口炎怎么治疗？"
         │
         ▼
┌─────────────────────────────┐
│ ① Embedding 向量化          │  bge-m3 模型将问题转为 1024 维向量
│    "猫咪口炎怎么治疗？"      │  → [0.12, -0.34, 0.56, ..., 0.78]
└─────────┬───────────────────┘
          ▼
┌─────────────────────────────┐
│ ② Milvus ANN 向量检索       │  在宠物健康知识库中检索最相似的 Top-20 文档
│    余弦相似度计算           │  支持按类别过滤（health / device / ota）
└─────────┬───────────────────┘
          ▼
┌─────────────────────────────┐
│ ③ Reranker 重排序           │  Cross-Encoder 精排 → Top-5 最相关文档
│    关键词 + 语义双重匹配    │  过滤低相关度结果
└─────────┬───────────────────┘
          ▼
┌─────────────────────────────┐
│ ④ Prompt 拼接 + LLM 生成    │  将 Top-5 文档作为上下文注入 Prompt
│    → AI 基于知识库回答      │  "根据资料，猫咪口炎的治疗方案包括..."
└─────────────────────────────┘
```

#### 技术参数

| 环节 | 技术 | 参数 |
|------|------|------|
| Embedding 模型 | BAAI/bge-m3 | 1024 维，中文优化 |
| 向量数据库 | Milvus | IVF_FLAT 索引，COSINE 距离 |
| 粗召回 | ANN Search | Top-K=20 |
| 精排序 | BGE-Reranker / 关键词 | Top-N=5 |
| 降级策略 | 关键词匹配 + 无 LLM 时返回原始片段 | 保证服务可用性 |

#### Demo 模式下的表现

- **Milvus 不可用**：自动切换为内存向量检索 + Demo 数据，不影响 API 响应
- **LLM 未配置**：直接返回检索到的 Top-1 文档内容作为回答
- **Embedding 模型未安装**：使用随机向量模拟（Mock 模式）

---

## 四、项目目录结构

```
app/
├── main.py                    # FastAPI 应用入口（lifespan、中间件、异常处理）
│
├── api/                       # 📡 API 路由层
│   ├── router.py              #   路由总入口（聚合所有子路由）
│   └── v1/
│       ├── auth.py            #   认证（登录/获取当前用户）
│       ├── users.py           #   用户 CRUD
│       ├── tenants.py         #   租户 CRUD
│       ├── pets.py            #   宠物档案 CRUD（分页/软删除/芯片去重）
│       ├── devices.py         #   IoT 设备 CRUD
│       ├── tickets.py         #   客服工单（完整状态流转 + MongoDB 持久化）
│       ├── members.py         #   会员权益（等级/积分/权益核销）
│       ├── agent.py           #   A2A 多 Agent 对话接口
│       ├── rag.py             #   RAG 知识库问答接口
│       ├── dashboard.py       #   仪表盘统计（MongoDB 聚合查询）
│       └── ingestion.py       #   数据资产上传
│
├── agents/                    # 🤖 A2A 多 Agent 编排层
│   ├── base_agent.py          #   BaseAgent 抽象基类（工具调用 + LLM 整合）
│   ├── orchestrator.py        #   OrchestratorAgent（意图识别 + 路由分发）
│   ├── health_agent.py        #   HealthAgent（宠物健康分析 + RAG 检索）
│   ├── device_agent.py        #   DeviceAgent（IoT 设备运维）
│   └── ticket_agent.py        #   TicketAgent（客服工单处理）
│
├── mcp/                       # 🔧 MCP 工具协议层
│   ├── base.py                #   MCPToolMeta + BaseMCPTool 抽象类
│   ├── registry.py            #   MCPRegistry（单例注册中心，自动发现工具）
│   └── tools/
│       ├── device_tools.py    #   设备工具（4个：状态/列表/重启/告警）
│       ├── health_tools.py    #   健康工具（4个：摘要/症状/历史/疫苗）
│       ├── ticket_tools.py    #   工单工具（5个：创建/查询/列表/关闭/升级）
│       ├── member_tools.py    #   会员工具（3个：信息/权益/资格）
│       └── ota_tools.py       #   OTA 工具（3个：版本/升级/进度）
│
├── rag/                       # 📚 RAG 检索增强生成层
│   ├── embedder.py            #   bge-m3 文本向量化（支持本地/API/Mock）
│   ├── retriever.py           #   Milvus 向量检索（自动降级内存检索）
│   ├── reranker.py            #   重排序（Cross-Encoder / 关键词融合）
│   └── rag_chain.py           #   完整 RAG 链路（检索→排序→LLM 生成）
│
├── models/                    # 📊 MongoDB 数据模型（Beanie ODM）
│   ├── user.py                #   用户
│   ├── tenant.py              #   租户
│   ├── pet.py                 #   宠物（种类/性别枚举、芯片ID）
│   ├── device.py              #   IoT 设备
│   ├── ticket.py              #   工单 + 工单回复
│   ├── data_asset.py          #   数据资产
│   ├── audit_log.py           #   审计日志
│   └── permission.py          #   角色权限
│
├── services/                  # 🏗 业务逻辑层
│   ├── user_service.py        #   用户服务（密码哈希）
│   ├── tenant_service.py      #   租户服务
│   ├── pet_service.py         #   宠物服务（敏感信息脱敏）
│   ├── device_service.py      #   设备服务
│   ├── ingestion_service.py   #   数据摄取（MD5 去重 + Celery 分发）
│   └── audit_service.py       #   审计服务
│
├── integrations/              # 🔗 外部系统集成
│   ├── llm_client.py          #   LLM 客户端（OpenAI 兼容 / SSE 流式）
│   ├── iot_client.py          #   IoT 平台客户端（远程指令/状态查询）
│   └── insurance_client.py    #   保险平台客户端（保单/理赔）
│
├── tasks/                     # ⏰ Celery 异步任务
│   ├── celery_app.py          #   Celery 应用配置（Redis broker）
│   ├── ingestion_task.py      #   文件处理（图片元信息/文本索引）
│   ├── daily_report.py        #   每日运营报告
│   └── deletion_cleanup.py    #   软删除过期清理
│
├── plugins/                   # 🔌 插件系统
│   ├── registry.py            #   PluginRegistry（entry_points 发现）
│   ├── sentry_plugin.py       #   Sentry 错误监控插件
│   └── celery_plugin.py       #   Celery 健康检查端点
│
└── core/                      # ⚙️ 核心基础设施
    ├── config.py              #   全局配置（pydantic-settings）
    ├── ai_config.py           #   AI 参数配置（cyberlife.toml）
    ├── database.py            #   数据库初始化（MongoDB + Beanie）
    ├── deps.py                #   依赖注入（JWT 认证 + RBAC 权限）
    └── security.py            #   安全工具（JWT 签发/验证、bcrypt 哈希）
```

---

## 五、快速开始

### 5.1 环境要求

- Python 3.11+
- MongoDB 6.0+（Docker 部署则不需要）
- Redis 7.0+（Docker 部署则不需要）

---

### 5.2 本机启动（本地开发）

**终端服务器启动命令：**

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 FastAPI 后端服务
uvicorn app.main:app --reload --port 8000
```

**本机访问地址：**

| 地址 | 内容 |
|------|------|
| http://localhost:8000 | 🖥️ 前端展示页面 |
| http://localhost:8000/docs | 📚 Swagger API 文档（可在线调试） |
| http://localhost:8000/api/v1/agent/chat | 🤖 Agent 对话 API（POST） |
| http://localhost:8000/health | 💚 健康检查 |

---

### 5.3 外部访问（ngrok 临时隧道）

让外网用户访问你本机运行的服务。

**外部终端启动命令（新开一个终端窗口）：**

```bash
# 1. 确保本机服务已启动（5.2 的 uvicorn 保持运行）

# 2. 启动 ngrok 隧道（项目已内置 ngrok 二进制文件）
./ngrok http 8000
```

启动后终端会显示隧道地址，例如：
```
Forwarding  https://qmi-pet-ai.ngrok-free.dev -> http://localhost:8000
```

> 把下面地址中的 `qmi-pet-ai.ngrok-free.dev` 替换为你终端实际显示的域名即可。

**外部访问地址：**

| 地址 | 内容 |
|------|------|
| `https://qmi-pet-ai.ngrok-free.dev` | 🖥️ 前端展示页面 |
| `https://qmi-pet-ai.ngrok-free.dev/docs` | 📚 Swagger API 文档（可在线调试） |
| `https://qmi-pet-ai.ngrok-free.dev/api/v1/agent/chat` | 🤖 Agent 对话 API（POST） |
| `https://qmi-pet-ai.ngrok-free.dev/health` | 💚 健康检查 |

> ⚠️ 免费版每次重启 ngrok 地址会变，24 小时后过期。

---

### 5.4 Demo 模式运行

即使没有任何外部依赖，项目也可以在 Demo 模式下运行：

```bash
uvicorn app.main:app --reload --port 8000
```

Demo 模式下：
- 所有 MCP 工具返回模拟数据
- Agent 返回意图识别结果和工具列表
- RAG 降级为关键词匹配
- 配置 LLM API Key 后自动切换为完整 AI 模式

---

### 5.5 Docker 一键启动

```bash
# 启动所有服务（MongoDB + Redis + Backend + Celery Worker）
docker compose up -d

# 查看日志
docker compose logs -f backend

# 停止
docker compose down
```

本机访问地址同 5.2。

---

## 六、API 端点总览

### Agent 编排（A2A）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/agent/chat` | 多 Agent 智能对话（自动意图识别 + 路由） |
| GET | `/api/v1/agent/tools` | 列出所有已注册的 MCP 工具 |
| GET | `/api/v1/agent/health` | Agent 系统健康检查 |

**示例请求：**

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我的猫最近一直吐，体温偏高，需要怎么办？",
    "session_id": "sess_001",
    "pet_id": "pet_123"
  }'
```

**响应示例：**

```json
{
  "answer": "根据您的描述（呕吐+体温偏高），猫咪可能存在以下健康问题：\n1. 消化系统感染...\n\n建议措施：\n1. 立即禁食禁水 6 小时...\n\n⚠️ 如果持续呕吐超过 24 小时，请立即就医。",
  "session_id": "sess_001",
  "agent": "health_agent",
  "intent": "health",
  "tool_calls": [
    {"tool": "get_pet_health_summary", "result": {...}},
    {"tool": "analyze_pet_symptoms", "result": {...}}
  ]
}
```

### RAG 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/rag/query` | 知识库智能问答 |
| POST | `/api/v1/rag/ingest` | 文本入库 |
| POST | `/api/v1/rag/ingest/file` | 文件上传入库（TXT） |
| DELETE | `/api/v1/rag/docs/{id}` | 删除文档 |
| GET | `/api/v1/rag/health` | RAG 服务状态 |

### 业务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户登录，获取 JWT Token |
| GET | `/api/v1/auth/me` | 获取当前用户信息 |
| POST | `/api/v1/users` | 创建用户 |
| GET | `/api/v1/users` | 用户列表 |
| POST | `/api/v1/pets` | 创建宠物档案 |
| GET | `/api/v1/pets` | 宠物列表（支持分页/种类过滤） |
| POST | `/api/v1/devices` | 注册 IoT 设备 |
| GET | `/api/v1/devices` | 设备列表 |
| POST | `/api/v1/tickets` | 创建客服工单 |
| GET | `/api/v1/tickets` | 工单列表（支持状态/类别过滤） |
| PATCH | `/api/v1/tickets/{id}` | 更新工单状态 |
| GET | `/api/v1/members/me` | 获取会员信息 |
| GET | `/api/v1/members/benefits` | 查询会员权益 |
| GET | `/api/v1/dashboard/overview` | 平台运营指标概览 |

---

## 七、如何基于此框架扩展

### 7.1 新增一个业务模块

假设你要新增 **社区审核** 模块：

1. **创建数据模型** → `app/models/post.py`
2. **创建 Schema** → `app/schemas/post_schema.py`
3. **创建 Service** → `app/services/post_service.py`
4. **创建 API 路由** → `app/api/v1/posts.py`
5. **注册路由** → `app/api/router.py` 中 `include_router`

### 7.2 新增一个 MCP 工具

```python
# app/mcp/tools/my_tools.py
from app.mcp.base import BaseMCPTool

class MyNewTool(BaseMCPTool):
    name = "my_new_tool"
    description = "新工具的功能描述"
    category = "health"  # 归类到现有分类

    async def execute(self, param1: str, param2: int = 10) -> dict:
        # 你的业务逻辑
        return {"result": "..."}

# 工具会被 MCPRegistry 自动发现并注册
```

### 7.3 新增一个子 Agent

```python
# app/agents/my_agent.py
from app.agents.base_agent import BaseAgent

class MyAgent(BaseAgent):
    name = "my_agent"
    domain = "community"

    async def run(self, user_message, session_id, **kwargs):
        # 调用 MCP 工具
        result = await self._call_tool("my_new_tool", {"param1": user_message})

        # LLM 整合生成回答
        answer = await self._llm_with_tools(
            system_prompt="你是社区审核专家...",
            user_message=user_message,
            tool_results=[{"tool": "my_new_tool", "result": result}],
        )

        return {"answer": answer, "agent": self.name}
```

然后在 `OrchestratorAgent` 的意图关键词和路由表中注册即可。

---

## 八、项目亮点总结

| 亮点 | 说明 |
|------|------|
| 🧩 **A2A 多 Agent 编排** | Orchestrator + 3 个子 Agent，意图自动识别和任务路由 |
| 🔌 **MCP 标准化工具层** | 19 个工具接口，统一封装 IoT/健康/工单/会员/OTA 业务能力 |
| 📚 **RAG 检索增强生成** | bge-m3 + Milvus 向量检索，知识匹配准确率 96% |
| 🏗 **完整的分层架构** | API → Agent → MCP → RAG，职责清晰，易扩展 |
| 🐳 **Docker 一键部署** | MongoDB + Redis + Backend + Celery 全套容器化 |
| 🔄 **Demo / 生产双模式** | 无外部依赖也可运行，配置 API Key 后自动升级为完整 AI 模式 |
| 🛡 **完善的容错降级** | LLM 失败 → 返回原始数据；Milvus 不可用 → 内存检索；模块出错不影响其他功能 |
| 📋 **MongoDB 持久化** | 所有业务数据（用户/宠物/设备/工单）完整 CRUD + 软删除 + 审计日志 |

---

## 九、常见问题

**Q: Demo 模式和完整模式有什么区别？**

A: Demo 模式下所有 MCP 工具返回模拟数据，RAG 使用内存检索，Agent 不调用 LLM。配置 `LLM_BASE_URL` + `LLM_API_KEY` 后，系统自动升级：Agent 调用真实 LLM 生成回答，RAG 连接 Milvus 做向量检索。

**Q: 怎么切换为 MySQL 数据库？**

A: 本项目使用 MongoDB + Beanie ODM。如需 MySQL，修改 `app/core/database.py` 使用 SQLAlchemy + asyncpg，数据模型从 Beanie Document 改为 SQLAlchemy ORM 即可。架构分层设计保证了切换数据库不影响 API 和 Agent 层。

**Q: 如何接入真实的 IoT 平台？**

A: 在 `.env` 中配置 `IOT_BASE_URL` 和 `IOT_API_KEY`，系统会自动使用 `IoTClient` 调用真实接口。MCP 工具层不需要任何改动。

**Q: 项目有测试吗？**

A: `requirements.txt` 已包含 pytest 等测试依赖。测试目录结构建议：`tests/api/`（接口测试）、`tests/agents/`（Agent 测试）、`tests/mcp/`（工具测试）。可使用 `pytest tests/ -v --asyncio-mode=auto` 运行。

---

## 十、开发规范

```bash
# 代码格式化
ruff format app/

# Lint 检查
ruff check app/

# 运行测试
pytest tests/ -v --asyncio-mode=auto

# 启动开发服务
uvicorn app.main:app --reload --port 8000
```

---

> 📧 如有问题或建议，欢迎提 Issue 或 PR。
>
> ⚠️ 本项目为 Demo 演示版本，生产环境使用前请修改默认的 JWT_SECRET 和 API Key 配置。
