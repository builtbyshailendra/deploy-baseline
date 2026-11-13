# deploy-baseline

**Takes [serviceops-workbench](https://github.com/builtbyshailendra/serviceops-workbench) from "runs on my laptop" to container images, a one-command local stack and a Kubernetes deployment with health checks and rollback.**

> Personal learning project. Every person, team and request in the app is made up.

The app lives in [`app/`](app) as a git submodule pinned to one commit, so this repo always says exactly which version of the app it deploys.

## Build log

### Step 1: Dockerfiles for the backend and the frontend

**Built:** one Dockerfile per part of the app, kept in [`docker/`](docker) next to its own ignore file. The backend image is Python 3.12 slim with only the runtime packages and the `app` package. The frontend image is built in two stages: the first installs everything and builds Next.js as a standalone server, the second copies only that server and its static files. Both run as a fixed, unprivileged user id.

**Decision:** the Dockerfiles live here, not in the app repo. The app stays about the app; this repo is about running it. BuildKit reads `<name>.Dockerfile.dockerignore` next to each Dockerfile, so the ignore files can live here too.

**Learned:** Next.js writes the backend address into the build output, so `API_URL` is a build argument, not something to set when the container starts. Its default, `http://backend:8000`, is the service name used in both compose and Kubernetes.

### Step 2: one command for the whole app

**Built:** [`compose.yaml`](compose.yaml) runs PostgreSQL, the backend and the frontend. `docker compose up --build` builds both images and starts everything in order: the backend waits until PostgreSQL accepts connections, and the frontend waits until the backend is ready. Only the frontend and backend ports are published, and only on `127.0.0.1`. [`scripts/smoke.py`](scripts/smoke.py) walks one request from raised to done through the frontend, so a single run checks the page, the `/api` proxy, the backend and the database together.

**Decision:** the backend's health check in compose calls `/api/ready`, not `/api/health`, so "healthy" means it can reach the database, not just that the process is up.
