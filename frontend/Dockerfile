# ---- dev: Vite dev server with hot reload (used by docker-compose) ----
FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
EXPOSE 5173
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]

# ---- build: static production bundle ----
FROM dev AS build
RUN npx vite build

# ---- prod: nginx serving the bundle and proxying /api to the backend ----
FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
