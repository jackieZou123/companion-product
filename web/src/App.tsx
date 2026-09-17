import { FormEvent, useEffect, useRef, useState } from "react";
import brandLogo from "./assets/brand-logo.png";
import {
  api,
  clearCurrentId,
  loadAdult,
  loadCurrentId,
  loadUserId,
  readSse,
  saveAdult,
  saveCurrentId,
  type ChatMessage,
  type Conversation,
  type Thread,
} from "./api";

export default function App() {
  const userId = useRef(loadUserId()).current;
  const [open, setOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [adult, setAdult] = useState(loadAdult);
  const [checked, setChecked] = useState(false);
  const [conversationId, setConversationId] = useState(loadCurrentId);
  const [disclosure, setDisclosure] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const listRef = useRef<HTMLOListElement>(null);

  async function openConversation(id: string) {
    const data = await api<Conversation>(userId, `/v1/conversations/${id}`);
    setConversationId(id);
    saveCurrentId(id);
    setDisclosure(data.ai_disclosure || "");
    setMessages(data.messages);
  }

  async function ensureConversation() {
    const items = await api<Thread[]>(userId, "/v1/conversations");
    if (items[0]) {
      await openConversation(items[0].conversation_id);
      return;
    }
    const data = await api<Conversation>(userId, "/v1/conversations", {
      method: "POST",
      body: JSON.stringify({
        adult_confirmed: true,
        character_id: "mei_li_kou",
      }),
    });
    await openConversation(data.conversation_id);
  }

  async function boot() {
    const ready = await fetch("/readyz");
    if (!ready.ok) setStatus("模型还没接上。过一会儿再试。");
    await ensureConversation();
  }

  useEffect(() => {
    if (!adult) return;
    boot().catch((error: Error) => setStatus(error.message));
  }, [adult]);

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
    setMenuOpen(false);
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
    setMenuOpen(false);
    try {
      await api(userId, "/v1/me", { method: "DELETE" });
      clearCurrentId();
      setConversationId("");
      setMessages([]);
      setDisclosure("");
      setStatus("");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "暂时接不上。");
    }
  }

  function collapse() {
    setOpen(false);
    setMenuOpen(false);
  }

  function widgetBody() {
    if (!adult) {
      return (
        <div className="widget-gate">
          <BrandMark invert />
          <h1 className="sr-only">玫莉蔻</h1>
          <p className="gate-copy">
            皮肤问答专家。懂肤质、屏障和护理里那些烦，陪你把皮肤的事说清楚。这是 AI 陪伴，不是真人，也不会上门。
          </p>
          <label className="check">
            <input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
            <span>我已满 18 岁，以成年人身份来聊天</span>
          </label>
          <button
            type="button"
            disabled={!checked}
            onClick={() => {
              saveAdult();
              setAdult(true);
            }}
          >
            进入
          </button>
        </div>
      );
    }
    return (
      <>
        <div className="widget-body">
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
        </div>
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
      </>
    );
  }

  return (
    <div className="desktop">
      {open ? (
        <section className="widget" aria-label="玫莉蔻对话">
          <header className="widget-top">
            <div className="widget-heading">
              <h2>
                <BrandMark compact />
              </h2>
              {disclosure ? <p className="disclosure">{disclosure}</p> : null}
            </div>
            <div className="widget-actions">
              {adult ? (
                <div className="menu-wrap">
                  <button
                    className="icon-btn"
                    type="button"
                    aria-label="更多"
                    aria-expanded={menuOpen}
                    onClick={() => setMenuOpen((current) => !current)}
                  >
                    ⋯
                  </button>
                  {menuOpen ? (
                    <div className="menu">
                      <button className="text-btn" type="button" onClick={exportData}>
                        导出我的记录
                      </button>
                      <button className="text-btn danger" type="button" onClick={wipeData}>
                        清空本地数据
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <button className="icon-btn" type="button" aria-label="收起对话" onClick={collapse}>
                –
              </button>
            </div>
          </header>
          {widgetBody()}
        </section>
      ) : (
        <button
          className="fab"
          type="button"
          aria-label="打开玫莉蔻"
          onClick={() => {
            setMenuOpen(false);
            setOpen(true);
          }}
        >
          <img className="fab-logo" src={brandLogo} alt="" />
        </button>
      )}
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
