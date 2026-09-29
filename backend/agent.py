# -*- coding: utf-8 -*-
"""
你的专属 Agent 核心。
负责三件事：
1. 人设（SYSTEM_PROMPT，可自定义）
2. 工具调用循环（让大模型决定何时调用工具、执行工具、再回答）
3. 接入豆包大模型（火山方舟），并把回答流式吐给前端
未配置 API Key 时自动进入 Mock 模式，方便先把界面跑通。
"""

import ast
import html
import json
import operator
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ---------------- 配置 ----------------
ARK_API_KEY = os.getenv("ARK_API_KEY", "").strip()
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seed-1-8-251228").strip()
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").strip()

# 你的 Agent 人设：想让它叫什么、是什么性格、擅长什么，改这里就行
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "你是一个名叫「小晚」的智能助手，由我亲手打造。你性格友善、说话简洁、用中文交流。"
    "遇到需要实时信息（时间日期）或数学计算的问题时，你会主动调用工具来获得准确结果，"
    "而不是凭空猜测。",
)

MAX_TOOL_ROUNDS = 3  # 最多连续调用几轮工具

# ---------------- 工具定义（OpenAI Function Calling 格式）----------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的日期和时间。当用户问「现在几点」「今天几号」「几点了」时使用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "执行数学计算。当用户给出算式或需要算数时使用，如「300+250*0.8」。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "合法的数学表达式，例如 300+250*0.8",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市当前及今天的天气、气温。当用户问「XX天气」「XX最高气温」「今天冷不冷」时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，例如 高州、广州、北京",
                    }
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "联网搜索最新信息。当用户问新闻、最新消息、事件、人物或任何需要实时数据的问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如 高州 今天 最高气温",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# ---------------- 工具实现 ----------------
def _safe_calc(expression: str) -> float:
    """用 AST 白名单方式安全计算表达式，杜绝 eval 注入。"""
    tree = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
        ast.USub, ast.UAdd,
    )
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError("表达式包含不支持的内容")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("表达式包含不支持的内容")
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return ops[type(node.op)](_eval(node.operand))
        raise ValueError("无法计算的表达式")
    return _eval(tree.body)


def _get_weather(city: str) -> str:
    """用 wttr.in 查天气（免费、无需 Key、支持中文城市名）。"""
    url = "https://wttr.in/" + urllib.parse.quote(city) + "?format=j1&lang=zh"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        data = json.loads(r.read().decode("utf-8"))
    cur = data["current_condition"][0]
    today = data["weather"][0]
    desc = ""
    if cur.get("lang_zh"):
        desc = cur["lang_zh"][0]["value"]
    elif cur.get("weatherDesc"):
        desc = cur["weatherDesc"][0]["value"]
    return json.dumps({
        "city": city,
        "当前天气": desc,
        "当前温度": cur["temp_C"] + "℃",
        "今天最高气温": today["maxtempC"] + "℃",
        "今天最低气温": today["mintempC"] + "℃",
    }, ensure_ascii=False)


def _web_search(query: str, n: int = 5) -> str:
    """用必应国内版抓取搜索结果（免费、无需 Key）。"""
    url = "https://cn.bing.com/search?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    with urllib.request.urlopen(req, timeout=12) as r:
        page = r.read().decode("utf-8", errors="ignore")
    items = []
    blocks = re.findall(r'<li class="b_algo".*?</li>', page, re.S)
    for b in blocks[:n]:
        m = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        link = m.group(1)
        title = re.sub(r"<[^>]+>", "", m.group(2))
        p = re.search(r"<p[^>]*>(.*?)</p>", b, re.S)
        snippet = re.sub(r"<[^>]+>", "", p.group(1)) if p else ""
        items.append({
            "title": html.unescape(title).strip(),
            "url": link,
            "snippet": html.unescape(snippet).strip()[:200],
        })
    return json.dumps(items, ensure_ascii=False)


def execute_tool(name: str, args: dict) -> str:
    """真正执行工具，返回给模型的工具结果文本。"""
    try:
        if name == "get_current_time":
            now = datetime.now()
            return json.dumps({"time": now.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False)
        if name == "calculator":
            expression = (args.get("expression") or "").strip()
            if not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
                return json.dumps({"error": "表达式不合法"}, ensure_ascii=False)
            result = _safe_calc(expression)
            return json.dumps({"expression": expression, "result": result}, ensure_ascii=False)
        if name == "get_weather":
            return _get_weather(args.get("city") or "")
        if name == "web_search":
            return _web_search(args.get("query") or "")
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    return json.dumps({"error": "未知工具"}, ensure_ascii=False)


# ---------------- Agent 主体 ----------------
class Agent:
    def __init__(self):
        self.client = None
        if ARK_API_KEY:
            from openai import OpenAI  # 延迟导入，没 key 时不强制装 openai
            self.client = OpenAI(api_key=ARK_API_KEY, base_url=ARK_BASE_URL)

    @property
    def is_mock(self) -> bool:
        """没有 API Key 时为 True，走 Mock 演示流程。"""
        return self.client is None

    def chat_stream(self, messages: list[dict]):
        """
        接收前端传来的历史消息（list[dict]），yield 一个个 JSON 字符串事件：
          {"type": "tool",  "name": ..., "args": {...}}   调用了某个工具
          {"type": "delta", "content": "..."}              回答文本片段（流式）
        """
        if self.is_mock:
            yield from self._mock_stream(messages)
            return

        # 0) 拼上人设
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

        # 1) 决策轮：非流式调用，让模型决定是否要调用工具
        resp = self.client.chat.completions.create(
            model=ARK_MODEL, messages=msgs, tools=TOOLS, stream=False,
        )
        msg = resp.choices[0].message

        # 2) 工具调用循环
        for _ in range(MAX_TOOL_ROUNDS):
            calls = getattr(msg, "tool_calls", None)
            if not calls:
                break
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield json.dumps({"type": "tool", "name": c.function.name, "args": args}, ensure_ascii=False)
            msgs.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function",
                     "function": {"name": c.function.name, "arguments": c.function.arguments}}
                    for c in calls
                ],
            })
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = execute_tool(c.function.name, args)
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": result})
            resp = self.client.chat.completions.create(
                model=ARK_MODEL, messages=msgs, tools=TOOLS, stream=False,
            )
            msg = resp.choices[0].message

        # 3) 最终回答：真实流式吐给前端
        stream = self.client.chat.completions.create(
            model=ARK_MODEL, messages=msgs, stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield json.dumps({"type": "delta", "content": chunk.choices[0].delta.content}, ensure_ascii=False)

    def _mock_stream(self, messages: list[dict]):
        """Mock 模式：模拟一次工具调用 + 一段流式回答，让没有 Key 也能跑通全流程。"""
        yield json.dumps({"type": "tool", "name": "get_current_time", "args": {}}, ensure_ascii=False)
        time.sleep(0.4)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"（Mock 演示模式：还没配置 ARK_API_KEY）\n\n"
            f"你好呀！现在是 {now}。\n\n"
            f"我已经跑通「人设 → 工具调用 → 流式回答」的完整链路。"
            f"想要我接入真实大脑，去火山方舟控制台申请 API Key，"
            f"填进 backend/.env 再重启后端即可。步骤见 README.md。"
        )
        for i in range(0, len(text), 4):
            yield json.dumps({"type": "delta", "content": text[i:i + 4]}, ensure_ascii=False)
            time.sleep(0.02)
