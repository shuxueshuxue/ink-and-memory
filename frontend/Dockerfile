# [Input] Consume frontend package.json/package-lock.json/source tree, nginx template, and runtime entrypoint.
# [Output] Build the Vite SPA and serve it at the nginx root.
# [Pos] deployment image spec in frontend/
# [Sync] 2026-06-12: add configurable npm mirror build arg for faster China builds.
# [Sync] 2026-06-14: pass VITE_PUBLIC_SITE_URL into Vite build for static SEO metadata.
# [Sync] 2026-06-15: remove /ink-and-memory/ deployment prefix; copy build output to nginx root.
# [Sync] 2026-07-20: cap builder heap via NODE_OPTIONS, install from the committed
#                    lockfile with `npm ci`, and skip the `tsc -b` full type-check
#                    (already covered by CI on ample-memory runners) to reduce the
#                    image build's memory footprint. The mermaid/tiptap/ai-sdk
#                    dependency graph still needs a ~1G Node heap for `vite build`
#                    alone (measured minimum, see frontend/.folder.md), which
#                    leaves no headroom on a 1G-RAM host: pair this with
#                    `deploy/remote-ssh/setup-swap.sh` (wired into `deploy.sh deploy`)
#                    so the build survives instead of being OOM-killed.
# [Sync] 2026-07-20: Vite 8 (rolldown/Rust bundler) cuts the build's peak RSS
#                    from ~1.25GB to ~605MB, so the default builder heap drops
#                    from 1024MB to 512MB and the build finishes comfortably on
#                    a 1G-RAM host without swap thrashing.

ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG VITE_PUBLIC_SITE_URL=http://localhost/
ARG NODE_BUILD_MAX_OLD_SPACE_MB=512

# ── Stage 1: build ──────────────────────────────────────────────────────────
FROM node:22-alpine AS builder
ARG NPM_REGISTRY
ARG VITE_PUBLIC_SITE_URL
ARG NODE_BUILD_MAX_OLD_SPACE_MB
ENV VITE_PUBLIC_SITE_URL="${VITE_PUBLIC_SITE_URL}"
ENV NODE_OPTIONS="--max-old-space-size=${NODE_BUILD_MAX_OLD_SPACE_MB}"

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm ci

COPY . .
RUN npm run build:docker

# ── Stage 2: serve ──────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Custom entrypoint renders nginx proxy fallback and browser runtime API config.
COPY nginx.conf.template /etc/nginx/templates/ink.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
