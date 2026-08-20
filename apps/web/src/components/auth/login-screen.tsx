import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import {
  ArrowLeft,
  LoaderCircle,
  LockKeyhole,
  Mail,
  Moon,
  ShieldCheck,
  Sun,
} from "lucide-react"

import { useTheme } from "@/components/theme-provider"
import { StarfieldBackground } from "@/components/ui/starfield-background"
import {
  ApiError,
  requestEmailCode,
  type AuthSession,
  verifyEmailCode,
} from "@/lib/api"

type LoginScreenProps = {
  onAuthenticated: (session: AuthSession) => void
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message
  }
  return "خطایی رخ داد. لطفاً دوباره تلاش کنید."
}

export function LoginScreen({ onAuthenticated }: LoginScreenProps) {
  const { theme, setTheme } = useTheme()
  const [email, setEmail] = useState("")
  const [code, setCode] = useState("")
  const [step, setStep] = useState<"email" | "code">("email")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")
  const [resendAfter, setResendAfter] = useState(0)

  useEffect(() => {
    if (resendAfter <= 0) {
      return undefined
    }
    const timer = window.setInterval(() => {
      setResendAfter((current) => Math.max(0, current - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [resendAfter])

  const sendCode = async () => {
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      setError("ایمیل خود را وارد کنید.")
      return
    }

    setIsSubmitting(true)
    setError("")
    try {
      const response = await requestEmailCode(normalizedEmail)
      setEmail(normalizedEmail)
      setStep("code")
      setResendAfter(response.retry_after)
    } catch (requestError) {
      setError(errorMessage(requestError))
    } finally {
      setIsSubmitting(false)
    }
  }

  const verifyCode = async () => {
    if (!/^\d{6}$/.test(code)) {
      setError("کد تایید باید ۶ رقم باشد.")
      return
    }

    setIsSubmitting(true)
    setError("")
    try {
      onAuthenticated(await verifyEmailCode(email, code))
    } catch (verifyError) {
      setError(errorMessage(verifyError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main
      dir="rtl"
      className="relative flex min-h-svh items-center justify-center overflow-hidden bg-[#06091d] px-4 py-8 text-white"
    >
      <StarfieldBackground />
      <button
        aria-label="تغییر پوسته"
        className="fixed right-4 top-4 z-30 flex h-11 w-11 items-center justify-center rounded-xl border border-white/15 bg-[#111c45]/80 text-[#a7f2e5] shadow-lg shadow-black/20 backdrop-blur-md transition hover:bg-[#1b2a5b]"
        onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        type="button"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>

      <div className="relative z-10 grid w-full max-w-5xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <motion.section
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          className="order-2 text-center lg:order-1 lg:text-right"
        >
          <a
            className="mx-auto mb-7 flex h-12 w-28 items-center justify-center rounded-2xl bg-gradient-to-br from-[#62e4d1] to-[#6575ff] px-2 shadow-xl shadow-[#4f76ff]/30 lg:mx-0"
            href="https://liara.ir/"
            rel="noreferrer"
            target="_blank"
          >
            <img
              alt="لیارا"
              className="h-8 w-auto"
              src="https://liara.ir/assets/images/liara-logo.svg"
            />
          </a>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-[#8b9cff]/20 bg-[#6575ff]/10 px-4 py-2 text-xs text-[#bec8ff] backdrop-blur-md">
            <ShieldCheck className="h-4 w-4 text-[#75ead8]" />
            ورود امن، بدون نیاز به رمز عبور
          </div>
          <h1 className="text-4xl font-black leading-tight tracking-tight sm:text-5xl">
            دستیار هوشمند
            <span className="block bg-gradient-to-l from-[#75ead8] to-[#8f9cff] bg-clip-text text-transparent">
              زیرساخت لیارا
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-sm leading-8 text-white/65 lg:mx-0 sm:text-base">
            با ایمیل خود وارد شوید تا گفتگوهایتان همیشه ذخیره بماند و پاسخ‌های دقیق مبتنی بر مستندات لیارا دریافت کنید.
          </p>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.08 }}
          className="order-1 overflow-hidden rounded-[1.75rem] border border-white/15 bg-[#0d1738]/90 p-[1px] shadow-2xl shadow-[#4052a6]/20 backdrop-blur-2xl lg:order-2"
        >
          <div className="rounded-[1.7rem] bg-gradient-to-br from-[#1b2d67]/80 via-[#0d1738]/95 to-[#111a42]/95 p-6 sm:p-8">
            <div className="mb-7 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#a7f2e5] text-[#0b1739] shadow-lg shadow-[#a7f2e5]/15">
                {step === "email" ? <Mail className="h-5 w-5" /> : <LockKeyhole className="h-5 w-5" />}
              </div>
              <div>
                <h2 className="text-xl font-bold">
                  {step === "email" ? "ورود یا ثبت‌نام" : "تایید ایمیل"}
                </h2>
                <p className="mt-1 text-xs text-white/50">
                  {step === "email" ? "فقط با ایمیل، سریع و ساده" : `کد ارسال‌شده به ${email}`}
                </p>
              </div>
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault()
                void (step === "email" ? sendCode() : verifyCode())
              }}
            >
              {step === "email" ? (
                <div>
                  <label className="mb-2 block text-xs font-medium text-white/65" htmlFor="login-email">
                    آدرس ایمیل
                  </label>
                  <div className="relative">
                    <Mail className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/35" />
                    <input
                      id="login-email"
                      autoComplete="email"
                      autoFocus
                      className="h-13 w-full rounded-2xl border border-white/15 bg-white/[0.07] px-11 text-left text-sm text-white outline-none transition placeholder:text-white/30 focus:border-[#8d9bff]/60 focus:ring-4 focus:ring-[#6575ff]/10"
                      dir="ltr"
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="name@example.com"
                      type="email"
                      value={email}
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="mb-2 block text-xs font-medium text-white/65" htmlFor="login-code">
                    کد تایید ۶ رقمی
                  </label>
                  <input
                    id="login-code"
                    autoComplete="one-time-code"
                    autoFocus
                    className="h-16 w-full rounded-2xl border border-white/15 bg-white/[0.07] px-4 text-center text-2xl font-bold tracking-[0.55em] text-white outline-none transition placeholder:text-white/20 focus:border-[#75ead8]/60 focus:ring-4 focus:ring-[#75ead8]/10"
                    dir="ltr"
                    inputMode="numeric"
                    maxLength={6}
                    onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                    placeholder="------"
                    value={code}
                  />
                </div>
              )}

              {error && (
                <p className="mt-4 rounded-xl border border-red-400/20 bg-red-400/10 px-3 py-2 text-xs leading-6 text-red-200">
                  {error}
                </p>
              )}

              <button
                className="mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-l from-[#5b6cff] to-[#35cfc5] text-sm font-bold text-[#101a3d] shadow-xl shadow-[#2a4e9a]/30 transition hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowLeft className="h-4 w-4" />
                )}
                {step === "email" ? "ارسال کد ورود" : "تایید و ورود"}
              </button>
            </form>

            {step === "code" && (
              <div className="mt-5 flex items-center justify-between text-xs">
                <button
                  className="text-white/55 transition hover:text-white"
                  onClick={() => {
                    setStep("email")
                    setCode("")
                    setError("")
                  }}
                  type="button"
                >
                  ویرایش ایمیل
                </button>
                <button
                  className="text-[#a7f2e5] disabled:text-white/30"
                  disabled={resendAfter > 0 || isSubmitting}
                  onClick={() => void sendCode()}
                  type="button"
                >
                  {resendAfter > 0 ? `ارسال مجدد تا ${resendAfter} ثانیه` : "ارسال مجدد کد"}
                </button>
              </div>
            )}
          </div>
        </motion.section>
      </div>
    </main>
  )
}
