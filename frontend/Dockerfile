FROM node:20-alpine AS base

WORKDIR /app
COPY package*.json ./
RUN npm ci

# ── dev : Vite dev server avec hot-reload ─────────────────────
FROM base AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ── builder : compilation TypeScript + Vite ───────────────────
FROM base AS builder
COPY . .
RUN npm run build

# ── prod : nginx sert le build statique ───────────────────────
FROM nginx:alpine AS prod
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
