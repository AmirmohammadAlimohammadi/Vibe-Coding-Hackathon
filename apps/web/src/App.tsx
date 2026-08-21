import { useCallback, useEffect, useMemo, useState } from "react"
import {
  LoaderCircle,
  LogOut,
  GraduationCap,
  Menu,
  MessageSquare,
  Moon,
  Plus,
  Sun,
  UserRound,
  X,
} from "lucide-react"

import { LoginScreen } from "@/components/auth/login-screen"
import { useTheme } from "@/components/theme-provider"
import AIChatCard, { type ChatMessage } from "@/components/ui/ai-chat"
import { StarfieldBackground } from "@/components/ui/starfield-background"
import {
  ACCESS_TOKEN_STORAGE_KEY,
  ApiError,
  createChat,
  getChat,
  getCurrentUser,
  listChats,
  sendChatMessage,
  updateCurrentUserPreferences,
  type AuthSession,
  type ChatMessageRecord,
  type ExpertiseLevel,
  type User,
} from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

type ChatHistory = {
  id: string
  title: string
  messages: ChatMessage[]
  loaded: boolean
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  sender: "ai",
  text: "👋 سلام! من دستیار هوشمند لیارا هستم. چطور می‌توانم کمکتان کنم؟",
}

const EXPERTISE_OPTIONS: Array<{
  value: ExpertiseLevel
  label: string
  description: string
}> = [
  {
    value: "beginner",
    label: "مبتدی",
    description: "توضیح ساده و قدم‌به‌قدم",
  },
  {
    value: "intermediate",
    label: "متوسط",
    description: "پاسخ کاربردی با جزئیات لازم",
  },
  {
    value: "advanced",
    label: "حرفه‌ای",
    description: "جزئیات فنی، محدودیت‌ها و ملاحظات",
  },
]

function mapMessage(message: ChatMessageRecord): ChatMessage {
  return {
    id: message.id,
    sender: message.role === "assistant" ? "ai" : "user",
    text: message.content,
  }
}

function getPreview(messages: ChatMessage[]) {
  const lastMessage = messages[messages.length - 1]
  return lastMessage && lastMessage.id !== "welcome"
    ? lastMessage.text
    : "برای مشاهده گفتگو انتخاب کنید"
}

function getTitle(message: string) {
  return message.length > 34 ? `${message.slice(0, 34)}…` : message
}

function messageFromError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message
  }
  return "ارتباط با سرور برقرار نشد. دوباره تلاش کنید."
}

type ChatWorkspaceProps = {
  session: AuthSession
  onLogout: () => void
  onUserUpdate: (user: User) => void
}

