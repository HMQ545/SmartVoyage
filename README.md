# SmartVoyage 旅游智能体

SmartVoyage 是一个面向旅行场景的 AI 助手。用户可以用自然语言查询天气、机票、火车票、演唱会门票、租车、旅行团和保险，并在同一会话中持续补充需求。

项目采用 FastAPI 提供 Web 服务，使用 LangGraph ReAct Agent 完成意图理解与工具调度，通过 A2A 服务层和 MCP 服务连接业务工具，并使用 MySQL 保存会话记录。

## 功能

- 天气查询：查询指定城市的实时天气或未来天气
- 票务服务：查询和预订机票、火车票、演唱会门票
- 旅行服务：查询和预订租车、旅行团、旅行保险
- 多轮会话：保存会话历史，并结合上下文补全城市、日期等信息
- 流式响应：通过 SSE 实时返回回答和工具调用步骤
- 会话管理：支持新建、加载和删除历史会话
- 工具解耦：A2A 服务层与 MCP 服务层分离，便于独立扩展业务能力

## 系统架构

```text
浏览器
  │
  ▼
FastAPI Web 服务
  │
  ▼
LangGraph ReAct Agent
  │
  ├── 天气 A2A 服务 ──┐
  ├── 票务 A2A 服务 ──┼── MCP 工具服务
  └── 旅行 A2A 服务 ──┘
                         │
                         ├── MySQL
                         ├── 和风天气 API
                         └── Milvus
```

## 技术栈

- Web 与 API：FastAPI、Uvicorn
- 智能体：LangGraph、LangChain
- 工具协议：MCP、A2A
- 模型服务：DeepSeek、OpenAI 兼容接口
- 数据存储：MySQL
- 向量检索：Milvus、DashScope Embedding
- 前端：原生 HTML、CSS、JavaScript

## 快速开始

### 1. 环境要求

- Python 3.10+
- MySQL
- 可用的模型 API Key

### 2. 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS 或 Linux 使用：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 3. 配置

根据 `.env.example` 填写所需配置。主要环境变量包括：

- `DEEPSEEK_API_KEY`：模型服务配置
- `QWEATHER_API_KEY`：和风天气服务配置
- `DASHSCOPE_API_KEY`：Embedding 服务配置
- `MYSQL_*`：MySQL 连接配置

`.env` 包含私人配置，不应提交到版本库。

### 4. 初始化数据库

创建 `travel_rag` 数据库并配置连接后，执行：

```bash
python script/init_session_tables.py
python script/init_ticket_mock_data.py
python script/init_trip_mock_data.py
```

需要旅行团向量检索时，可继续执行：

```bash
python script/init_tour_group_rag.py
```

### 5. 启动

```bash
python main.py
```

访问 <http://127.0.0.1:8000>。更详细的环境准备和问题排查见[启动文档](docs/启动文档.md)。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/chat` | 同步聊天 |
| `POST` | `/api/chat/stream` | SSE 流式聊天 |
| `GET` | `/api/sessions` | 获取会话列表 |
| `GET` | `/api/sessions/{session_id}` | 获取会话详情 |
| `DELETE` | `/api/sessions/{session_id}` | 删除会话 |

## 项目结构

```text
.
├── api_server.py       # FastAPI 入口与 API
├── chat_service.py     # 智能体、消息处理与响应流
├── memory.py           # 会话持久化与上下文提取
├── main_prompts.py     # 系统提示词
├── a2a_server/         # A2A 业务服务层
├── mcp_server/         # MCP 工具服务
├── static/             # Web 前端
├── script/             # 数据库与示例数据初始化脚本
└── docs/               # 项目文档
```

## 安全说明

- 不要提交 `.env`、API Key、数据库密码或其他私人配置。
- 示例数据仅用于本地开发和功能演示。
- 生产环境应使用独立的凭据管理方式，并开启必要的访问控制。
