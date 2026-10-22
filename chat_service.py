"""Agent 服务：LangChain ReAct 调度 + 会话持久化 + 上下文注入 + SSE 流式。

- 会话历史存储在 MySQL（sessions / session_messages），重启不丢
- 每轮注入规则抽取的“已知上下文”（城市/日期/意图）+ 最近历史消息
- run_chat：同步调用（兼容旧接口）；run_chat_stream：SSE 流式（工具实时 + 回复打字机）
- 容错：LLM 瞬态异常重试 1 次，仍失败返回兜底回复并保证用户消息落库
"""

import asyncio
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent as create_agent

from a2a_server.trip_server import TOOLS as TRIP_TOOLS
from a2a_server.ticket_server import TOOLS as TICKET_TOOLS
from a2a_server.weather_server import TOOLS as WEATHER_TOOLS
from config import Config
from main_prompts import CONTEXT_TEMPLATE, SYSTEM_PROMPT
from memory import ContextExtractor, SessionStore, format_context
from utils.tool_parser import to_langchain_tool

conf = Config()

# 简单转换：把服务模块中的普通函数统一转换为 LangChain 工具
SERVICE_TOOLS = WEATHER_TOOLS + TICKET_TOOLS + TRIP_TOOLS
ALL_TOOLS = [to_langchain_tool(fn) for fn in SERVICE_TOOLS]

HISTORY_LIMIT = 20
RECURSION_LIMIT = 15
FALLBACK_REPLY = "抱歉，服务暂时不可用，请稍后再试。"

store = SessionStore()
extractor = ContextExtractor()


def build_agent():
    """构建 ReAct 智能体（模型 + 工具 + 系统提示词）。"""
    model = ChatOpenAI(
        base_url=conf.base_url,
        api_key=conf.api_key,
        model=conf.model_name,
        temperature=conf.temperature,
        timeout=60,
        max_retries=1,
    )
    return create_agent(model=model, tools=ALL_TOOLS, prompt=SYSTEM_PROMPT)


_agent = None


def get_agent():
    """获取全局单例 Agent。"""
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


def _build_messages(session_id: str, message: str) -> List:
    """构造本轮输入：已知上下文 + DB 历史(最近 N 条) + 当前用户消息。"""
    history = store.load_messages(session_id, limit=HISTORY_LIMIT)
    ctx = extractor.extract_from_history(history, message)

    msgs: List = []
    ctx_text = format_context(ctx)
    if ctx_text:
        msgs.append(SystemMessage(content=CONTEXT_TEMPLATE.format(context=ctx_text)))
    for h in history:
        role, content = h["role"], h["content"]
        if role == "user":
            msgs.append(HumanMessage(content=content))
        else:
            msgs.append(AIMessage(content=content))
    msgs.append(HumanMessage(content=message))
    return msgs


def _extract_steps(messages: List[Any], start: int = 0) -> List[Dict[str, Any]]:
    """从消息序列中提取工具调用轨迹（工具名/入参/结果）。"""
    pending: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for msg in messages[start:]:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for call in msg.tool_calls:
                call_id = call.get("id")
                pending[call_id] = {
                    "tool": call.get("name", ""),
                    "args": call.get("args", {}),
                    "result": "",
                }
                order.append(call_id)
        elif isinstance(msg, ToolMessage):
            call_id = getattr(msg, "tool_call_id", None)
            if call_id in pending:
                pending[call_id]["result"] = str(msg.content)
    return [pending[cid] for cid in order if cid in pending]


def _persist_turn(session_id: str, message: str, reply: str, steps: list) -> None:
    """保存本轮用户消息与助手回复。"""
    store.append_message(session_id, "user", message)
    store.append_message(session_id, "assistant", reply, steps=steps)


def _invoke_with_retry(msgs: List) -> Any:
    """调用 Agent；LLM 瞬态异常重试 1 次。"""
    agent = get_agent()
    config = {"recursion_limit": RECURSION_LIMIT}
    try:
        return agent.invoke({"messages": msgs}, config=config)
    except Exception:
        return agent.invoke({"messages": msgs}, config=config)


def run_chat(session_id: str, message: str) -> Dict[str, Any]:
    """执行一次对话（同步），返回 {"reply", "steps"}，历史落库。"""
    session_id = session_id or "default"
    store.ensure_session(session_id, message)
    msgs = _build_messages(session_id, message)
    try:
        result = _invoke_with_retry(msgs)
        result_messages = result.get("messages", []) if isinstance(result, dict) else []
        reply = str(result_messages[-1].content) if result_messages else ""
        # 新产生的消息从“系统提示词 + 本轮输入”之后开始
        start = len(msgs) + 1
        steps = _extract_steps(result_messages, start=start)
        if not steps:
            steps = _extract_steps(result_messages, start=0)
    except Exception:  # noqa: BLE001
        reply, steps = FALLBACK_REPLY, []
    _persist_turn(session_id, message, reply, steps)
    return {"reply": reply, "steps": steps}


async def run_chat_stream(session_id: str, message: str):
    """SSE 流式对话：依次产出 tool_start / tool_end / content / done 事件。"""
    session_id = session_id or "default"
    store.ensure_session(session_id, message)
    msgs = _build_messages(session_id, message)
    yield {"type": "session", "session_id": session_id}

    pending: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    reply_parts: List[str] = []
    fallback = None

    agent = get_agent()
    try:
        async for evt in agent.astream_events(
            {"messages": msgs},
            config={"recursion_limit": RECURSION_LIMIT},
            version="v2",
        ):
            kind = evt.get("event")
            if kind == "on_chat_model_stream":
                chunk = evt.get("data", {}).get("chunk")
                delta = getattr(chunk, "content", None)
                if delta:
                    reply_parts.append(str(delta))
                    yield {"type": "content", "delta": str(delta)}
            elif kind == "on_tool_start":
                run_id = evt.get("run_id")
                name = evt.get("name") or "tool"
                args = evt.get("data", {}).get("input") or {}
                pending[run_id] = {"tool": name, "args": args, "result": ""}
                order.append(run_id)
                yield {"type": "tool_start", "tool": name, "args": args}
            elif kind == "on_tool_end":
                run_id = evt.get("run_id")
                output = evt.get("data", {}).get("output")
                text = str(output) if output is not None else ""
                if run_id not in pending:
                    pending[run_id] = {"tool": evt.get("name") or "tool",
                                       "args": {}, "result": ""}
                    order.append(run_id)
                pending[run_id]["result"] = text
                yield {"type": "tool_end", "tool": pending[run_id]["tool"],
                       "result": text}
    except Exception:  # noqa: BLE001
        fallback = FALLBACK_REPLY
        yield {"type": "error", "message": fallback}
    finally:
        reply = "".join(reply_parts) or fallback or ""
        steps = [pending[cid] for cid in order if cid in pending]
        _persist_turn(session_id, message, reply, steps)
        yield {"type": "done", "reply": reply, "steps": steps}


# 兼容旧调用方（如需要同步等待流式结果）
def run_chat_async(session_id: str, message: str) -> Dict[str, Any]:
    """异步流式结果的同步封装（测试/兼容用）。"""
    events = []

    async def _collect():
        async for evt in run_chat_stream(session_id, message):
            events.append(evt)

    asyncio.run(_collect())
    done = next((e for e in reversed(events) if e["type"] == "done"), None)
    return {"reply": done["reply"] if done else FALLBACK_REPLY,
            "steps": done["steps"] if done else []}