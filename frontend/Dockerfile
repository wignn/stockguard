# Multi-stage Dockerfile for Next.js 16 with latest Bun
FROM oven/bun:latest AS base
WORKDIR /app

# Stage 1: Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# Stage 2: Build the standalone Next.js bundle
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

ARG API_ORIGIN=http://api:8000
ENV API_ORIGIN=${API_ORIGIN}

RUN mkdir -p /app/public
RUN bun run build

# Stage 3: Minimal production runner
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    API_ORIGIN=http://api:8000

# Use non-root bun user provided by official oven/bun image
USER bun

# Copy static assets and standalone server
COPY --from=builder --chown=bun:bun /app/public ./public
COPY --from=builder --chown=bun:bun /app/.next/standalone ./
COPY --from=builder --chown=bun:bun /app/.next/static ./.next/static

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD bun -e 'fetch("http://localhost:3000").then(r => process.exit(r.status < 500 ? 0 : 1)).catch(() => process.exit(1))'

CMD ["bun", "server.js"]
