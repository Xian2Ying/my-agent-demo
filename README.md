# My Agent · 我的专属智能体

用 **React + Vite（前端）+ Python FastAPI（后端）** 从零搭建的专属 AI Agent。
前端负责聊天界面，后端负责「人设 + 工具调用 + 大模型推理」，回答全程流式输出。

## 技术架构

```
浏览器页面 (React + Vite, :5173)
      │  fetch('/api/chat', SSE 流)
      ▼
FastAPI 后端 (:8000)
      │  ① 决策：是否调用工具？
      │  ② 循环执行工具（获取时间 / 计算器）
      │  ③ 流式吐回答
      ▼
豆包大模型 API（火山方舟）  ← 未配 Key 时自动走 Mock 模式
```

## 目录结构

```
my-agent/
├── backend/
│   ├── main.py          # FastAPI 服务 + SSE 流式接口
│   ├── agent.py         # Agent 核心：人设 / 工具调用循环 / 豆包接入 / Mock
│   ├── requirements.txt # Python 依赖
│   └── .env.example     # 配置模板（复制为 .env）
└── frontend/
    ├── package.json     # 前端依赖
    ├── vite.config.js   # 含 /api 代理 → 后端
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx      # 聊天界面 + SSE 流式解析
        └── index.css
```

## 快速开始（两条命令跑起来）

先启动后端：

```bash
cd backend
pip install -r requirements.txt
python main.py            # 监听 http://localhost:8000
```

再开一个终端启动前端：

```bash
cd frontend
npm install
npm run dev               # 打开 http://localhost:5173
```

> 小坑：如果项目所在路径里含 `&` 字符（例如放在 `C:\Users\XIAN&YING\...` 下），
> `npm run dev` 会被 cmd 误解析而报错，改用下面这条命令直接启动：
> `node node_modules\vite\bin\vite.js`

没配 API Key 也能玩：后端会自动进入 **Mock 演示模式**，可以看到
「工具调用 → 流式回答」完整流程。

## 接入真实大模型（豆包，免费额度友好）

1. 打开火山方舟控制台：https://console.volcengine.com/ark
2. 左侧「API Key 管理」→ 创建 API Key
3. 左侧「在线推理」→ 创建推理接入点，记下接入点 ID（形如 `ep-2026xxxxxxxx`）
4. 复制 `backend/.env.example` 为 `backend/.env`，填入：

```ini
ARK_API_KEY=你的_API_Key
ARK_MODEL=你的接入点ID  # 或直接填模型名，如 doubao-seed-1-8-251228
```

5. 重启后端 `python main.py`，刷新页面即可。API Key 只存在 `.env` 里，不会泄漏到前端。

## 改成「你自己的」Agent

所有个性化都在 `backend/agent.py` 顶部：

- **人设**：改 `SYSTEM_PROMPT`，让它叫你的名字、按你的性格说话
- **工具**：在 `TOOLS` 里加一个 JSON 描述，再在 `execute_tool()` 里写实现，模型就会自动学会在需要时调用它

## 下一步可以玩什么

- 给 Agent 加「搜索网页」「查天气」等新工具
- 加多轮记忆（把历史消息存进数据库，重启不丢）
- 加语音输入 / 输出（豆包语音大模型）
- 部署上线（前端 `npm run build` 后交给 Nginx/静态托管，后端用 uvicorn 跑在服务器）
