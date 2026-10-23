# ClaimSense console + the three client-system APIs.
#
# Multi-stage so the runtime image carries no build toolchain: `output:
# standalone` in next.config.mjs emits a self-contained server, which is what
# makes the final stage ~180MB instead of ~1.2GB.
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev --ignore-scripts || npm install --omit=dev --ignore-scripts

FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts || npm install --ignore-scripts
COPY . .
# A DSN has to be present for the build to resolve imports, but nothing is
# queried at build time — every page is force-dynamic, because each reflects
# live claim state and none of it is safe to bake into the image.
ENV CLAIMSENSE_DB_URL=postgresql://build:build@localhost:5432/build
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3200 HOSTNAME=0.0.0.0

RUN addgroup -g 10001 -S nodejs && adduser -u 10001 -S nextjs -G nodejs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3200

# The health endpoint is unauthenticated precisely so compose can use it: a
# check that needs a credential cannot run before credentials exist.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3200/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
