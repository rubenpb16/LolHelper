# ── Etapa 1: compilar el frontend ────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# VITE_API_URL se pasa como build argument desde Railway
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Etapa 2: servir la build estática con nginx ───────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
# nginx.conf usa $PORT para que Railway/Render puedan asignar el puerto
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

EXPOSE 80

# envsubst reemplaza $PORT en la config antes de arrancar nginx
CMD ["/bin/sh", "-c", "envsubst '$PORT' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
