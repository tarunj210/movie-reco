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
    return userId.trim().length > 0 && password.trim().length > 0 && !isSubmitting;
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
      const message =
        err instanceof Error ? err.message : "Login failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-8">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold text-slate-900">Sign in</h1>
            <span className="text-xs font-medium text-slate-500">MovieReco</span>
          </div>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                User ID
              </label>
              <input
                value={userId}
                onChange={(e) => setUserIdInput(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400"
                placeholder="e.g. 574"
                inputMode="numeric"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                Password
              </label>
              <div className="mt-1 relative">
                <input
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type={showPw ? "text" : "password"}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 pr-12 text-slate-900 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400"
                  placeholder="Enter password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="absolute inset-y-0 right-2 px-3 text-xs font-medium text-slate-600 hover:text-slate-900"
                >
                  {showPw ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              disabled={!canSubmit}
              className="w-full rounded-xl bg-slate-900 text-white py-2.5 font-medium hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}