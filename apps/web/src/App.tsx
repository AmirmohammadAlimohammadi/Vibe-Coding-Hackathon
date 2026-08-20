import { useState } from "react"
import { MessageSquare, Plus, Sparkles } from "lucide-react"

import AIChatCard, { type ChatMessage } from "@/components/ui/ai-chat"
import { cn } from "@workspace/ui/lib/utils"

type ChatHistory = {
  id: string
  title: string
  messages: ChatMessage[]
}

const INITIAL_MESSAGES: ChatMessage[] = [
  { sender: "ai", text: "👋 درود کاربر گرامی سوالات خود را میتوانید از من بپرسید." },
]

const STARTER_CHATS: ChatHistory[] = [
  {
    id: "welcome",
    title: "Welcome to your assistant",
    messages: INITIAL_MESSAGES,
  },
  {
    id: "product-ideas",
    title: "Product ideas",
    messages: [
      { sender: "user", text: "Help me brainstorm a product idea." },
      {
        sender: "ai",
        text: "🤖 Let’s explore a few ideas together. What problem do you want to solve?",
      },
    ],
  },
  {
    id: "daily-plan",
    title: "Daily planning",
    messages: [
      { sender: "user", text: "Create a focused plan for today." },
      {
        sender: "ai",
        text: "🤖 Start with your most important task, then schedule two focused work blocks.",
      },
    ],
  },
]

function getPreview(messages: ChatMessage[]) {
  return messages[messages.length - 1]?.text ?? "No messages yet"
}

function getTitle(messages: ChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.sender === "user")

  if (!firstUserMessage) {
    return "New chat"
  }

  return firstUserMessage.text.length > 28
    ? `${firstUserMessage.text.slice(0, 28)}…`
    : firstUserMessage.text
}

export function App() {
  const [chats, setChats] = useState<ChatHistory[]>(STARTER_CHATS)
  const [activeChatId, setActiveChatId] = useState(STARTER_CHATS[0].id)
  const activeChat =
    chats.find((chat) => chat.id === activeChatId) ?? chats[0]

  const handleCreateChat = () => {
    const newChat: ChatHistory = {
      id: `chat-${Date.now()}`,
      title: "New chat",
      messages: [...INITIAL_MESSAGES],
    }

    setChats((currentChats) => [newChat, ...currentChats])
    setActiveChatId(newChat.id)
  }

  const handleMessagesChange = (messages: ChatMessage[]) => {
    setChats((currentChats) =>
      currentChats.map((chat) => {
        if (chat.id !== activeChat.id) {
          return chat
        }

        return {
          ...chat,
          messages,
          title: chat.title === "New chat" ? getTitle(messages) : chat.title,
        }
      })
    )
  }

  return (
    <main className="flex min-h-svh flex-col bg-black text-white md:flex-row">
      <aside className="flex w-full shrink-0 flex-col border-b border-white/10 bg-white/[0.03] md:h-svh md:w-72 md:border-b-0 md:border-r">
        <div className="border-b border-white/10 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/15 bg-white/10">
              <Sparkles aria-hidden="true" className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold">AI Workspace</p>
              <p className="text-xs text-white/45">Your conversations</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-4">
          <div className="mb-3 flex items-center justify-between px-2">
            <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-white/40">
              Recent chats
            </p>
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] text-white/50">
              {chats.length}
            </span>
          </div>

          <div className="space-y-1">
            {chats.map((chat) => {
              const isActive = chat.id === activeChat.id

              return (
                <button
                  key={chat.id}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left transition-colors",
                    isActive
                      ? "bg-white/12 text-white shadow-inner shadow-white/5"
                      : "text-white/55 hover:bg-white/[0.06] hover:text-white/85"
                  )}
                  onClick={() => setActiveChatId(chat.id)}
                  type="button"
                >
                  <MessageSquare
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 h-4 w-4 shrink-0",
                      isActive ? "text-white" : "text-white/35"
                    )}
                  />
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">
                      {chat.title}
                    </span>
                    <span className="mt-1 block truncate text-xs text-white/35">
                      {getPreview(chat.messages)}
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="border-t border-white/10 p-3">
          <button
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/10 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-white/15"
            onClick={handleCreateChat}
            type="button"
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            New chat
          </button>
          <p className="mt-3 text-center text-[11px] text-white/30">
            Press <kbd className="rounded bg-white/10 px-1 py-0.5">D</kbd> to toggle theme
          </p>
        </div>
      </aside>

      <section className="relative flex min-w-0 flex-1 items-center justify-center overflow-hidden px-4 py-10 sm:px-8">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(255,255,255,0.08),transparent_42%)]"
        />
        <div className="relative flex w-full max-w-2xl flex-col items-center gap-6">
          <div className="text-center">
            <p className="mb-2 text-xs font-medium uppercase tracking-[0.3em] text-white/50">
              {activeChat.title}
            </p>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Meet your AI assistant
            </h1>
            <p className="mt-3 max-w-md text-sm text-white/60">
              Select a conversation or start a new chat from the sidebar.
            </p>
          </div>
          <AIChatCard
            key={activeChat.id}
            messages={activeChat.messages}
            onMessagesChange={handleMessagesChange}
          />
        </div>
      </section>
    </main>
  )
}
