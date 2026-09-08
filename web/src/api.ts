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
  gender: "companion.gender",
  current: "companion.conversation_id",
};

export type UserGender = "female" | "male";

export function loadUserId(): string {
  const existing = localStorage.getItem(KEYS.user);
  if (existing) return existing;
  const created = crypto.randomUUID();
  localStorage.setItem(KEYS.user, created);
  return created;
}

export function loadAdult(): boolean {
  return localStorage.getItem(KEYS.adult) === "1";
}

export function saveAdult(): void {
  localStorage.setItem(KEYS.adult, "1");
}

export function loadGender(): UserGender | "" {
  const value = localStorage.getItem(KEYS.gender);
  return value === "female" || value === "male" ? value : "";
}

export function saveGender(gender: UserGender): void {
  localStorage.setItem(KEYS.gender, gender);
}

export function clearGender(): void {
  localStorage.removeItem(KEYS.gender);
}

export function loadCurrentId(): string {
  return localStorage.getItem(KEYS.current) || "";
}

export function saveCurrentId(id: string): void {
  localStorage.setItem(KEYS.current, id);
}

export function clearCurrentId(): void {
  localStorage.removeItem(KEYS.current);
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
