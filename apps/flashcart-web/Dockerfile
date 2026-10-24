# FlashCart web image: build the SPA with Node, serve it with unprivileged nginx (port 8080, non-root).
# nginx also proxies /api and /healthz to the API so the browser sees one origin (ADR-005).
# Build from apps/flashcart-web:  docker build -t flashcart-web .
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN npm run build

# nginx 1.30 stable (1.28 is end-of-life). 1.30.6 is newer than the 14-day cooldown because it fixes nginx CVEs
# (security-fix exception, ADR-004 / TS-019). Pinned by digest so rebuilds are reproducible.
FROM nginxinc/nginx-unprivileged:1.30.6-alpine3.24@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
# Apply Alpine package fixes released after the base image was built, then drop back to non-root.
USER root
RUN apk upgrade --no-cache
USER 101
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
