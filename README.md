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

### Step 3: CI builds, checks and pushes the images

**Built:** a GitHub Actions workflow. It checks out the app submodule, lints both Dockerfiles with `docker build --check`, builds each image once, starts the stack in compose from those images and runs the smoke test. On `main` it pushes them to GitHub Container Registry, tagged with this repo's commit. Each image also carries labels with this repo's commit and the app's commit, so `docker inspect` tells you exactly what's inside.

**Decision:** build once, test what ships. Compose takes the image names from `BACKEND_IMAGE` and `FRONTEND_IMAGE`, so CI tests the images it pushes instead of building fresh ones.

### Step 4: Kubernetes manifests with health checks

**Built:** manifests in [`k8s/base`](k8s/base) for PostgreSQL (one pod with its own volume), two backend pods and two frontend pods, plus a [`k8s/kind`](k8s/kind) overlay that puts the frontend on `http://127.0.0.1:8080` in a local [kind](https://kind.sigs.k8s.io/) cluster. [`scripts/deploy.sh`](scripts/deploy.sh) deploys one release (an image tag) and waits for it. CI now creates a kind cluster, deploys the images it just built and runs the smoke test through the cluster.

Every pod has three checks:

| Check | Backend | Frontend | What Kubernetes does when it fails |
|---|---|---|---|
| Startup | `/api/health`, up to 60 s | `/`, up to 60 s | Restarts the pod; the other two checks wait for it |
| Liveness | `/api/health` | `/` | Restarts the pod |
| Readiness | `/api/ready`, which needs the database | `/` | Stops sending it traffic, without a restart |

**Decisions:**
- **No database check in liveness.** If PostgreSQL goes down, restarting every backend pod wouldn't fix anything. The pods go not-ready instead and come back by themselves.
- **No unavailable pods during a rollout.** With `maxUnavailable: 0`, an old pod is only removed once its replacement is ready, so a release that never becomes ready leaves the old one serving.
- **Wait for the database in an init container.** On a fresh cluster the backend starts before PostgreSQL. Without the wait it crashes, and Kubernetes restarts it with a longer pause each time.
- **A five-second `preStop` pause.** Kubernetes stops routing to a pod and tells it to stop at about the same time. The pause lets in-flight requests finish.
- **Locked-down containers.** They run as non-root on a read-only filesystem with every Linux capability dropped. Next.js gets a small writable folder for its cache.
- **A password made inside the cluster.** The deploy script generates the database password the first time and stores it as a Kubernetes Secret, so it never exists in this repo or in CI.

**Learned:** the PostgreSQL image starts a temporary server while it creates a new database, listening only on its socket. `pg_isready` over the socket calls that "ready" a moment before it restarts, so the checks use `-h 127.0.0.1`. The compose file now does the same.

### Step 5: a failing deploy rolls back

**Built:** if a release isn't ready in time, [`scripts/deploy.sh`](scripts/deploy.sh) runs `kubectl rollout undo` on every Deployment that release changed and exits with an error. CI proves it on every push:

1. It builds a release called `bad`, whose backend crashes on startup ([`test/bad-release.Dockerfile`](test/bad-release.Dockerfile)). Its frontend is unchanged.
2. [`scripts/watch.py`](scripts/watch.py) starts calling the app through the cluster five times a second.
3. It deploys `bad`. The new backend pod never becomes ready, so the old pods keep serving. After 60 seconds the script rolls back both the backend and the frontend.
4. The job fails unless the deploy was refused, both Deployments are back on the previous images, the watcher saw no failed calls and the smoke test passes again.

**Decision:** roll back the whole release, not just the part that failed. Here the frontend went out fine, but leaving it on a release whose backend was refused would mix versions.

**Learned:** Kubernetes doesn't roll back by itself. A stuck rollout just stays stuck, with the old pods serving, until someone or something runs `kubectl rollout undo`.
