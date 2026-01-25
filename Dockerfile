# Multi-stage build for Frontend + Backend
FROM node:20-alpine AS frontend-builder

# Set working directory
WORKDIR /app/frontend

# Accept build arguments for Next.js public environment variables
# These are baked into the JavaScript bundle at build time
# Default to empty strings if not provided (will cause runtime error, but allows build to complete)
ARG NEXT_PUBLIC_SUPABASE_URL=""
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=""
ARG NEXT_PUBLIC_BACKEND_URL=""

# Set as environment variables for the build process
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL

# Copy frontend package files
COPY frontend/package*.json ./

# Install frontend dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build Next.js application (NEXT_PUBLIC_* vars are baked in here)
RUN npm run build

# Python backend stage
FROM python:3.11-slim AS backend-builder

# Set working directory
WORKDIR /app/backend

# Install system dependencies for PDF processing and compilation
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Final stage - runtime
FROM python:3.11-slim

# Install runtime dependencies including nginx, net-tools, and PDF processing tools
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    nginx \
    net-tools \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Next.js runtime
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin
COPY backend/ ./backend/

# Copy frontend build from builder
COPY --from=frontend-builder /app/frontend/.next ./frontend/.next
COPY --from=frontend-builder /app/frontend/public ./frontend/public
COPY --from=frontend-builder /app/frontend/package*.json ./frontend/
COPY --from=frontend-builder /app/frontend/node_modules ./frontend/node_modules
COPY --from=frontend-builder /app/frontend/next.config.ts ./frontend/
COPY --from=frontend-builder /app/frontend/tsconfig.json ./frontend/
COPY --from=frontend-builder /app/frontend/postcss.config.mjs ./frontend/
COPY --from=frontend-builder /app/frontend/eslint.config.mjs ./frontend/
COPY --from=frontend-builder /app/frontend/app ./frontend/app
COPY --from=frontend-builder /app/frontend/components ./frontend/components
COPY --from=frontend-builder /app/frontend/lib ./frontend/lib

# Copy startup script and nginx config
COPY start.sh ./
COPY nginx.conf /etc/nginx/nginx.conf
RUN chmod +x start.sh

# Create necessary directories
RUN mkdir -p backend/logs backend/tmp/uploads

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD sh -c 'curl -fsS http://localhost:${PORT:-8080}/health || exit 1'

# Start both services
CMD ["./start.sh"]
