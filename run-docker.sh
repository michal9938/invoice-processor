#!/bin/bash

# Helper script to run the project locally with Docker

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Patent Generator - Docker Local Setup${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Creating .env.example template..."
    cat > .env.example << EOF
# Database Configuration
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/dbname

# Security
SECRET_KEY=your-secret-key-change-in-production

# API Keys
ANTHROPIC_API_KEY=your-claude-api-key
SENDGRID_API_KEY=your-sendgrid-api-key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-key
SUPABASE_STORAGE_SOURCE_BUCKET=sources
SUPABASE_STORAGE_PATENT_BUCKET=patents
SUPABASE_STORAGE_FIGURES_BUCKET=figures

# Frontend
NEXT_PUBLIC_BACKEND_URL=
EOF
    echo -e "${YELLOW}Please create a .env file with your configuration!${NC}"
    echo "You can copy .env.example and fill in your values."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running!${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

# Parse command line arguments
COMMAND=${1:-up}

case $COMMAND in
    build)
        echo -e "${GREEN}Building Docker image...${NC}"
        docker build -t patent-generator .
        echo -e "${GREEN}Build complete!${NC}"
        ;;
    up)
        echo -e "${GREEN}Starting containers...${NC}"
        docker-compose up -d
        echo -e "${GREEN}Containers started!${NC}"
        echo ""
        echo "Application is available at:"
        echo "  Frontend: http://localhost:8080"
        echo "  API Docs: http://localhost:8080/docs"
        echo ""
        echo "View logs with: ./run-docker.sh logs"
        ;;
    down)
        echo -e "${GREEN}Stopping containers...${NC}"
        docker-compose down
        echo -e "${GREEN}Containers stopped!${NC}"
        ;;
    logs)
        docker-compose logs -f
        ;;
    restart)
        echo -e "${GREEN}Restarting containers...${NC}"
        docker-compose restart
        echo -e "${GREEN}Containers restarted!${NC}"
        ;;
    shell)
        echo -e "${GREEN}Opening shell in container...${NC}"
        docker exec -it patent-generator /bin/bash
        ;;
    clean)
        echo -e "${YELLOW}Cleaning up...${NC}"
        docker-compose down -v
        docker rmi patent-generator 2>/dev/null || true
        echo -e "${GREEN}Cleanup complete!${NC}"
        ;;
    *)
        echo "Usage: ./run-docker.sh [command]"
        echo ""
        echo "Commands:"
        echo "  build    - Build the Docker image"
        echo "  up       - Start containers (default)"
        echo "  down     - Stop containers"
        echo "  logs     - View container logs"
        echo "  restart  - Restart containers"
        echo "  shell    - Open shell in container"
        echo "  clean    - Remove containers and images"
        exit 1
        ;;
esac
