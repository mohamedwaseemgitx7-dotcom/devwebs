import { Zap } from "lucide-react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "../api/client";
import { Alert } from "../components/ui";
import { useAuth } from "../lib/auth";

/** Only same-site relative paths are allowed as post-login redirects (prevents open-redirect attacks). */
export function safeNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/products";
  return raw;
}

function AuthShell({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto mt-6 max-w-md">
      <div className="card p-8">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-white">
            <Zap className="h-6 w-6 fill-white" aria-hidden="true" />
          </span>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        {children}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { login, user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={next} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle={<>New here? <Link to={`/signup?next=${encodeURIComponent(next)}`} className="font-medium text-brand-700 underline">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <div>
          <label htmlFor="email" className="label">Email</label>
          <input id="email" type="email" autoComplete="email" required maxLength={254} className="input" value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" type="password" autoComplete="current-password" required maxLength={128} className="input" value={password}
            onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button type="submit" className="btn-primary w-full py-2.5" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </AuthShell>
  );
}

export function passwordProblems(pw: string): string[] {
  const problems: string[] = [];
  if (pw.length < 10) problems.push("at least 10 characters");
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
  if (classes < 3) problems.push("3 of: lowercase, uppercase, digits, symbols");
  return problems;
}

export function SignupPage() {
  const { signup, user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const next = safeNext(params.get("next"));
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const problems = passwordProblems(form.password);

  if (user) return <Navigate to={next} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (problems.length) {
      setError(`Password needs ${problems.join(" and ")}.`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signup(form.name.trim(), form.email.trim(), form.password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle={<>Already have one? <Link to={`/login?next=${encodeURIComponent(next)}`} className="font-medium text-brand-700 underline">Sign in</Link></>}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <Alert>{error}</Alert>}
        <div>
          <label htmlFor="name" className="label">Name</label>
          <input id="name" autoComplete="name" required maxLength={100} className="input" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label htmlFor="email" className="label">Email</label>
          <input id="email" type="email" autoComplete="email" required maxLength={254} className="input" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" type="password" autoComplete="new-password" required maxLength={128} className="input"
            aria-describedby="password-help" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <p id="password-help" className={`mt-1 text-xs ${form.password && problems.length ? "text-danger" : "text-muted"}`}>
            {form.password && !problems.length ? "Strong enough ✓" : "Use at least 10 characters with 3 of: lowercase, uppercase, digits, symbols."}
          </p>
        </div>
        <button type="submit" className="btn-primary w-full py-2.5" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
    </AuthShell>
  );
}
