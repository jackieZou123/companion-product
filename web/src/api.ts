export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type Thread = {
  conversation_id: string;
  character_id: string;
  message_count: number;
};

export type Conversation = {
  conversation_id: string;
  ai_disclosure: string;
  messages: ChatMessage[];
};

const KEYS = {
  user: "companion.user_id",
  adult: "companion.adult",
  current: "companion.conversation_id",
};

function newUserId(): string {
  // http://局域网 IP 不是安全上下文，没有 crypto.randomUUID
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function storageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function storageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* 隐私模式写不了，会话内仍用内存 id */
  }
}

export function loadUserId(): string {
  const existing = storageGet(KEYS.user);
  if (existing) return existing;
  const created = newUserId();
  storageSet(KEYS.user, created);
  return created;
}

export function loadAdult(): boolean {
  return storageGet(KEYS.adult) === "1";
}

export function saveAdult(): void {
  storageSet(KEYS.adult, "1");
}

export function loadCurrentId(): string {
  return storageGet(KEYS.current) || "";
}

export function saveCurrentId(id: string): void {
  storageSet(KEYS.current, id);
}

export function clearCurrentId(): void {
  try {
    localStorage.removeItem(KEYS.current);
  } catch {
    /* ignore */
  }
}

function headers(userId: string): HeadersInit {
  return {
    "content-type": "application/json",
    "X-User-Id": userId,
  };
}

export async function api<T>(userId: string, path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: { ...headers(userId), ...(options.headers || {}) },
  });
  if (response.status === 204) return null as T;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (body as { detail?: string }).detail;
    throw new Error(typeof detail === "string" ? detail : "暂时接不上，请稍后再试。");
  }
  return body as T;
}

export async function readSse(
  response: Response,
  onEvent: (event: string, data: Record<string, unknown>) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      let event = "message";
      const dataLines: string[] = [];
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      onEvent(event, JSON.parse(dataLines.join("\n")) as Record<string, unknown>);
    }
  }
}
