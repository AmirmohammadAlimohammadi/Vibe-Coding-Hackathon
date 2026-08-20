import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"
import { Send } from "lucide-react"

import { cn } from "@workspace/ui/lib/utils"

type Message = {
  sender: "ai" | "user"
  text: string
}

type Particle = {
  left: string
  x: [number, number]
  duration: number
  delay: number
}

const INITIAL_MESSAGES: Message[] = [
  { sender: "ai", text: "👋 Hello! I’m your AI assistant." },
]

const PARTICLES: Particle[] = Array.from({ length: 20 }, (_, index) => ({
  left: `${(index * 37) % 100}%`,
  x: [((index * 53) % 200) - 100, ((index * 97) % 200) - 100],
  duration: 5 + (index % 4) * 0.75,
  delay: index * 0.5,
}))

export default function AIChatCard({ className }: { className?: string }) {
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES)
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const responseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (responseTimeout.current) {
        clearTimeout(responseTimeout.current)
      }
    }
  }, [])

  const handleSend = () => {
    const trimmedInput = input.trim()

    if (!trimmedInput) {
      return
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      { sender: "user", text: trimmedInput },
    ])
    setInput("")
    setIsTyping(true)

    responseTimeout.current = setTimeout(() => {
      setMessages((currentMessages) => [
        ...currentMessages,
        { sender: "ai", text: "🤖 This is a sample AI response." },
      ])
      setIsTyping(false)
      responseTimeout.current = null
    }, 1200)
  }

  return (
    <div
      className={cn(
        "relative h-[min(80vh,460px)] min-h-[400px] w-full max-w-[360px] overflow-hidden rounded-2xl p-[2px]",
        className
      )}
    >
      <motion.div
        aria-hidden="true"
        className="absolute inset-0 rounded-2xl border-2 border-white/20"
        animate={{ rotate: [0, 360] }}
        transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
      />

      <div className="relative flex h-full w-full flex-col overflow-hidden rounded-xl border border-white/10 bg-black/90 backdrop-blur-xl">
        <motion.div
          aria-hidden="true"
          className="absolute inset-0 bg-gradient-to-br from-gray-800 via-black to-gray-900"
          animate={{ backgroundPosition: ["0% 0%", "100% 100%", "0% 0%"] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
          style={{ backgroundSize: "200% 200%" }}
        />

        {PARTICLES.map((particle, index) => (
          <motion.div
            key={index}
            aria-hidden="true"
            className="absolute bottom-[-10%] h-1 w-1 rounded-full bg-white/10"
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

        <div className="relative z-10 border-b border-white/10 px-4 py-3">
          <h2 className="text-lg font-semibold text-white">🤖 AI Assistant</h2>
          <p className="text-xs text-white/50">Always ready to help</p>
        </div>

        <div
          aria-live="polite"
          className="relative z-10 flex flex-1 flex-col gap-3 overflow-y-auto px-4 py-3 text-sm"
        >
          {messages.map((message, index) => (
            <motion.div
              key={`${message.sender}-${index}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className={cn(
                "max-w-[80%] rounded-xl px-3 py-2 shadow-md backdrop-blur-md",
                message.sender === "ai"
                  ? "self-start bg-white/10 text-white"
                  : "self-end bg-white/30 font-semibold text-black"
              )}
            >
              {message.text}
            </motion.div>
          ))}

          {isTyping && (
            <motion.div
              aria-label="AI is typing"
              className="flex max-w-[30%] items-center gap-1 self-start rounded-xl bg-white/10 px-3 py-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 0.6, 1] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
            >
              <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-white delay-200" />
              <span className="h-2 w-2 animate-pulse rounded-full bg-white delay-400" />
            </motion.div>
          )}
        </div>

        <form
          className="relative z-10 flex items-center gap-2 border-t border-white/10 p-3"
          onSubmit={(event) => {
            event.preventDefault()
            handleSend()
          }}
        >
          <label className="sr-only" htmlFor="ai-chat-message">
            Type a message
          </label>
          <input
            id="ai-chat-message"
            className="flex-1 rounded-lg border border-white/10 bg-black/50 px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-white/50"
            placeholder="Type a message..."
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
          <button
            aria-label="Send message"
            className="rounded-lg bg-white/10 p-2 transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40"
            disabled={!input.trim()}
            type="submit"
          >
            <Send aria-hidden="true" className="h-4 w-4 text-white" />
          </button>
        </form>
      </div>
    </div>
  )
}
