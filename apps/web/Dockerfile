# syntax=docker/dockerfile:1.7

FROM node:24-bookworm-slim AS base

WORKDIR /workspace
ENV NEXT_TELEMETRY_DISABLED=1

FROM base AS dependencies
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY apps/mobile/package.json apps/mobile/package.json
RUN --mount=type=cache,target=/root/.npm \
    npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 300000 \
    && npm ci --workspace=apps/web --no-audit --no-fund

FROM dependencies AS development
COPY apps/web apps/web
WORKDIR /workspace/apps/web
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

FROM dependencies AS build
COPY apps/web apps/web
WORKDIR /workspace/apps/web
RUN npm run build

FROM base AS production
ENV NODE_ENV=production
COPY --from=dependencies /workspace/node_modules /workspace/node_modules
COPY --from=dependencies /workspace/package.json /workspace/package.json
COPY --from=dependencies /workspace/package-lock.json /workspace/package-lock.json
COPY --from=dependencies /workspace/apps/web/package.json /workspace/apps/web/package.json
COPY --from=build /workspace/apps/web/.next /workspace/apps/web/.next
COPY --from=build /workspace/apps/web/public /workspace/apps/web/public
COPY --from=build /workspace/apps/web/next.config.ts /workspace/apps/web/next.config.ts
WORKDIR /workspace/apps/web
EXPOSE 3000
CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]
