import { useState } from "react"
import {
  Menu,
  MessageSquare,
  Moon,
  Plus,
  Sparkles,
  Sun,
  X,
} from "lucide-react"

import AIChatCard, { type ChatMessage } from "@/components/ui/ai-chat"
import { StarfieldBackground } from "@/components/ui/starfield-background"
import { useTheme } from "@/components/theme-provider"
import { cn } from "@workspace/ui/lib/utils"

type ChatHistory = {
  id: string
  title: string
  messages: ChatMessage[]
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    sender: "ai",
    text: "👋 سلام! من دستیار هوشمند لیارا هستم. چطور می‌توانم کمکتان کنم؟",
  },
]

function createDraftChat(): ChatHistory {
  return {
    id: `draft-${Date.now()}`,
    title: "گفتگوی جدید",
    messages: [...INITIAL_MESSAGES],
  }
}

function getPreview(messages: ChatMessage[]) {
  return messages[messages.length - 1]?.text ?? "No messages yet"
}

function getTitle(messages: ChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.sender === "user")

  if (!firstUserMessage) {
    return "گفتگوی جدید"
  }

  return firstUserMessage.text.length > 28
    ? `${firstUserMessage.text.slice(0, 28)}…`
    : firstUserMessage.text
}

function hasConversation(chat: ChatHistory) {
  return chat.messages.some((message) => message.sender === "user")
}

