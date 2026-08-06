# syntax=docker/dockerfile:1
#
# Multi-stage: build with the full node_modules tree, ship only the
# Next.js "standalone" output (see next.config.mjs's `output: "standalone"`)
# — a self-contained server bundle with just the traced-in dependencies,
# not the whole node_modules directory.
#
# Build from apps/web itself (unlike the Python services, this app has no
# workspace-sibling dependency on the rest of the repo):
#   docker build -f apps/web/Dockerfile -t staffstream/web apps/web
#
# NEXT_PUBLIC_* vars are inlined into the client bundle at BUILD time, so
# the public API origin has to be a build arg, not a runtime env var —
# unlike every other service's image, this one isn't identical regardless
# of which environment it's deployed to.
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_BASE_URL=https://vartaverse.in
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
ARG NEXT_PUBLIC_API_BASE_URL=https://vartaverse.in
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
# The standalone server binds to process.env.HOSTNAME, which container
# runtimes commonly auto-set to the container ID — without this override
# it silently listens only on that container's own IP, not every
# interface, and nothing outside the container (healthcheck, a reverse
# proxy) can reach it.
ENV HOSTNAME=0.0.0.0

COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public

# node:20-slim already ships a uid-1000 "node" user — reuse it rather
# than colliding on the same uid with a new one.
USER node

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
    CMD node -e "fetch('http://localhost:3000/login').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
