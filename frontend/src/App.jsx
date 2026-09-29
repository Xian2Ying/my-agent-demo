import { useEffect, useRef, useState } from 'react'

// 工具名称 → 展示用中文名
const TOOL_NAMES = {
  get_current_time: '获取当前时间',
  calculator: '计算器',
}

export default function App() {
  const [messages, setMessages] = useState([]) // [{role:'user'|'assistant', content}]
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false) // 是否正在回复
  const [tool, setTool] = useState(null) // 当前正在调用的工具
  const [thinking, setThinking] = useState(false) // 模型思考中（尚未吐出内容）
  const bottomRef = useRef(null)

  // 新消息时自动滚到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, tool, thinking])

  async function send() {
    const text = input.trim()
    if (!text || streaming) return
    setInput('')
    setTool(null)
    setThinking(true)

    // 历史消息 + 当前提问
    const history = [...messages, { role: 'user', content: text }]
    setMessages([...history, { role: 'assistant', content: '' }])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
      })
      if (!res.ok || !res.body) throw new Error(`请求失败（HTTP ${res.status}）`)

      // —— 读取 SSE 流 ——
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let acc = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })

        // SSE 事件以空行分隔，每条形如：data: {json}
        const events = buf.split('\n\n')
        buf = events.pop() // 最后一段可能不完整，留到下一轮
        for (const ev of events) {
          if (!ev.startsWith('data: ')) continue
          let data
          try {
            data = JSON.parse(ev.slice(6))
          } catch {
            continue
          }
          if (data.type === 'tool') {
            setThinking(false)
            setTool(data.name)
          } else if (data.type === 'delta') {
            setThinking(false)
            setTool(null)
            acc += data.content
            // 更新最后一个 assistant 气泡
            setMessages((prev) => {
              const next = [...prev]
              next[next.length - 1] = { role: 'assistant', content: acc }
              return next
            })
          } else if (data.type === 'done') {
            break
          }
        }
      }

      setTool(null)
      setThinking(false)
      setStreaming(false)
      setMessages((prev) => {
        const next = [...prev]
        if (next[next.length - 1].role === 'assistant' && !next[next.length - 1].content) {
          next[next.length - 1] = { role: 'assistant', content: '（没有返回内容）' }
        }
        return next
      })
    } catch (err) {
      setTool(null)
      setThinking(false)
      setStreaming(false)
      setMessages((prev) => [...prev, { role: 'assistant', content: `出错了：${err.message}` }])
    }
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="app">
      <header className="header">
        <span className="logo">◆</span>
        <span className="title">My Agent · 我的专属智能体 - Hello</span>
        <span className="status">已连接</span>
      </header>

      <main className="chat">
        {messages.length === 0 && (
          <div className="empty">
            <div className="empty-title">你好，我是你的专属智能体</div>
            <div className="empty-sub">
              试试问我「现在几点」或「128×0.75 等于多少」——我会调用工具来回答
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            <div className="bubble">{m.content}</div>
          </div>
        ))}

        {thinking && (
          <div className="row assistant">
            <div className="bubble status-bubble">思考中…</div>
          </div>
        )}

        {tool && (
          <div className="row assistant">
            <div className="tool-chip">
              <span className="tool-spin">⟳</span>
              <span>正在调用工具：{TOOL_NAMES[tool] || tool}</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      <footer className="input-bar">
        <textarea
          className="input"
          rows={1}
          placeholder="输入消息，Enter 发送（Shift+Enter 换行）"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button className="send" onClick={send} disabled={streaming || !input.trim()}>
          {streaming ? '…' : '发送'}
        </button>
      </footer>
    </div>
  )
}