function ChatWorkspace({
  session,
  onLogout,
  onUserUpdate,
}: ChatWorkspaceProps) {
  const { theme, setTheme } = useTheme()
  const [chats, setChats] = useState<ChatHistory[]>([])
  const [draftMessages, setDraftMessages] = useState<ChatMessage[]>([
    WELCOME_MESSAGE,
  ])
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSending, setIsSending] = useState(false)
  const [isUpdatingExpertise, setIsUpdatingExpertise] = useState(false)
  const [error, setError] = useState("")

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId),
    [activeChatId, chats]
  )
  const activeMessages = activeChat?.messages ?? draftMessages
  const activeTitle = activeChat?.title ?? "گفتگوی جدید"

  const handleApiError = useCallback(
    (apiError: unknown) => {
      if (apiError instanceof ApiError && apiError.status === 401) {
        onLogout()
        return
      }
      setError(messageFromError(apiError))
    },
    [onLogout]
  )

  const loadChat = async (chatId: string) => {
    const currentChat = chats.find((chat) => chat.id === chatId)
    if (currentChat?.loaded) {
      return
    }
    try {
      const detail = await getChat(session.accessToken, chatId)
      setChats((current) =>
        current.map((chat) =>
          chat.id === chatId
            ? {
                ...chat,
                title: detail.title,
                loaded: true,
                messages: [WELCOME_MESSAGE, ...detail.messages.map(mapMessage)],
              }
            : chat
        )
      )
    } catch (loadError) {
      handleApiError(loadError)
    }
  }

  useEffect(() => {
    let active = true
    const loadChats = async () => {
      try {
        const summaries = await listChats(session.accessToken)
        if (!active) {
          return
        }
        const nextChats = summaries.map((chat) => ({
          id: chat.id,
          title: chat.title,
          messages: [WELCOME_MESSAGE],
          loaded: false,
        }))
        setChats(nextChats)
        if (nextChats[0]) {
          setActiveChatId(nextChats[0].id)
          const detail = await getChat(session.accessToken, nextChats[0].id)
          if (active) {
            setChats((current) =>
              current.map((chat) =>
                chat.id === detail.id
                  ? {
                      ...chat,
                      title: detail.title,
                      loaded: true,
                      messages: [
                        WELCOME_MESSAGE,
                        ...detail.messages.map(mapMessage),
                      ],
                    }
                  : chat
              )
            )
          }
        }
      } catch (loadError) {
        if (active) {
          handleApiError(loadError)
        }
      } finally {
        if (active) {
          setIsLoading(false)
        }
      }
    }
    void loadChats()
    return () => {
      active = false
    }
  }, [handleApiError, session.accessToken])

  const handleCreateChat = () => {
    setActiveChatId(null)
    setDraftMessages([WELCOME_MESSAGE])
    setError("")
    setIsSidebarOpen(false)
  }

  const handleExpertiseChange = async (expertiseLevel: ExpertiseLevel) => {
    if (
      expertiseLevel === session.user.expertise_level ||
      isUpdatingExpertise
    ) {
      return
    }
    setIsUpdatingExpertise(true)
    setError("")
    try {
      const user = await updateCurrentUserPreferences(
        session.accessToken,
        expertiseLevel
      )
      onUserUpdate(user)
    } catch (updateError) {
      handleApiError(updateError)
    } finally {
      setIsUpdatingExpertise(false)
    }
  }

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId)
    setError("")
    setIsSidebarOpen(false)
    void loadChat(chatId)
  }

  const appendToChat = (chatId: string, message: ChatMessage) => {
    setChats((current) =>
      current.map((chat) =>
        chat.id === chatId
          ? { ...chat, loaded: true, messages: [...chat.messages, message] }
          : chat
      )
    )
  }

  const handleSendMessage = async (question: string) => {
    setIsSending(true)
    setError("")
    let targetChatId = activeChatId
    try {
      if (!targetChatId) {
        const optimisticMessages = [
          ...draftMessages,
          { sender: "user", text: question } satisfies ChatMessage,
        ]
        setDraftMessages(optimisticMessages)
        const created = await createChat(
          session.accessToken,
          getTitle(question)
        )
        targetChatId = created.id
        setChats((current) => [
          {
            id: created.id,
            title: created.title,
            messages: optimisticMessages,
            loaded: true,
          },
          ...current,
        ])
        setActiveChatId(created.id)
      } else {
        appendToChat(targetChatId, { sender: "user", text: question })
        setChats((current) =>
          current.map((chat) =>
            chat.id === targetChatId && chat.title === "New chat"
              ? { ...chat, title: getTitle(question) }
              : chat
          )
        )
      }

      const turn = await sendChatMessage(
        session.accessToken,
        targetChatId,
        question
      )
      appendToChat(targetChatId, mapMessage(turn.assistant_message))
    } catch (sendError) {
      handleApiError(sendError)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <main
      dir="rtl"
      className="flex h-svh max-h-svh flex-col overflow-hidden bg-[#f6f8ff] text-[#152044] md:flex-row-reverse dark:bg-[#080d1e] dark:text-white"
    >
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] flex h-svh w-[min(88vw,20rem)] shrink-0 flex-col border-r border-[#dbe2f5] bg-white text-[#152044] shadow-2xl transition-transform duration-300 md:static md:z-auto md:h-full md:w-80 md:translate-x-0 md:shadow-none dark:border-[#26366a] dark:bg-[#111c45] dark:text-white",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="border-b border-[#e8ecf7] px-4 py-4 dark:border-white/10">
          <div className="flex items-center gap-3">
            <a
              aria-label="رفتن به سایت لیارا"
              className="flex h-10 w-[90px] items-center justify-center rounded-2xl bg-gradient-to-br from-[#62e4d1] to-[#6575ff] px-1 shadow-lg shadow-[#4f76ff]/30 transition-transform hover:-translate-y-0.5"
              href="https://liara.ir/"
              rel="noreferrer"
              target="_blank"
            >
              <img
                alt="لیارا"
                className="h-7 w-auto"
                src="https://liara.ir/assets/images/liara-logo.svg"
              />
            </a>
            <h1 className="text-sm font-bold"></h1>
            <button
              aria-label="بستن تاریخچه گفتگوها"
              className="mr-auto rounded-lg p-2 text-[#667394] hover:bg-[#edf1fb] md:hidden dark:text-white/60 dark:hover:bg-white/10"
              onClick={() => setIsSidebarOpen(false)}
              type="button"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <div className="mb-3 flex items-center justify-between px-2">
            <p className="text-xs font-medium text-[#7885a5] dark:text-white/45">
              گفتگوهای اخیر
            </p>
            <span className="rounded-full bg-[#edf1fb] px-2 py-0.5 text-[10px] text-[#7885a5] dark:bg-white/10 dark:text-white/50">
              {chats.length}
            </span>
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-[#7885a5] dark:text-white/40">
              <LoaderCircle className="h-5 w-5 animate-spin" />
            </div>
          ) : (
            <div className="space-y-1">
              {chats.map((chat) => {
                const isActive = chat.id === activeChatId
                return (
                  <button
                    key={chat.id}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "flex w-full items-start gap-3 rounded-xl px-3 py-3 text-right transition-colors",
                      isActive
                        ? "bg-[#e7ecff] text-[#26366a] dark:bg-[#26366a] dark:text-white"
                        : "text-[#667394] hover:bg-[#f3f6ff] dark:text-white/60 dark:hover:bg-white/[0.07]"
                    )}
                    onClick={() => handleSelectChat(chat.id)}
                    type="button"
                  >
                    <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-[#6575ff]" />
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">
                        {chat.title}
                      </span>
                      <span className="mt-1 block truncate text-xs text-[#8995b3] dark:text-white/40">
                        {getPreview(chat.messages)}
                      </span>
                    </span>
                  </button>
                )
              })}
              {chats.length === 0 && (
                <p className="px-2 py-8 text-center text-xs leading-6 text-[#8995b3] dark:text-white/40">
                  هنوز گفتگویی شروع نشده است.
                </p>
              )}
            </div>
          )}
        </div>

        <div className="border-t border-[#e8ecf7] p-3 dark:border-white/10">
          <div className="mb-3 rounded-xl border border-[#e1e7f5] bg-[#f8faff] p-3 dark:border-white/10 dark:bg-white/[0.04]">
            <div className="mb-2.5 flex items-center gap-2 text-xs font-semibold text-[#536185] dark:text-white/70">
              <GraduationCap className="h-4 w-4 text-[#5265cf] dark:text-[#a7f2e5]" />
              سطح پاسخ‌ها
              {isUpdatingExpertise && (
                <LoaderCircle className="mr-auto h-3.5 w-3.5 animate-spin" />
              )}
            </div>
            <div className="grid grid-cols-3 gap-1 rounded-lg bg-[#e9eefb] p-1 dark:bg-black/20">
              {EXPERTISE_OPTIONS.map((option) => {
                const isSelected = session.user.expertise_level === option.value
                return (
                  <button
                    key={option.value}
                    aria-pressed={isSelected}
                    className={cn(
                      "rounded-md px-1.5 py-2 text-[11px] font-medium transition-all disabled:cursor-wait disabled:opacity-60",
                      isSelected
                        ? "bg-white text-[#3549aa] shadow-sm dark:bg-[#26366a] dark:text-[#a7f2e5]"
                        : "text-[#7582a3] hover:text-[#3549aa] dark:text-white/45 dark:hover:text-white"
                    )}
                    disabled={isUpdatingExpertise}
                    onClick={() => void handleExpertiseChange(option.value)}
                    title={option.description}
                    type="button"
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
            <p className="mt-2 text-[10px] leading-5 text-[#8995b3] dark:text-white/35">
              {
                EXPERTISE_OPTIONS.find(
                  (option) => option.value === session.user.expertise_level
                )?.description
              }
            </p>
          </div>
          <div className="mb-3 flex items-center gap-3 rounded-xl bg-[#f3f6ff] p-3 dark:bg-white/[0.06]">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#e1e7ff] text-[#5265cf] dark:bg-white/10 dark:text-[#a7f2e5]">
              <UserRound className="h-4 w-4" />
            </div>
            <span className="min-w-0 flex-1 truncate text-xs" dir="ltr">
              {session.user.email}
            </span>
            <button
              aria-label="خروج"
              className="rounded-lg p-2 text-[#8995b3] hover:bg-white hover:text-red-500 dark:hover:bg-white/10"
              onClick={onLogout}
              type="button"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-l from-[#5b6cff] to-[#35cfc5] px-3 py-2.5 text-sm font-semibold text-[#101a3d] shadow-lg shadow-[#2a4e9a]/30 transition-transform hover:-translate-y-0.5"
            onClick={handleCreateChat}
            type="button"
          >
            <Plus className="h-4 w-4" />
            گفتگوی جدید
          </button>
        </div>
      </aside>

      {isSidebarOpen && (
        <button
          aria-label="بستن تاریخچه گفتگوها"
          className="fixed inset-0 z-[60] cursor-default bg-[#08102a]/40 backdrop-blur-md md:hidden dark:bg-black/45"
          onClick={() => setIsSidebarOpen(false)}
          type="button"
        />
      )}

      <section className="relative flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden bg-[#06091d] p-3 sm:p-5 lg:p-7">
        <button
          aria-label="تغییر پوسته"
          className="fixed top-4 right-4 z-30 flex h-11 w-11 items-center justify-center rounded-xl border border-[#d7def1] bg-white/85 text-[#5265cf] shadow-lg backdrop-blur-md hover:bg-white dark:border-white/15 dark:bg-[#111c45]/85 dark:text-[#a7f2e5] dark:hover:bg-[#1b2a5b]"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          type="button"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
        <StarfieldBackground />
        <div className="relative flex h-full min-h-0 w-full max-w-[1400px] items-stretch justify-center">
          <AIChatCard
            key={activeChatId ?? "draft"}
            className="max-h-full min-h-0 max-w-none flex-1"
            error={error}
            isSending={isSending}
            messages={activeMessages}
            onSendMessage={handleSendMessage}
            title={activeTitle}
          />
        </div>
        <button
          aria-label="باز کردن تاریخچه گفتگوها"
          className="fixed top-4 left-4 z-30 flex h-11 w-11 items-center justify-center rounded-xl bg-[#5265cf] text-white shadow-xl shadow-[#5265cf]/30 transition-transform hover:-translate-y-0.5 md:hidden dark:bg-[#a7f2e5] dark:text-[#0b1739]"
          onClick={() => setIsSidebarOpen(true)}
          type="button"
        >
          <Menu className="h-4 w-4" />
        </button>
      </section>
    </main>
  )
}

export function App() {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [isRestoringSession, setIsRestoringSession] = useState(() =>
    Boolean(localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY))
  )

  useEffect(() => {
    const token = localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
    if (!token) {
      return
    }
    getCurrentUser(token)
      .then((user) => setSession({ accessToken: token, user }))
      .catch(() => localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY))
      .finally(() => setIsRestoringSession(false))
  }, [])

  const handleAuthenticated = (nextSession: AuthSession) => {
    localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, nextSession.accessToken)
    setSession(nextSession)
  }

  const handleLogout = useCallback(() => {
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
    setSession(null)
  }, [])

  const handleUserUpdate = (user: User) => {
    setSession((current) => (current ? { ...current, user } : current))
  }

  if (isRestoringSession) {
    return (
      <main className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[#06091d] text-[#a7f2e5]">
        <StarfieldBackground />
        <LoaderCircle className="relative z-10 h-8 w-8 animate-spin" />
      </main>
    )
  }
  if (!session) {
    return <LoginScreen onAuthenticated={handleAuthenticated} />
  }
  return (
    <ChatWorkspace
      onLogout={handleLogout}
      onUserUpdate={handleUserUpdate}
      session={session}
    />
  )
}