export function App() {
  const { theme, setTheme } = useTheme()
  const [chats, setChats] = useState<ChatHistory[]>([])
  const [draftChat, setDraftChat] = useState<ChatHistory | null>(
    createDraftChat
  )
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const selectedChatId = activeChatId ?? draftChat?.id ?? chats[0]?.id
  const activeChat =
    draftChat?.id === selectedChatId
      ? draftChat
      : chats.find((chat) => chat.id === selectedChatId) ??
        draftChat ??
        chats[0]
  const visibleChats = chats
    .filter(hasConversation)
    .filter(
      (chat, index, allChats) =>
        allChats.findIndex((candidate) => candidate.id === chat.id) === index
    )

  const handleCreateChat = () => {
    if (draftChat) {
      setActiveChatId(draftChat.id)
      setIsSidebarOpen(false)
      return
    }

    const newDraft = createDraftChat()

    setDraftChat(newDraft)
    setActiveChatId(newDraft.id)
    setIsSidebarOpen(false)
  }

  const handleSelectChat = (chatId: string) => {
    setActiveChatId(chatId)
    setIsSidebarOpen(false)
  }

  const handleMessagesChange = (messages: ChatMessage[]) => {
    if (draftChat?.id === selectedChatId) {
      const updatedDraft: ChatHistory = {
        ...draftChat,
        messages,
        title: getTitle(messages),
      }

      if (messages.some((message) => message.sender === "user")) {
        setChats((currentChats) => {
          const existingChat = currentChats.some(
            (chat) => chat.id === updatedDraft.id
          )

          if (existingChat) {
            return currentChats.map((chat) =>
              chat.id === updatedDraft.id ? updatedDraft : chat
            )
          }

          return [updatedDraft, ...currentChats]
        })
        setDraftChat(null)
      } else {
        setDraftChat(updatedDraft)
      }

      return
    }

    setChats((currentChats) =>
      currentChats.map((chat) => {
        if (chat.id !== selectedChatId) {
          return chat
        }

        return {
          ...chat,
          messages,
          title:
            chat.title === "گفتگوی جدید" ? getTitle(messages) : chat.title,
        }
      })
    )
  }

  return (
    <main
      dir="rtl"
      className="flex h-svh max-h-svh flex-col overflow-hidden bg-[#f6f8ff] text-[#152044] dark:bg-[#080d1e] dark:text-white md:flex-row-reverse"
    >
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-[70] flex h-svh w-[min(88vw,20rem)] shrink-0 flex-col border-r border-[#dbe2f5] bg-white text-[#152044] shadow-2xl transition-transform duration-300 dark:border-[#26366a] dark:bg-[#111c45] dark:text-white md:static md:z-auto md:h-full md:w-80 md:translate-x-0 md:border-r md:shadow-none",
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
                className="h-7 w-auto object-contain"
                src="https://liara.ir/assets/images/liara-logo.svg"
              />
            </a>
            <div>
              <h1 className="text-sm font-bold text-[#152044] dark:text-white">
                دستیار هوشمند لیارا
              </h1>
            </div>
            <button
              aria-label="بستن تاریخچه گفتگوها"
              className="mr-auto rounded-lg p-2 text-[#667394] transition-colors hover:bg-[#edf1fb] dark:text-white/60 dark:hover:bg-white/10 md:hidden"
              onClick={() => setIsSidebarOpen(false)}
              type="button"
            >
              <X aria-hidden="true" className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
          <div className="mb-3 flex items-center justify-between px-2">
            <p className="text-xs font-medium text-[#7885a5] dark:text-white/45">
              گفتگوهای اخیر
            </p>
            <span className="rounded-full bg-[#edf1fb] px-2 py-0.5 text-[10px] text-[#7885a5] dark:bg-white/10 dark:text-white/50">
              {visibleChats.length}
            </span>
          </div>

          <div className="space-y-1">
            {visibleChats.map((chat) => {
              const isActive = chat.id === activeChat.id

              return (
                <button
                  key={chat.id}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors",
                    isActive
                      ? "bg-[#e7ecff] text-[#26366a] shadow-inner shadow-[#c2cdf2]/50 dark:bg-[#26366a] dark:text-white dark:shadow-white/5"
                      : "text-[#667394] hover:bg-[#f3f6ff] hover:text-[#26366a] dark:text-white/60 dark:hover:bg-white/[0.07] dark:hover:text-white"
                  )}
                  onClick={() => handleSelectChat(chat.id)}
                  type="button"
                >
                  <MessageSquare
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 h-4 w-4 shrink-0",
                      isActive
                        ? "text-[#5265cf] dark:text-white"
                        : "text-[#a1acc6] dark:text-white/35"
                    )}
                  />
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
            {visibleChats.length === 0 && (
              <p className="px-2 py-4 text-center text-xs leading-6 text-[#8995b3] dark:text-white/40">
                هنوز گفتگویی شروع نشده است.
              </p>
            )}
          </div>
        </div>

        <div className="border-t border-[#e8ecf7] p-3 dark:border-white/10">
          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-l from-[#5b6cff] to-[#35cfc5] px-3 py-2.5 text-sm font-semibold text-[#101a3d] shadow-lg shadow-[#2a4e9a]/30 transition-transform hover:-translate-y-0.5"
            onClick={handleCreateChat}
            type="button"
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            گفتگوی جدید
          </button>
        </div>
      </aside>

      {isSidebarOpen && (
        <button
          aria-label="بستن تاریخچه گفتگوها"
          className="fixed inset-0 z-[60] cursor-default bg-[#08102a]/40 backdrop-blur-md dark:bg-black/45 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
          type="button"
        />
      )}

      <section className="relative flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden bg-[#06091d] px-4 py-4 sm:px-8 sm:py-6">
        <button
          aria-label="تغییر پوسته"
          className="fixed right-4 top-4 z-30 flex h-11 w-11 items-center justify-center rounded-xl border border-[#d7def1] bg-white/85 text-[#5265cf] shadow-lg shadow-[#5265cf]/10 backdrop-blur-md transition-colors hover:bg-white dark:border-white/15 dark:bg-[#111c45]/85 dark:text-[#a7f2e5] dark:shadow-black/20 dark:hover:bg-[#1b2a5b]"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          title="تغییر پوسته"
          type="button"
        >
          {theme === "dark" ? (
            <Sun aria-hidden="true" className="h-4 w-4" />
          ) : (
            <Moon aria-hidden="true" className="h-4 w-4" />
          )}
        </button>
        <StarfieldBackground />
        <div className="relative flex h-full min-h-0 w-full max-w-5xl flex-col items-center gap-4">
          <div className="shrink-0 text-center">
            <div className="mb-4 flex items-center justify-center gap-2 text-xs font-medium text-[#aab9ff]">
              <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
              {activeChat.title}
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
              دستیار هوشمند لیارا
            </h1>
            <p className="mt-3 max-w-md text-sm text-white/70">
              برای استقرار و مدیریت سرویس‌ها، سریع و ساده راهنمایی بگیرید.
            </p>
          </div>
          <AIChatCard
            key={activeChat.id}
            className="min-h-0 max-h-full max-w-[720px] flex-1"
            messages={activeChat.messages}
            onMessagesChange={handleMessagesChange}
          />
        </div>
        <button
          aria-label="باز کردن تاریخچه گفتگوها"
          className="fixed left-4 top-4 z-30 flex h-11 w-11 items-center justify-center rounded-xl bg-[#5265cf] text-white shadow-xl shadow-[#5265cf]/30 transition-transform hover:-translate-y-0.5 dark:bg-[#a7f2e5] dark:text-[#0b1739] dark:shadow-[#0b1739]/30 md:hidden"
          onClick={() => setIsSidebarOpen(true)}
          type="button"
        >
          <Menu aria-hidden="true" className="h-4 w-4" />
        </button>
      </section>
    </main>
  )
}
