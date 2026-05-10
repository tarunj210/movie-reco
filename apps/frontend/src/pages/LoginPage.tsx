import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/auth";

export default function LoginPage() {
  const navigate = useNavigate();

  const [userId, setUserIdInput] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = useMemo(() => {
    return (
      userId.trim().length > 0 &&
      password.trim().length > 0 &&
      !isSubmitting
    );
  }, [userId, password, isSubmitting]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!canSubmit) return;

    try {
      setIsSubmitting(true);

      await login({
        user_id: userId.trim(),
        password: password.trim(),
      });

      navigate("/dashboard");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-neutral-950 px-4 text-neutral-100">
      {/* Cinematic background */}
      <BackgroundDecor />

      <div className="relative z-10 grid w-full max-w-5xl grid-cols-1 gap-10 md:grid-cols-2 md:items-center">
        {/* Left: brand / pitch */}
        <div className="hidden md:block">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-red-500 to-amber-500 text-xl font-black text-neutral-950 shadow-lg shadow-red-500/20">
              M
            </div>
            <div>
              <p className="text-lg font-bold tracking-tight">MovieReco</p>
              <p className="text-xs text-neutral-500">Personalized cinema</p>
            </div>
          </div>

          <h2 className="text-4xl font-black leading-tight tracking-tight md:text-5xl">
            Find your{" "}
            <span className="bg-gradient-to-r from-red-400 to-amber-400 bg-clip-text text-transparent">
              next favorite
            </span>{" "}
            film.
          </h2>

          <p className="mt-4 max-w-md text-neutral-400">
            Hybrid recommendations refined with your own words. Sign in to pick
            up where you left off.
          </p>

          <ul className="mt-8 space-y-3 text-sm text-neutral-300">
            <Feature>Hybrid collaborative + content-based ranking</Feature>
            <Feature>Refine results with natural language prompts</Feature>
            <Feature>Learns from every rating, click, and dislike</Feature>
          </ul>
        </div>

        {/* Right: auth card */}
        <div className="rounded-3xl border border-neutral-800 bg-neutral-900/70 p-8 shadow-2xl shadow-black/60 backdrop-blur-xl">
          {/* Mobile-only brand */}
          <div className="mb-6 flex items-center gap-3 md:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-red-500 to-amber-500 font-black text-neutral-950">
              M
            </div>
            <p className="text-base font-bold tracking-tight">MovieReco</p>
          </div>

          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-tight text-neutral-100">
              Sign in
            </h1>
            <span className="text-xs font-medium uppercase tracking-widest text-neutral-500">
              Welcome back
            </span>
          </div>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label
                htmlFor="userId"
                className="block text-xs font-semibold uppercase tracking-wider text-neutral-400"
              >
                User ID
              </label>
              <input
                id="userId"
                value={userId}
                onChange={(e) => setUserIdInput(e.target.value)}
                className="mt-2 w-full rounded-xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 text-neutral-100 placeholder-neutral-600 transition focus:border-red-500/60 focus:outline-none focus:ring-2 focus:ring-red-500/20"
                placeholder="e.g. 574"
                inputMode="numeric"
                autoComplete="username"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold uppercase tracking-wider text-neutral-400"
              >
                Password
              </label>
              <div className="relative mt-2">
                <input
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type={showPw ? "text" : "password"}
                  className="w-full rounded-xl border border-neutral-800 bg-neutral-950/60 px-4 py-3 pr-14 text-neutral-100 placeholder-neutral-600 transition focus:border-red-500/60 focus:outline-none focus:ring-2 focus:ring-red-500/20"
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  aria-label={showPw ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-2 flex items-center px-3 text-neutral-500 transition hover:text-neutral-200"
                >
                  {showPw ? (
                    <EyeOffIcon className="h-5 w-5" />
                  ) : (
                    <EyeIcon className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-red-900/60 bg-red-950/40 px-3 py-2.5 text-sm text-red-300">
                <WarnIcon className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              disabled={!canSubmit}
              className="group relative w-full overflow-hidden rounded-xl bg-gradient-to-r from-red-600 to-red-500 py-3 font-semibold text-white shadow-lg shadow-red-600/20 transition hover:from-red-500 hover:to-red-400 disabled:cursor-not-allowed disabled:from-neutral-800 disabled:to-neutral-800 disabled:text-neutral-500 disabled:shadow-none"
            >
              {isSubmitting ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Signing in…
                </span>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-neutral-500">
            By signing in you agree to keep watching great movies.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ Subcomponents ----------------------------- */

function BackgroundDecor() {
  return (
    <>
      {/* Radial gradient glows */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-40 h-[480px] w-[480px] rounded-full bg-red-600/20 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-40 -right-40 h-[520px] w-[520px] rounded-full bg-amber-500/15 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,rgba(239,68,68,0.08),transparent_60%)]"
      />

      {/* Subtle film-grain noise via SVG */}
      <svg
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full opacity-[0.05] mix-blend-overlay"
      >
        <filter id="noise">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" />
        </filter>
        <rect width="100%" height="100%" filter="url(#noise)" />
      </svg>
    </>
  );
}

function Feature({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400">
        <CheckIcon className="h-3 w-3" />
      </span>
      <span>{children}</span>
    </li>
  );
}

function CheckIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      aria-hidden
    >
      <path d="M5 12l5 5L20 7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function EyeIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      aria-hidden
    >
      <path
        d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      aria-hidden
    >
      <path
        d="M3 3l18 18M10.6 6.1A10.6 10.6 0 0112 6c6.5 0 10 7 10 7a18 18 0 01-3.2 4.2M6.7 6.7A18 18 0 002 12s3.5 7 10 7c1.7 0 3.2-.4 4.5-1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9.9 9.9a3 3 0 004.2 4.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WarnIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden
    >
      <path
        d="M12 9v4m0 4h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
