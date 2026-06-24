# Parsley 🌿

Parsley takes a GitHub repository and turns it into a live deployment. It detects your framework, builds a Docker container, and serves your app on a public subdomain with HTTPS. No configuration files, no DevOps setup required.

---

## How it works

Paste a repository URL into Parsley. It clones the repo, analyses the codebase to detect the framework, port, and start command, and generates the right Dockerfile for it. The image gets built and pushed to DockerHub. A container is spun up on the server, Traefik routes a subdomain to it and provisions HTTPS automatically. Your app is live.

On every push to your main branch, Parsley picks up the GitHub webhook, rebuilds the image, and swaps the container with zero manual intervention.

---

## Supported Stacks [Initial Version]

React · Express · FastAPI · Flask · Static HTML · Django · Next.js · Nuxt.js · Vue

---

## Architecture

Parsley is built across four modules that run in sequence:

- **Build Engine** — clones the repo, detects the stack, builds and pushes the Docker image
- **Deployment Agent** — pulls the image, runs the container, handles restarts and redeploys
- **Networking** — assigns each deployment a subdomain and provisions HTTPS via Traefik and Let's Encrypt
- **Dashboard** — gives you a live view of your deployments, build status, and logs

---

## Status

Currently in active development. The MVP supports the frameworks listed above. ZIP upload, environment variable injection, and custom domain support are coming next.

---

## Contributing

Building in public. Issues and pull requests are welcome.
