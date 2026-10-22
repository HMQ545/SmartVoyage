"""工具解析模块：把服务中的普通函数转换为 LangChain 工具

对 LangChain 标准的“函数转工具”机制（StructuredTool.from_function / @tool）
做二次封装，统一处理：
- 工具名（默认取函数名，可覆盖）
- 工具描述（默认取 docstring，可覆盖）
- 参数 schema（通过类型注解 + docstring 中的 Args 说明自动生成）
- 异常兜底（默认把运行异常转成字符串返回，避免中断 Agent）
"""

import functools
import inspect
from typing import Any, Callable, List, Optional

from langchain_core.tools import BaseTool, StructuredTool


def to_langchain_tool(
    func: Callable,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    wrap_errors: bool = True,
) -> StructuredTool:
    """把一个普通 Python 函数转换成 LangChain 工具。

    Args:
        func: 服务模块中定义的普通函数，docstring 中需写明 Args 参数说明
        name: 可选，覆盖工具名，默认取函数名
        description: 可选，覆盖工具描述，默认取 docstring 首段
        wrap_errors: 为 True 时把运行异常包装成字符串返回，不中断 Agent

    Returns:
        可直接交给 create_agent(tools=[...]) 的 LangChain 工具
    """
    tool_name = name or func.__name__
    tool_description = description or (inspect.getdoc(func) or func.__name__)

    @functools.wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            if wrap_errors:
                return f"工具 {tool_name} 调用失败：{type(exc).__name__}: {exc}"
            raise

    return StructuredTool.from_function(
        func=_wrapped,
        name=tool_name,
        description=tool_description,
    )


def load_tools_from(*modules: Any, wrap_errors: bool = True) -> List[BaseTool]:
    """从多个服务模块中收集 TOOLS 列表并统一转换为 LangChain 工具。

    每个模块需导出 TOOLS（普通函数列表）。等价于：
    [to_langchain_tool(fn) for fn in 模块1.TOOLS + 模块2.TOOLS + ...]

    Args:
        modules: 服务模块对象（如 weather_server、ticket_server、trip_server）
        wrap_errors: 是否开启异常兜底

    Returns:
        LangChain 工具列表
    """
    tools: List[BaseTool] = []
    for module in modules:
        for func in getattr(module, "TOOLS", []):
            tools.append(to_langchain_tool(func, wrap_errors=wrap_errors))
    return tools