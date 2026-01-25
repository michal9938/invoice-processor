#!/bin/bash
set -e

# Get port from environment (Cloud Run sets PORT)
PORT=${PORT:-8080}
BACKEND_PORT=8000
FRONTEND_PORT=3000

echo "=== Starting Invoice Processor Services ==="
echo "PORT: $PORT"
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"

# Frontend uses relative URLs for API calls (same domain)

# Generate nginx config with dynamic PORT
echo "Generating nginx configuration for port $PORT..."
cat > /etc/nginx/nginx.conf <<EOF
events {
    worker_connections 1024;
}

http {
    client_max_body_size 50m;

    upstream backend {
        server localhost:$BACKEND_PORT;
    }

    upstream frontend {
        server localhost:$FRONTEND_PORT;
    }

    server {
        listen $PORT;
        server_name _;

        # Proxy API requests to backend
        location /api/ {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }

        # Proxy docs/redoc/openapi.json to backend
        location ~ ^/(docs|redoc|openapi\.json) {
            proxy_pass http://backend;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        # Health check
        location = /health {
            proxy_pass http://backend/health;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        # All other requests go to frontend
        location / {
            proxy_pass http://frontend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade \$http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_cache_bypass \$http_upgrade;
        }
    }
}
EOF

# Test nginx configuration
nginx -t || {
    echo "ERROR: nginx configuration test failed!"
    exit 1
}

# Start backend in background
echo "Starting FastAPI backend on port $BACKEND_PORT..."
cd /app
uvicorn backend.main:app --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!

# Wait for backend to be ready (with shorter intervals)
echo "Waiting for backend to start..."
for i in {1..60}; do
    if curl -fsS http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        echo "✓ Backend is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "✗ Backend failed to start after 60 attempts"
        exit 1
    fi
    sleep 1
done

# Start frontend
echo "Starting Next.js frontend on port $FRONTEND_PORT..."
cd /app/frontend
PORT=$FRONTEND_PORT npm start &
FRONTEND_PID=$!

# Wait for frontend to be ready (with shorter intervals)
echo "Waiting for frontend to start..."
for i in {1..60}; do
    if curl -f http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        echo "✓ Frontend is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "✗ Frontend failed to start after 60 attempts"
        exit 1
    fi
    sleep 1
done

# Start nginx as reverse proxy (foreground)
echo "Starting nginx reverse proxy on port $PORT..."
nginx -g 'daemon off;' &
NGINX_PID=$!

# Wait a moment for nginx to start
sleep 2

# Verify nginx is listening on the correct port
if ! netstat -tuln | grep -q ":$PORT "; then
    echo "✗ ERROR: nginx is not listening on port $PORT"
    exit 1
fi

echo "=== All services are running! ==="
echo "Backend PID: $BACKEND_PID on port $BACKEND_PORT"
echo "Frontend PID: $FRONTEND_PID on port $FRONTEND_PORT"
echo "Nginx PID: $NGINX_PID on port $PORT"
echo "Application ready at http://localhost:$PORT"

# Function to handle shutdown (Cloud Run sends SIGTERM)
cleanup() {
    echo "Received shutdown signal, shutting down services..."
    kill -TERM $BACKEND_PID $FRONTEND_PID $NGINX_PID 2>/dev/null || true
    # Wait for processes to terminate gracefully
    wait $BACKEND_PID $FRONTEND_PID $NGINX_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for nginx to exit (it runs in foreground with daemon off)
# If nginx exits, we exit too
wait $NGINX_PID
EXIT_CODE=$?

# If nginx exited, kill other services
cleanup
exit $EXIT_CODE
