import { Children, isValidElement, type ReactNode, useState } from "react"
import { Check, Copy } from "lucide-react"
import Markdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "@workspace/ui/lib/utils"

type MarkdownMessageProps = {
  children: string
  className?: string
}

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") {
    return String(node)
  }
  if (Array.isArray(node)) {
    return node.map(nodeText).join("")
  }
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return nodeText(node.props.children)
  }
  return ""
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const [copied, setCopied] = useState(false)
  const codeElement = Children.toArray(children).find(isValidElement)
  const className = isValidElement<{ className?: string }>(codeElement)
    ? codeElement.props.className
    : undefined
  const language = className?.match(/language-([^\s]+)/)?.[1]
  const code = nodeText(children).replace(/\n$/, "")

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div
      className="my-4 max-w-full overflow-hidden rounded-xl border border-slate-700 bg-[#0b1020] text-slate-100 shadow-lg"
      dir="ltr"
    >
      <div className="flex h-10 items-center justify-between border-b border-white/10 bg-white/[0.04] px-3 text-xs text-slate-400">
        <span className="font-mono">{language ?? "code"}</span>
        <button
          aria-label="کپی کد"
          className="flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-white/10 hover:text-white"
          onClick={() => void copyCode()}
          type="button"
        >
          {copied ? (
            <Check
              aria-hidden="true"
              className="h-3.5 w-3.5 text-emerald-400"
            />
          ) : (
            <Copy aria-hidden="true" className="h-3.5 w-3.5" />
          )}
          <span>{copied ? "کپی شد" : "کپی"}</span>
        </button>
      </div>
      <pre className="max-w-full overflow-x-auto p-4 text-left font-mono text-[13px] leading-6">
        {children}
      </pre>
    </div>
  )
}

const components: Components = {
  a: ({ children, ...props }) => (
    <a
      {...props}
      className="font-medium text-[#405ac8] underline decoration-[#7184df]/40 underline-offset-4 transition-colors hover:text-[#273fa8] dark:text-[#a7f2e5] dark:hover:text-white"
      rel="noreferrer noopener"
      target="_blank"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-r-4 border-[#6679df] bg-[#5b6cff]/5 py-2 pr-4 pl-3 text-[#4d5d8c] dark:border-[#a7f2e5] dark:bg-white/5 dark:text-white/70">
      {children}
    </blockquote>
  ),
  code: ({ children, className, ...props }) => {
    const isBlock =
      Boolean(className?.includes("language-")) ||
      String(children).endsWith("\n")
    return (
      <code
        {...props}
        className={cn(
          className,
          isBlock
            ? "font-mono text-slate-100"
            : "mx-0.5 rounded-md bg-[#5265cf]/10 px-1.5 py-0.5 font-mono text-[0.9em] text-[#3448a8] dark:bg-white/10 dark:text-[#baf8ed]"
        )}
        dir="ltr"
      >
        {children}
      </code>
    )
  },
  h1: ({ children }) => (
    <h1 className="mt-1 mb-4 text-xl font-bold text-[#172654] dark:text-white">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 text-lg font-bold text-[#172654] dark:text-white">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 mb-2 text-base font-semibold text-[#25376d] dark:text-white/90">
      {children}
    </h3>
  ),
  hr: () => <hr className="my-5 border-[#cdd6ef] dark:border-white/15" />,
  li: ({ children }) => <li className="my-1 pr-1">{children}</li>,
  ol: ({ children }) => (
    <ol className="my-3 list-decimal space-y-1 pr-6 marker:font-semibold marker:text-[#5265cf] dark:marker:text-[#a7f2e5]">
      {children}
    </ol>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-7 first:mt-0 last:mb-0">{children}</p>
  ),
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  strong: ({ children }) => (
    <strong className="font-bold text-[#1a2959] dark:text-white">
      {children}
    </strong>
  ),
  table: ({ children }) => (
    <div className="my-4 max-w-full overflow-x-auto rounded-xl border border-[#cdd6ef] dark:border-white/15">
      <table className="w-full min-w-[420px] border-collapse text-right text-sm">
        {children}
      </table>
    </div>
  ),
  td: ({ children }) => (
    <td className="border-t border-[#dbe3f5] px-3 py-2.5 align-top dark:border-white/10">
      {children}
    </td>
  ),
  th: ({ children }) => (
    <th className="bg-[#5265cf]/10 px-3 py-2.5 font-semibold text-[#1f316a] dark:bg-white/10 dark:text-white">
      {children}
    </th>
  ),
  ul: ({ children }) => (
    <ul className="my-3 list-disc space-y-1 pr-6 marker:text-[#5265cf] dark:marker:text-[#a7f2e5]">
      {children}
    </ul>
  ),
}

export function MarkdownMessage({ children, className }: MarkdownMessageProps) {
  return (
    <div
      className={cn(
        "max-w-full min-w-0 text-right [overflow-wrap:anywhere]",
        className
      )}
    >
      <Markdown
        components={components}
        disallowedElements={["img"]}
        remarkPlugins={[remarkGfm]}
        skipHtml
      >
        {children}
      </Markdown>
    </div>
  )
}
