import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { Send } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

export type ChatMessage = {
  sender: "ai" | "user"
  text: string
}

type AIChatCardProps = {
  className?: string
  messages?: ChatMessage[]
  onMessagesChange?: (messages: ChatMessage[]) => void
}

type Particle = {
  left: string
  x: [number, number]
  duration: number
  delay: number
}

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    sender: "ai",
    text: "👋 سلام! من دستیار هوشمند لیارا هستم. چطور می‌توانم کمکتان کنم؟",
  },
]

const PARTICLES: Particle[] = Array.from({ length: 20 }, (_, index) => ({
  left: `${(index * 37) % 100}%`,
  x: [((index * 53) % 200) - 100, ((index * 97) % 200) - 100],
  duration: 5 + (index % 4) * 0.75,
  delay: index * 0.5,
}))

export default function AIChatCard({
  className,
  messages: controlledMessages,
  onMessagesChange,
}: AIChatCardProps) {
  const [localMessages, setLocalMessages] =
    useState<ChatMessage[]>(INITIAL_MESSAGES)
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const responseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)
  const messages = controlledMessages ?? localMessages
  const messagesRef = useRef<ChatMessage[]>(messages)

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    return () => {
      if (responseTimeout.current) {
        clearTimeout(responseTimeout.current)
      }
    }
  }, [])

  const appendMessage = (message: ChatMessage) => {
    const nextMessages = [...messagesRef.current, message]
    messagesRef.current = nextMessages

    if (onMessagesChange) {
      onMessagesChange(nextMessages)
      return
    }

    setLocalMessages(nextMessages)
  }

  const handleSend = () => {
    const trimmedInput = input.trim()

    if (!trimmedInput) {
      return
    }

    appendMessage({ sender: "user", text: trimmedInput })
    setInput("")
    setIsTyping(true)

    responseTimeout.current = setTimeout(() => {
      appendMessage({
        sender: "ai",
        text: "🤖 این یک پاسخ نمونه از دستیار لیارا است.",
      })
      setIsTyping(false)
      responseTimeout.current = null
    }, 1200)
  }

  return (
    <div
      dir="rtl"
      className={cn(
        "relative flex h-full min-h-0 w-full max-w-[720px] overflow-hidden rounded-[1.4rem] p-[2px]",
        className
      )}
    >
      <motion.div
        aria-hidden="true"
        className="absolute inset-0 rounded-[1.4rem] border-2 border-[#6c7dff]/50"
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
      />

      <div className="relative flex h-full w-full flex-col overflow-hidden rounded-[1.3rem] border border-[#dbe4f6] bg-white/95 shadow-2xl shadow-[#6a78b8]/20 backdrop-blur-xl dark:border-white/15 dark:bg-[#0d1738]/95 dark:shadow-[#4052a6]/20">
        <motion.div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-br from-[#eef3ff] via-white to-[#e5ebff] dark:from-[#243b82] dark:via-[#0d1738] dark:to-[#111a42]"
          animate={{ backgroundPosition: ["0% 0%", "100% 100%", "0% 0%"] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          style={{ backgroundSize: "200% 200%" }}
        />

        {PARTICLES.map((particle, index) => (
          <motion.div
            key={index}
            aria-hidden="true"
            className="absolute bottom-[-10%] h-1 w-1 rounded-full bg-[#5067da]/20 dark:bg-[#a7f2e5]/25"
            animate={{ y: ["0%", "-140%"], x: particle.x, opacity: [0, 1, 0] }}
            transition={{
              duration: particle.duration,
              repeat: Infinity,
              delay: particle.delay,
              ease: "easeInOut",
            }}
            style={{ left: particle.left }}
          />
        ))}

        <div className="relative z-10 border-b border-[#dbe4f6] px-5 py-4 dark:border-white/10">
          <h2 className="text-lg font-semibold text-[#16224a] dark:text-white">دستیار هوشمند</h2>
          <p className="text-xs text-[#6e7a9b] dark:text-white/50">همیشه آماده پاسخگویی</p>
        </div>

        <div
          aria-live="polite"
          dir="ltr"
          className="relative z-10 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 py-4 text-sm"
        >
          {messages.map((message, index) => (
            <motion.div
              key={`${message.sender}-${index}`}
              dir="rtl"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className={cn(
                "min-w-0 max-w-[82%] break-words whitespace-pre-wrap px-4 py-2.5 text-right leading-7 shadow-md backdrop-blur-md [overflow-wrap:anywhere]",
                message.sender === "ai"
                  ? "self-start rounded-2xl bg-[#eef2ff] text-[#26366a] dark:bg-white/10 dark:text-white"
                  : "self-end rounded-2xl bg-[#5b6cff] font-semibold text-white dark:bg-[#a7f2e5] dark:text-[#0b1739]"
              )}
            >
              {message.text}
            </motion.div>
          ))}

          {isTyping && (
            <motion.div
              aria-label="دستیار در حال نوشتن است"
              className="flex max-w-[30%] items-center gap-1 self-start rounded-2xl bg-[#eef2ff] px-4 py-3 dark:bg-white/10"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 0.6, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
            >
              <span className="h-2 w-2 animate-pulse rounded-full bg-[#5b6cff] dark:bg-[#a7f2e5]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-[#5b6cff] delay-200 dark:bg-[#a7f2e5]" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-[#5b6cff] delay-400 dark:bg-[#a7f2e5]" />
            </motion.div>
          )}
        </div>

        <form
          className="relative z-10 flex items-center gap-2 border-t border-[#dbe4f6] p-4 dark:border-white/10"
          onSubmit={(event) => {
            event.preventDefault()
            handleSend()
          }}
        >
          <label className="sr-only" htmlFor="ai-chat-message">
            پیام خود را بنویسید
          </label>
          <textarea
            id="ai-chat-message"
            className="max-h-32 min-h-11 flex-1 resize-none overflow-y-auto rounded-xl border border-[#cbd6ef] bg-white/70 px-4 py-2.5 text-sm leading-6 text-[#16224a] placeholder:text-[#8290b2] focus:outline-none focus:ring-2 focus:ring-[#5265cf]/40 dark:border-white/15 dark:bg-white/10 dark:text-white dark:placeholder:text-white/40 dark:focus:ring-[#a7f2e5]/60"
            enterKeyHint="send"
            placeholder="پیام خود را بنویسید..."
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                handleSend()
              }
            }}
          />
          <button
            aria-label="ارسال پیام"
            className="rounded-xl bg-[#5265cf] p-2.5 text-white transition-colors hover:bg-[#4052b8] disabled:cursor-not-allowed disabled:opacity-40 dark:bg-[#a7f2e5] dark:text-[#0b1739] dark:hover:bg-[#c8fff5]"
            disabled={!input.trim()}
            type="submit"
          >
            <Send aria-hidden="true" className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
