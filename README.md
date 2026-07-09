<img width="1858" height="863" alt="image" src="https://github.com/user-attachments/assets/f344d346-6d46-42b8-944b-36d982e52b81" />


# Parsley 🌿

A **self-hosted deployment platform**. Paste a GitHub repository URL and get a live HTTPS subdomain back. It handles Dockerfiles, server configuration, DevOps .

Most deployment tools are either too simple (static sites only) or too complex (Kubernetes, cloud consoles, IAM roles). Parsley sits in between: containerised deployments, automatic framework detection, and a clean UI, all running entirely on a VPS you control.

---

## How it works

Paste a URL. Parsley clones the repository and reads the files to figure out the framework, port, and start command. It generates the right Dockerfile, builds a container image, and pushes it to Docker Hub. The image gets pulled onto the server and run behind Traefik, which assigns a subdomain and provisions HTTPS automatically via Let's Encrypt.

Push to `main` and the GitHub webhook triggers the same pipeline again. Also includes rollback mechanism to ensure the previous version keeps running in case the new build fails.

**Live at** [home.parsley.website](https://home.parsley.website/) · Dashboard at [app.parsley.website](https://app.parsley.website/)

---

## Architecture

Parsley is built across four modules that run in sequence:

<img width="500" height="300" alt="parsley_architecture" src="https://github.com/user-attachments/assets/8e911096-08c8-44c5-aeaf-f0b88859c6d6" />

- **Build Engine** — clones the repo, detects the stack, builds and pushes the Docker image
- **Deployment Agent** — pulls the image, runs the container, handles restarts and redeploys
- **Networking** — assigns each deployment a subdomain and provisions HTTPS via Traefik and Let's Encrypt
- **Dashboard** — gives you a live view of your deployments, build status, and logs

---

## Supported Stacks [Initial Version]

React · Vue · Next.js · Nuxt · Express · FastAPI · Flask · Django · Static HTML

## Built with

Python · FastAPI · PostgreSQL · SQLAlchemy · Docker · Traefik · Paramiko · React · TypeScript · Vite

Four modules in sequence: 
a **build engine** that clones, detects, and builds; 
a **deploy agent** that runs containers over SSH with automatic rollback; 
**networking** via Traefik for subdomain routing and TLS; 
and a **React dashboard** with live log streaming over WebSocket.

---
## Running locally

**Prerequisites:** Python 3.11+, Docker, Node 20+

```bash
git clone https://github.com/BStok/Parsley
cd Parsley
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
cd apps/api && pip install -r requirements.txt
uvicorn apps.api.src.main:app --reload
```

For the dashboard:
```bash
cd apps/dashboard && npm install && npm run dev
```

Fill in `.env` with your Docker Hub credentials and VPS details before triggering a deploy.

---

## Status

Core pipeline is working clone, detect, build, push, deploy, rollback, HTTPS. The MVP supports the stacks listed above.
Next version will focus on broader framework support, environment variable injection per project, and managed database connections.

---

## Contributing

Building in public. Issues and pull requests are welcome.

## Contributors

- Sadkishya - https://github.com/sadisap
- Shravani - https://github.com/Shravaniiii

## 

<img width="417" height="421" align="center" alt="image" src="https://github.com/user-attachments/assets/cf3a78e6-30bc-4072-9a76-76a6985c33df" />

