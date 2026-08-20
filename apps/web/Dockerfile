FROM node:22-alpine AS builder

ENV PNPM_HOME="/pnpm" \
    PATH="$PNPM_HOME:$PATH"

WORKDIR /workspace

RUN corepack enable && corepack prepare pnpm@10.33.4 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.json .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY packages/ui/package.json packages/ui/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/ui packages/ui

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --filter web build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
