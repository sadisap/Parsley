const BASE = "https://api.parsley.website";
function token() {
  return localStorage.getItem("token");
}

function headers(extra: Record<string, string> = {}) {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: headers(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  register: (username: string, password: string) =>
    req<{ message: string }>("POST", "/auth/register", { username, password }),

  login: async (username: string, password: string): Promise<string> => {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Login failed");
  }
  const data = await res.json();
  return data.access_token;
},

  projects: {
    list: () => req<Project[]>("GET", "/projects"),
    create: (name: string, repo_url: string) =>
      req<Project>("POST", "/projects", { name, repo_url }),
    deploy: (id: string) =>
      req<{ build_id: string }>("POST", `/projects/${id}/deploy`),
    getEnv: (id: string) =>
      req<Record<string, string>>("GET", `/projects/${id}/env`),
    setEnv: (id: string, env_vars: Record<string, string>) =>
      req<Record<string, string>>("PUT", `/projects/${id}/env`, { env_vars }),
  },

  builds: {
    list: (projectId: string) =>
      req<Build[]>("GET", `/projects/${projectId}/builds`),
    get: (buildId: string) =>
      req<BuildDetail>("GET", `/builds/${buildId}`),
  },

  deployments: {
    list: (projectId: string) =>
      req<Deployment[]>("GET", `/projects/${projectId}/deployments`),
  },
};

export interface Project {
  project_id: string;
  name: string;
  repo_url: string;
  subdomain: string;
  status: string;
  framework?: string;
}

export interface Build {
  build_id: string;
  status: string;
  image_tag: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface BuildDetail extends Build {
  project_id: string;
  log_output: string | null;
  log_expires_at: string | null;
}

export interface Deployment {
  deployment_id: string;
  build_id: string;
  container_id: string | null;
  status: string;
  deployed_at: string | null;
  created_at: string;
}
