const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(
  /\/$/,
  ""
)

export const ACCESS_TOKEN_STORAGE_KEY = "liara-assistant-access-token"

export type ExpertiseLevel = "beginner" | "intermediate" | "advanced"

export type User = {
  id: string
  email: string
  expertise_level: ExpertiseLevel
  email_verified_at: string
  created_at: string
  last_login_at: string
}

export type AuthSession = {
  accessToken: string
  user: User
}

export type ChatSummary = {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export type ChatMessageRecord = {
  id: string
  chat_id: string
  role: "user" | "assistant"
  content: string
  position: number
  details: Record<string, unknown>
  created_at: string
}

export type ChatDetail = Omit<ChatSummary, "message_count"> & {
  messages: ChatMessageRecord[]
}

export type ChatTurn = {
  user_message: ChatMessageRecord
  assistant_message: ChatMessageRecord
}

export type StreamedChatTurn = {
  assistant_message: ChatMessageRecord
  rag: Record<string, unknown>
}

type ChatStreamCallbacks = {
  onStatus?: (status: string) => void
  onToken: (content: string) => void
}

type ApiErrorPayload = {
  detail?: string
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function apiRequest<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set("Accept", "application/json")
  if (options.body) {
    headers.set("Content-Type", "application/json")
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })
  const contentType = response.headers.get("content-type") ?? ""
  const payload: unknown = contentType.includes("application/json")
    ? await response.json()
    : null

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as ApiErrorPayload).detail
        : undefined
    throw new ApiError(
      response.status,
      detail ?? "ارتباط با سرور با مشکل مواجه شد. دوباره تلاش کنید."
    )
  }

  return payload as T
}

export async function requestEmailCode(email: string) {
  return apiRequest<{
    message: string
    expires_in: number
    retry_after: number
  }>("/auth/email/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  })
}

export async function verifyEmailCode(email: string, code: string) {
  const response = await apiRequest<{
    access_token: string
    token_type: string
    expires_in: number
    user: User
  }>("/auth/email/verify", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  })

  return {
    accessToken: response.access_token,
    user: response.user,
  } satisfies AuthSession
}

export function getCurrentUser(token: string) {
  return apiRequest<User>("/auth/me", { token })
}

export function updateCurrentUserPreferences(
  token: string,
  expertiseLevel: ExpertiseLevel
) {
  return apiRequest<User>("/auth/me", {
    method: "PATCH",
    token,
    body: JSON.stringify({ expertise_level: expertiseLevel }),
  })
}

export function listChats(token: string) {
  return apiRequest<ChatSummary[]>("/chats", { token })
}

export function getChat(token: string, chatId: string) {
  return apiRequest<ChatDetail>(`/chats/${chatId}`, { token })
}

export function createChat(token: string, title: string) {
  return apiRequest<ChatSummary>("/chats", {
    method: "POST",
    token,
    body: JSON.stringify({ title }),
  })
}

export function sendChatMessage(
  token: string,
  chatId: string,
  question: string
) {
  return apiRequest<ChatTurn>(`/chats/${chatId}/messages`, {
    method: "POST",
    token,
    body: JSON.stringify({ question, max_refinements: 2 }),
  })
}

export async function streamChatMessage(
  token: string,
  chatId: string,
  question: string,
  callbacks: ChatStreamCallbacks
): Promise<StreamedChatTurn> {
  const response = await fetch(
    `${API_BASE_URL}/chats/${chatId}/messages/stream`,
    {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, max_refinements: 2 }),
    }
  )

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as
      | ApiErrorPayload
      | null
    throw new ApiError(
      response.status,
      payload?.detail ?? "ارتباط با سرور با مشکل مواجه شد. دوباره تلاش کنید."
    )
  }
  if (!response.body) {
    throw new ApiError(502, "مرورگر نتوانست پاسخ زنده را دریافت کند.")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let completedTurn: StreamedChatTurn | null = null

  const processFrame = (frame: string) => {
    if (!frame.trim()) {
      return
    }
    let eventName = "message"
    const dataLines: string[] = []
    for (const line of frame.split("\n")) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    if (!dataLines.length) {
      return
    }

    const payload = JSON.parse(dataLines.join("\n")) as Record<string, unknown>
    if (eventName === "token" && typeof payload.content === "string") {
      callbacks.onToken(payload.content)
    } else if (eventName === "status" && typeof payload.status === "string") {
      callbacks.onStatus?.(payload.status)
    } else if (eventName === "done") {
      completedTurn = payload as StreamedChatTurn
    } else if (eventName === "error") {
      throw new ApiError(
        502,
        typeof payload.detail === "string"
          ? payload.detail
          : "پاسخ زنده با خطا متوقف شد."
      )
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer = (buffer + decoder.decode(value, { stream: !done })).replace(
      /\r\n/g,
      "\n"
    )
    let boundary = buffer.indexOf("\n\n")
    while (boundary !== -1) {
      processFrame(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      boundary = buffer.indexOf("\n\n")
    }
    if (done) {
      break
    }
  }
  processFrame(buffer)

  if (!completedTurn) {
    throw new ApiError(502, "پاسخ زنده پیش از تکمیل متوقف شد.")
  }
  return completedTurn
}
