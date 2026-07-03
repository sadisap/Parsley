import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Project } from "../api";

const STATUS_COLOR: Record<string, string> = {
  running: "var(--green)",
  building: "var(--yellow)",
  failed: "var(--red)",
  pending: "var(--muted)",
};

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  async function load() {
    try {
      setProjects(await api.projects.list());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const p = await api.projects.create(name, repoUrl);
      setProjects(prev => [p, ...prev]);
      setShowForm(false);
      setName(""); setRepoUrl("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleDeploy(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const { build_id } = await api.projects.deploy(id);
      navigate(`/projects/${id}?build=${build_id}`);
    } catch (e: any) {
      alert(e.message);
    }
  }

  function logout() {
    localStorage.removeItem("token");
    navigate("/login");
  }

  return (
    <div style={s.page}>
      <header style={s.header}>
        <span style={s.logo}><span style={{ color: "var(--green)" }}>🌿</span> Parsley</span>
        <button style={s.ghost} onClick={logout}>Sign out</button>
      </header>

      <main style={s.main}>
        <div style={s.topRow}>
          <h1 style={s.h1}>Projects</h1>
          <button style={s.btnGreen} onClick={() => setShowForm(v => !v)}>
            {showForm ? "Cancel" : "+ New project"}
          </button>
        </div>

        {showForm && (
          <form onSubmit={handleCreate} style={s.form}>
            <input style={s.input} placeholder="Project name" value={name} onChange={e => setName(e.target.value)} required autoFocus />
            <input style={s.input} placeholder="GitHub repo URL" value={repoUrl} onChange={e => setRepoUrl(e.target.value)} required />
            {error && <p style={{ color: "var(--red)", fontSize: 13 }}>{error}</p>}
            <button style={s.btnGreen} type="submit" disabled={creating}>{creating ? "Creating..." : "Create project"}</button>
          </form>
        )}

        {loading ? (
          <p style={{ color: "var(--muted)", marginTop: 32 }}>Loading...</p>
        ) : projects.length === 0 ? (
          <div style={s.empty}>
            <p>No projects yet.</p>
            <p style={{ color: "var(--muted)", fontSize: 14, marginTop: 8 }}>Create your first project to get started.</p>
          </div>
        ) : (
          <div style={s.grid}>
            {projects.map(p => (
              <div key={p.project_id} style={s.card} onClick={() => navigate(`/projects/${p.project_id}`)}>
                <div style={s.cardTop}>
                  <span style={s.projectName}>{p.name}</span>
                  <span style={{ ...s.badge, color: STATUS_COLOR[p.status] ?? "var(--muted)" }}>{p.status}</span>
                </div>
                <p style={s.repoUrl}>{p.repo_url}</p>
                {p.subdomain && (
                  <p style={s.subdomain}>
                    <a href={`https://${p.subdomain}.parsley.website`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} style={{ color: "var(--green)" }}>
                      {p.subdomain}.parsley.website ↗
                    </a>
                  </p>
                )}
                {p.framework && <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>{p.framework}</p>}
                <div style={{ marginTop: 16 }}>
                  <button style={s.deployBtn} onClick={e => handleDeploy(p.project_id, e)}>Deploy</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh" },
  header: { borderBottom: "1px solid var(--border)", padding: "16px 32px", display: "flex", alignItems: "center", justifyContent: "space-between" },
  logo: { fontSize: 18, fontWeight: 700 },
  ghost: { background: "none", border: "1px solid var(--border)", color: "var(--muted)", borderRadius: 8, padding: "7px 14px", fontSize: 14 },
  main: { maxWidth: 900, margin: "0 auto", padding: "40px 24px" },
  topRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 },
  h1: { fontSize: 24, fontWeight: 700 },
  btnGreen: { background: "var(--green)", color: "#000", border: "none", borderRadius: 8, padding: "9px 18px", fontWeight: 600, fontSize: 14 },
  form: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 24, display: "flex", flexDirection: "column", gap: 12, marginBottom: 32 },
  input: { background: "var(--surface2)", border: "1px solid var(--border)", borderRadius: 8, padding: "10px 14px", color: "var(--text)", fontSize: 14, outline: "none" },
  empty: { marginTop: 64, textAlign: "center", color: "var(--muted)" },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 },
  card: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20, cursor: "pointer", transition: "border-color .15s" },
  cardTop: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 },
  projectName: { fontWeight: 600, fontSize: 15 },
  badge: { fontSize: 12, fontWeight: 500, textTransform: "uppercase", letterSpacing: 0.5 },
  repoUrl: { color: "var(--muted)", fontSize: 12, wordBreak: "break-all" },
  subdomain: { fontSize: 13, marginTop: 6 },
  deployBtn: { background: "var(--surface2)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 6, padding: "6px 14px", fontSize: 13, fontWeight: 500 },
};
