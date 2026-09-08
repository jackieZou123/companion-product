import { FormEvent, useEffect, useRef, useState } from "react";
import brandLogo from "./assets/brand-logo.png";
import {
  api,
  clearCurrentId,
  clearGender,
  loadAdult,
  loadCurrentId,
  loadGender,
  loadUserId,
  readSse,
  saveAdult,
  saveCurrentId,
  saveGender,
  type ChatMessage,
  type Conversation,
  type Thread,
  type UserGender,
} from "./api";

export default function App() {
  const userId = useRef(loadUserId()).current;
  const [adult, setAdult] = useState(loadAdult);
  const [gender, setGender] = useState<UserGender | "">(loadGender);
  const [checked, setChecked] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [conversationId, setConversationId] = useState(loadCurrentId);
  const [disclosure, setDisclosure] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const listRef = useRef<HTMLOListElement>(null);

  async function refreshThreads() {
    const items = await api<Thread[]>(userId, "/v1/conversations");
    setThreads(items);
  }

  async function openConversation(id: string) {
    const data = await api<Conversation>(userId, `/v1/conversations/${id}`);
    setConversationId(id);
    saveCurrentId(id);
    setDisclosure(data.ai_disclosure || "");
    setMessages(data.messages);
    await refreshThreads();
  }

  async function createConversation(nextGender: UserGender = gender || "female") {
    const data = await api<Conversation>(userId, "/v1/conversations", {
      method: "POST",
      body: JSON.stringify({
        adult_confirmed: true,
        character_id: "mei_li_kou",
        gender: nextGender,
      }),
    });
    await openConversation(data.conversation_id);
  }

  async function boot() {
    const ready = await fetch("/readyz");
    if (!ready.ok) setStatus("模型还没接上。过一会儿再试。");
    const items = await api<Thread[]>(userId, "/v1/conversations");
    if (conversationId && items.some((item) => item.conversation_id === conversationId)) {
      await openConversation(conversationId);
      return;
    }
    if (items[0]) {
      await openConversation(items[0].conversation_id);
      return;
    }
    await createConversation();
  }

  useEffect(() => {
    if (!adult || !gender) return;
    boot().catch((error: Error) => setStatus(error.message));
  }, [adult, gender]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function sendTurn(text: string) {
    let activeId = conversationId;
    if (!activeId) {
      const created = await api<Conversation>(userId, "/v1/conversations", {
        method: "POST",
        body: JSON.stringify({
          adult_confirmed: true,
          character_id: "mei_li_kou",
          gender: gender || "female",
        }),
      });
      activeId = created.conversation_id;
      setConversationId(activeId);
      saveCurrentId(activeId);
      setDisclosure(created.ai_disclosure || "");
    }
    setMessages((current) => [...current, { role: "user", content: text }, { role: "assistant", content: "" }]);
    setStatus("玫莉蔻正在回复…");
    const response = await fetch(`/v1/conversations/${activeId}/turns/stream`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "X-User-Id": userId,
      },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      setMessages((current) => patchLastAssistant(current, "暂时接不上。请再说一遍。"));
      setStatus("");
      return;
    }
    await readSse(response, (event, data) => {
      if (event === "token" && typeof data.text === "string") {
        setMessages((current) => patchLastAssistant(current, `${lastAssistant(current)}${data.text}`));
      }
      if (event === "review" && data.code === "output_blocked") {
        setMessages((current) => patchLastAssistant(current, ""));
      }
      if (event === "done") {
        if (typeof data.assistant_text === "string") {
          setMessages((current) => patchLastAssistant(current, data.assistant_text as string));
        }
        setStatus(data.degraded ? "回复慢了一些，请先看这一句。" : "");
      }
      if (event === "error") {
        setMessages((current) =>
          patchLastAssistant(current, typeof data.detail === "string" ? data.detail : "暂时接不上。"),
        );
        setStatus("");
      }
    });
    await refreshThreads();
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setBusy(true);
    setDraft("");
    try {
      await sendTurn(text);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "暂时接不上。");
    } finally {
      setBusy(false);
    }
  }

  async function exportData() {
    try {
      const data = await api<unknown>(userId, "/v1/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "companion-export.json";
      link.click();
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "暂时接不上。");
    }
  }

  async function wipeData() {
    if (!window.confirm("把这个浏览器里的对话都清掉？清了就回不来。")) return;
    try {
      await api(userId, "/v1/me", { method: "DELETE" });
      clearCurrentId();
      clearGender();
      setGender("");
      setConversationId("");
      setMessages([]);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "暂时接不上。");
    }
  }

  if (!adult) {
    return (
      <div className="gate">
        <div className="gate-card">
          <BrandMark invert />
          <h1 className="sr-only">玫莉蔻</h1>
          <p className="gate-copy">
            皮肤问答专家。懂肤质、屏障和护理里那些烦，陪你把皮肤的事说清楚。这是 AI 陪伴，不是真人，也不会上门。
          </p>
          <label className="check">
            <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
            <span>我已满 18 岁，以成年人身份来聊天</span>
          </label>
          <button type="button" disabled={!checked} onClick={() => { saveAdult(); setAdult(true); }}>
            进入
          </button>
        </div>
      </div>
    );
  }

  if (!gender) {
    return (
      <div className="gate">
        <div className="gate-card">
          <BrandMark invert />
          <h1 className="sr-only">玫莉蔻</h1>
          <p className="gate-copy">开始之前请选择性别。之后会按这个称呼你：女性称姐姐，男性称哥哥。</p>
          <div className="gender-choices">
            <button
              type="button"
              onClick={() => {
                saveGender("female");
                setGender("female");
              }}
            >
              我是女性
            </button>
            <button
              type="button"
              onClick={() => {
                saveGender("male");
                setGender("male");
              }}
            >
              我是男性
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="shell">
      <aside className={railOpen ? "rail open" : "rail"}>
        <div className="brand">
          <BrandMark />
        </div>
        <button className="ghost" type="button" onClick={() => createConversation().catch((error: Error) => setStatus(error.message))}>
          新对话
        </button>
        <ul className="threads">
          {threads.map((item) => (
            <li key={item.conversation_id}>
              <button
                type="button"
                className={item.conversation_id === conversationId ? "active" : ""}
                onClick={() => openConversation(item.conversation_id).catch((error: Error) => setStatus(error.message))}
              >
                <span>和玫莉蔻</span>
                <span className="thread-meta">{item.message_count} 句</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="rail-foot">
          <button className="text-btn" type="button" onClick={exportData}>
            导出我的记录
          </button>
          <button className="text-btn danger" type="button" onClick={wipeData}>
            清空本地数据
          </button>
        </div>
      </aside>

      <main className="stage">
        <header className="top">
          <button className="icon-btn" type="button" aria-label="会话列表" onClick={() => setRailOpen((open) => !open)}>
            ☰
          </button>
          <div>
            <h2>
              <BrandMark compact />
            </h2>
            <p className="disclosure">{disclosure}</p>
          </div>
        </header>

        <ol className="messages" aria-live="polite" ref={listRef}>
          {messages.length === 0 ? (
            <li className="msg empty">皮肤上的烦，可以直接说。也可以先喊一声玫莉蔻。</li>
          ) : (
            messages.map((item, index) => (
              <li key={`${item.role}-${index}`} className={`msg ${item.role}`}>
                {item.content}
              </li>
            ))
          )}
        </ol>

        {status ? <p className="status">{status}</p> : null}

        <form className="composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="draft">
            说点什么
          </label>
          <textarea
            id="draft"
            rows={2}
            maxLength={4000}
            value={draft}
            placeholder="喊一声玫莉蔻，或说说皮肤最近怎么了"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button type="submit" disabled={busy}>
            发送
          </button>
        </form>
      </main>
    </div>
  );
}

function BrandMark({ invert = false, compact = false }: { invert?: boolean; compact?: boolean }) {
  const className = ["brand-logo", invert ? "invert" : "", compact ? "compact" : ""]
    .filter(Boolean)
    .join(" ");
  return <img className={className} src={brandLogo} alt="玫莉蔻" />;
}

function lastAssistant(messages: ChatMessage[]): string {
  const last = messages[messages.length - 1];
  return last?.role === "assistant" ? last.content : "";
}

function patchLastAssistant(messages: ChatMessage[], content: string): ChatMessage[] {
  if (!messages.length) return [{ role: "assistant", content }];
  const next = [...messages];
  const last = next[next.length - 1];
  if (last.role !== "assistant") return [...next, { role: "assistant", content }];
  next[next.length - 1] = { role: "assistant", content };
  return next;
}
