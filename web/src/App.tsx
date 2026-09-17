import { FormEvent, useEffect, useRef, useState } from "react";
import brandLogo from "./assets/brand-logo.png";
import {
  api,
  clearCurrentId,
  loadCurrentId,
  loadUserId,
  readSse,
  saveCurrentId,
  type ChatMessage,
  type Conversation,
  type Thread,
  type ActionProposal,
} from "./api";

export default function App() {
  const userId = useRef(loadUserId()).current;
  const [open, setOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [conversationId, setConversationId] = useState(loadCurrentId);
  const [disclosure, setDisclosure] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [pendingAction, setPendingAction] = useState<ActionProposal | null>(null);
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
    boot().catch((error: Error) => setStatus(error.message));
  }, []);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ block: "end" });
  }, [messages]);

  async function sendTurn(text: string) {
    let activeId = conversationId;
    if (!activeId) {
      const created = await api<Conversation>(userId, "/v1/conversations", {
        method: "POST",
        body: JSON.stringify({
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
    setPendingAction(null);
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
      if (event === "action") {
        setPendingAction(readAction(data));
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
              <button className="icon-btn" type="button" aria-label="收起对话" onClick={collapse}>
                –
              </button>
            </div>
          </header>
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
          <div className="widget-foot">
            {pendingAction?.code === "care_booking" ? (
              <div className="action-card">
                <p>{actionLabel(pendingAction)}</p>
                <div className="action-row">
                  <button
                    type="button"
                    onClick={() => {
                      setPendingAction(null);
                      setStatus("预约已交给系统，以屏幕上的确认为准。");
                    }}
                  >
                    确认预约
                  </button>
                  <button type="button" className="ghost" onClick={() => setPendingAction(null)}>
                    取消
                  </button>
                </div>
              </div>
            ) : null}
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
          </div>
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

function BrandMark({ compact = false }: { compact?: boolean }) {
  const className = ["brand-logo", compact ? "compact" : ""].filter(Boolean).join(" ");
  return <img className={className} src={brandLogo} alt="玫莉蔻" />;
}

const DATE_LABEL: Record<string, string> = {
  sunday: "星期天",
  monday: "星期一",
  tuesday: "星期二",
  wednesday: "星期三",
  thursday: "星期四",
  friday: "星期五",
  saturday: "星期六",
  tomorrow: "明天",
  day_after_tomorrow: "后天",
  tonight: "今晚",
};

function readAction(data: Record<string, unknown>): ActionProposal | null {
  if (typeof data.code !== "string" || data.code === "none") return null;
  const slots =
    data.slots && typeof data.slots === "object" && !Array.isArray(data.slots)
      ? Object.fromEntries(
          Object.entries(data.slots as Record<string, unknown>).filter(
            (entry): entry is [string, string] => typeof entry[1] === "string",
          ),
        )
      : {};
  return {
    code: data.code,
    slots,
    confirm_required: data.confirm_required === true,
  };
}

function actionLabel(action: ActionProposal): string {
  const when = DATE_LABEL[action.slots.date_hint] || "";
  if (when) return `${when} · 护理`;
  return "护理预约";
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
