# syntax=docker/dockerfile:1
# The serviceops-workbench web app. The build context is the app's frontend folder:
#   docker build -f docker/frontend.Dockerfile -t serviceops-frontend app/frontend

FROM node:26.13.1-alpine AS build
WORKDIR /src
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Next.js writes the backend address into the build output, so it's a build
# argument, not a runtime setting. "backend" is the service name in both
# compose and Kubernetes.
ARG API_URL=http://backend:8000
RUN API_URL="$API_URL" BUILD_STANDALONE=1 npm run build


FROM node:26.13.1-alpine
WORKDIR /srv
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Only the standalone server and the static files it serves. No node_modules
# from the build stage, no source.
COPY --from=build --chown=1000:1000 /src/.next/standalone ./
COPY --from=build --chown=1000:1000 /src/.next/static ./.next/static

# The image's "node" user, by number for the same reason as the backend.
USER 1000
EXPOSE 3000
CMD ["node", "server.js"]
