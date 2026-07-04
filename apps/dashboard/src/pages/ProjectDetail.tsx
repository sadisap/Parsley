import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, Build, Deployment, Project } from "../api";

const WS_BASE = "ws://187.127.175.133:8000";

const STATUS_COLOR: Record<string, string> = {
  running: "var(--green)",
  success: "var(--green)",
  building: "var(--yellow)",
  queued: "var(--yellow)",
  failed: "var(--red)",
  pending: "var(--muted)",
};

export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [project, setProject] = useState<Project | null>(null);
  const [builds, setBuilds] = useState<Build[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [activeBuildId, setActiveBuildId] = useState<string | null>(searchParams.get("build"));
  const [logs, setLogs] = useState<string[]>([]);
  const [logDone, setLogDone] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // load project + builds + deployments
  useEffect(() => {
    if (!id) return;
    api.projects.list().then(ps => setProject(ps.find(p => p.project_id === id) ?? null));
    api.builds.list(id).then(setBuilds);
    api.deployments.list(id).then(setDeployments);
  }, [id]);

  // open websocket when a build is selected
  useEffect(() => {
    if (!activeBuildId) return;
    setLogs([]);
    setLogDone(false);

    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(`${WS_BASE}/ws/builds/${activeBuildId}/logs`);
    wsRef.current = ws;

    ws.onmessage = e => {
      const line: string = e.data;
      if (line === "__done__") { setLogDone(true); return; }
      if (line === "__ping__") return;
      setLogs(prev => [...prev, line]);
    };

    return () => ws.close();
  }, [activeBuildId]);

  // auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  async function handleDeploy() {
    if (!id) return;
    try {
      const { build_id } = await api.projects.deploy(id);
      const fresh = await api.builds.list(id);
      setBuilds(fresh);
      setActiveBuildId(build_id);
    } catch (e: any) {
      alert(e.message);
    }
  }

  function selectBuild(b: Build) {
    setActiveBuildId(b.build_id);
  }

  return (
    <div style={s.page}>
      <header style={s.header}>
        <button style={s.back} onClick={() => navigate("/")}>← Projects</button>
        <span style={s.logo}><span style={{ color: "var(--green)" }}>🌿</span> Parsley</span>
      </header>

      <main style={s.main}>
        {project && (
          <div style={s.projectCard}>
            <div style={s.projectTop}>
              <div>
                <h1 style={s.h1}>{project.name}</h1>
                <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>{project.repo_url}</p>
                {project.subdomain && (
                  <a href={`https://${project.subdomain}.parsley.website`} target="_blank" rel="noreferrer" style={{ color: "var(--green)", fontSize: 13 }}>
                    {project.subdomain}.parsley.website ↗
                  </a>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ color: STATUS_COLOR[project.status] ?? "var(--muted)", fontSize: 13, fontWeight: 500 }}>{project.status}</span>
                <button style={s.btnGreen} onClick={handleDeploy}>Deploy</button>
              </div>
            </div>
          </div>
        )}

        <div style={s.cols}>
          {/* builds list */}
          <div style={s.sidebar}>
            <h2 style={s.h2}>Builds</h2>
            {builds.length === 0 ? (
              <p style={{ color: "var(--muted)", fontSize: 13 }}>No builds yet.</p>
            ) : (
              builds.map(b => (
                <div
                  key={b.build_id}
                  style={{ ...s.buildRow, ...(activeBuildId === b.build_id ? s.buildRowActive : {}) }}
                  onClick={() => selectBuild(b)}
                >
                  <span style={{ color: STATUS_COLOR[b.status] ?? "var(--muted)", fontSize: 12, fontWeight: 600, textTransform: "uppercase" }}>{b.status}</span>
                  <span style={{ color: "var(--muted)", fontSize: 11 }}>{b.build_id.slice(0, 8)}</span>
                  <span style={{ color: "var(--muted)", fontSize: 11 }}>{b.created_at ? new Date(b.created_at).toLocaleString() : ""}</span>
                </div>
              ))
            )}

            <h2 style={{ ...s.h2, marginTop: 28 }}>Deployments</h2>
            {deployments.length === 0 ? (
              <p style={{ color: "var(--muted)", fontSize: 13 }}>No deployments yet.</p>
            ) : (
              deployments.map(d => (
                <div key={d.deployment_id} style={s.buildRow}>
                  <span style={{ color: STATUS_COLOR[d.status] ?? "var(--muted)", fontSize: 12, fontWeight: 600, textTransform: "uppercase" }}>{d.status}</span>
                  <span style={{ color: "var(--muted)", fontSize: 11 }}>{d.deployed_at ? new Date(d.deployed_at).toLocaleString() : "—"}</span>
                </div>
              ))
            )}
          </div>

          {/* log panel */}
          <div style={s.logPanel}>
            <div style={s.logHeader}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>
                {activeBuildId ? `Build ${activeBuildId.slice(0, 8)}` : "Select a build to view logs"}
              </span>
              {activeBuildId && (
                <span style={{ fontSize: 12, color: logDone ? "var(--green)" : "var(--yellow)" }}>
                  {logDone ? "● Done" : "● Live"}
                </span>
              )}
            </div>
            <div style={s.logBody}>
              {logs.length === 0 && activeBuildId && !logDone && (
                <span style={{ color: "var(--muted)" }}>Waiting for logs...</span>
              )}
              {logs.map((line, i) => (
                <div key={i} style={s.logLine}>{line}</div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh" },
  header: { borderBottom: "1px solid var(--border)", padding: "16px 32px", display: "flex", alignItems: "center", justifyContent: "space-between" },
  back: { background: "none", border: "none", color: "var(--muted)", fontSize: 14, cursor: "pointer" },
  logo: { fontSize: 18, fontWeight: 700 },
  main: { maxWidth: 1100, margin: "0 auto", padding: "32px 24px" },
  projectCard: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "20px 24px", marginBottom: 28 },
  projectTop: { display: "flex", alignItems: "flex-start", justifyContent: "space-between" },
  h1: { fontSize: 22, fontWeight: 700 },
  h2: { fontSize: 13, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 12 },
  btnGreen: { background: "var(--green)", color: "#000", border: "none", borderRadius: 8, padding: "9px 18px", fontWeight: 600, fontSize: 14 },
  cols: { display: "grid", gridTemplateColumns: "240px 1fr", gap: 20, alignItems: "start" },
  sidebar: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 16 },
  buildRow: { padding: "10px 12px", borderRadius: 8, cursor: "pointer", display: "flex", flexDirection: "column", gap: 3, marginBottom: 4 },
  buildRowActive: { background: "var(--surface2)", border: "1px solid var(--border)" },
  logPanel: { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden", display: "flex", flexDirection: "column" },
  logHeader: { padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" },
  logBody: { padding: 16, fontFamily: "var(--mono)", fontSize: 12, lineHeight: 1.7, overflowY: "auto", maxHeight: 520, minHeight: 200 },
  logLine: { whiteSpace: "pre-wrap", wordBreak: "break-all" },
};
