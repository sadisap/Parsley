import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function Login() {
  const [tab, setTab] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "register") {
        await api.register(username, password);
        setTab("login");
        setError("Account created — please sign in.");
      } else {
        const token = await api.login(username, password);
        localStorage.setItem("token", token);
        navigate("/");
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>
          <span style={{ color: "var(--green)" }}>🌿</span> Parsley
        </div>
        <p style={s.tagline}>Deploy any repo in seconds.</p>

        <div style={s.tabs}>
          <button style={tab === "login" ? s.tabActive : s.tab} onClick={() => setTab("login")}>Sign in</button>
          <button style={tab === "register" ? s.tabActive : s.tab} onClick={() => setTab("register")}>Register</button>
        </div>

        <form onSubmit={handleSubmit} style={s.form}>
          <input
            style={s.input}
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            autoFocus
          />
          <input
            style={s.input}
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
          />
          {error && <p style={{ color: error.startsWith("Account") ? "var(--green)" : "var(--red)", fontSize: 13 }}>{error}</p>}
          <button style={s.btn} type="submit" disabled={loading}>
            {loading ? "..." : tab === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 },
  card: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 16, padding: "56px 48px", width: "100%", maxWidth: 460, display: "flex", flexDirection: "column", gap: 24 },
  logo: { fontSize: 28, fontWeight: 700, letterSpacing: -0.5 },
  tagline: { color: "var(--muted)", fontSize: 15 },
  tabs: { display: "flex", gap: 4, background: "var(--bg)", borderRadius: 10, padding: 4 },
  tab: { flex: 1, padding: "10px 0", background: "none", border: "none", color: "var(--muted)", borderRadius: 7, fontSize: 15, fontWeight: 500 },
  tabActive: { flex: 1, padding: "10px 0", background: "var(--surface2)", border: "none", color: "var(--text)", borderRadius: 7, fontSize: 15, fontWeight: 500 },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  input: { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 10, padding: "13px 16px", color: "var(--text)", fontSize: 15, outline: "none" },
  btn: { background: "var(--green)", color: "#000", border: "none", borderRadius: 10, padding: "14px 0", fontWeight: 700, fontSize: 15, marginTop: 4 },
};
