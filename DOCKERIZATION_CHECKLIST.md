# Dockerization & Google Cloud Deployment Checklist

## 📋 Information You Need Before Dockerizing

### 1. **Project Structure**
- ✅ **Frontend**: Next.js 16.1.4 app in `/frontend` directory
- ✅ **Backend**: FastAPI app in `/backend` directory
- ✅ **Backend Dockerfile**: Already exists at `backend/Dockerfile`
- ❌ **Frontend Dockerfile**: Needs to be created

### 2. **Backend Configuration** ✅

#### Port & Host
- **Port**: `8080` (configurable via `PORT` env var)
- **Host**: `0.0.0.0` (for container networking)

#### Required Environment Variables (Backend)
From `backend/.env`:

**Supabase Configuration:**
- `SUPABASE_URL` - Your Supabase project URL (with trailing slash)
- `SUPABASE_ANON_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `SUPABASE_PROJECT_ID` - Your Supabase project ID
- `SUPABASE_STORAGE_BUCKET` - Storage bucket name (default: `invoice_files`)

**Microsoft Graph API (for email polling):**
- `GRAPH_TENANT_ID` - Azure AD tenant ID
- `GRAPH_CLIENT_ID` - Azure AD client ID
- `GRAPH_CLIENT_SECRET` - Azure AD client secret
- `INVOICE_MAIL_ADDRESS` - Email address to poll for invoices

**OpenAI Configuration:**
- `OPENAI_API_KEY` - OpenAI API key for LLM-based invoice extraction

**Application Settings:**
- `PORT` - Server port (default: `8080`)
- `HOST` - Server host (default: `0.0.0.0`)
- `MAX_EMAILS_PER_RUN` - Max emails per polling run (default: `50`)
- `POLL_INTERVAL_MINUTES` - Email polling interval (default: `3`)
- `ENABLE_BACKGROUND_POLLING` - Set to `False` for Cloud Run with Cloud Scheduler
- `MAX_PDF_SIZE_MB` - Max PDF file size (default: `10`)
- `SUPPORTED_EXTENSIONS` - Supported file extensions (default: `.pdf`)
- `PRICE_TOLERANCE_PERCENT` - Price validation tolerance (default: `5.0`)

#### System Dependencies (Backend)
The backend Dockerfile already includes:
- Tesseract OCR (for future OCR features)
- Poppler utils (for PDF processing)

### 3. **Frontend Configuration** ⚠️

#### Required Environment Variables (Frontend)
From code analysis:

**Supabase Configuration:**
- `NEXT_PUBLIC_SUPABASE_URL` - Supabase project URL (public, exposed to browser)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Supabase anonymous key (public, exposed to browser)

**Backend API Connection:**
- ⚠️ **MISSING**: No environment variable found for backend API URL
- The frontend currently connects directly to Supabase, not the backend API
- You may need to add: `NEXT_PUBLIC_API_URL` if frontend needs to call backend endpoints

#### Build Configuration
- **Node Version**: Not specified in package.json (should be defined)
- **Build Command**: `next build`
- **Start Command**: `next start`
- **Port**: Next.js default is `3000` (should be configurable via `PORT` env var)

### 4. **Architecture Decisions Needed**

#### A. **Frontend-Backend Communication**
- Currently, frontend connects directly to Supabase
- Backend processes invoices via background tasks
- **Question**: Do you need frontend to call backend API endpoints? If yes, you'll need:
  - `NEXT_PUBLIC_API_URL` environment variable
  - API proxy configuration in Next.js

#### B. **Deployment Strategy on Google Cloud**

**Option 1: Cloud Run (Recommended for Serverless)**
- ✅ Backend: Already configured for Cloud Run (port 8080, health check endpoint)
- ✅ Frontend: Can deploy as Cloud Run service or Cloud Build + Cloud Run
- **Pros**: Auto-scaling, pay-per-use, easy deployment
- **Cons**: Cold starts, 60-minute timeout limit

**Option 2: GKE (Google Kubernetes Engine)**
- Better for long-running processes
- More control over resources
- **Pros**: No cold starts, better for background tasks
- **Cons**: More complex setup, higher minimum costs

**Option 3: App Engine**
- Simpler than GKE, more features than Cloud Run
- **Pros**: Managed platform, easy deployment
- **Cons**: Less flexible than Cloud Run

#### C. **Background Tasks**
- Backend has email polling and invoice processing orchestrator
- `ENABLE_BACKGROUND_POLLING=False` recommended for Cloud Run
- Use Cloud Scheduler to call `/internal/poll-emails` endpoint periodically
- **Action Needed**: Set up Cloud Scheduler job pointing to your Cloud Run service

### 5. **Docker Configuration Requirements**

#### Backend Dockerfile ✅
- Already exists and looks good
- Uses Python 3.11-slim
- Installs system dependencies
- Exposes port 8080

#### Frontend Dockerfile ❌
**Needs to be created with:**
- Node.js base image (specify version, e.g., `node:20-alpine`)
- Multi-stage build (build stage + production stage)
- Copy `package.json` and `package-lock.json`
- Run `npm ci --only=production` for production
- Copy application code
- Build Next.js app: `npm run build`
- Expose port (configurable, default 3000)
- Start command: `npm start`

#### Docker Compose (Optional for Local Testing)
- Already exists at root level
- Currently only has backend service
- **Action**: Add frontend service to docker-compose.yml

### 6. **Google Cloud Specific Requirements**

#### A. **Container Registry/Artifact Registry**
- Decide: Container Registry (older) or Artifact Registry (newer, recommended)
- Set up repository for storing Docker images
- Configure authentication

#### B. **Service Account & Permissions**
- Service account for Cloud Run services
- Permissions for:
  - Cloud Run deployment
  - Secret Manager (if using for env vars)
  - Cloud Scheduler (for email polling)
  - Cloud Storage (if using for file storage)

#### C. **Secrets Management**
- **Option 1**: Cloud Secret Manager (recommended)
  - Store sensitive env vars in Secret Manager
  - Reference secrets in Cloud Run service configuration
- **Option 2**: Environment variables in Cloud Run
  - Less secure, but simpler
  - Good for non-sensitive config

#### D. **Networking**
- **CORS Configuration**: Backend allows all origins (`allow_origins=["*"]`)
  - ⚠️ **Security**: Update for production to allow only your frontend domain
- **Internal Communication**: If frontend needs to call backend:
  - Use Cloud Run service URLs
  - Or set up VPC connector for private networking

#### E. **Health Checks**
- ✅ Backend has `/health` endpoint
- Frontend should have health check endpoint (Next.js doesn't have one by default)
- Configure Cloud Run health checks

### 7. **Build & Deployment Process**

#### Backend Build
```bash
# Build image
docker build -t gcr.io/PROJECT_ID/invoice-backend:latest ./backend

# Push to registry
docker push gcr.io/PROJECT_ID/invoice-backend:latest

# Deploy to Cloud Run
gcloud run deploy invoice-backend \
  --image gcr.io/PROJECT_ID/invoice-backend:latest \
  --platform managed \
  --region us-central1 \
  --port 8080 \
  --allow-unauthenticated
```

#### Frontend Build
```bash
# Build image
docker build -t gcr.io/PROJECT_ID/invoice-frontend:latest ./frontend

# Push to registry
docker push gcr.io/PROJECT_ID/invoice-frontend:latest

# Deploy to Cloud Run
gcloud run deploy invoice-frontend \
  --image gcr.io/PROJECT_ID/invoice-frontend:latest \
  --platform managed \
  --region us-central1 \
  --port 3000 \
  --allow-unauthenticated
```

### 8. **Missing Information to Gather**

1. **Node.js Version**: What Node.js version should frontend use? (Check your local version: `node --version`)
2. **Frontend Port**: Should frontend use port 3000 or be configurable?
3. **API Communication**: Does frontend need to call backend API? If yes, what endpoints?
4. **Domain/URLs**: 
   - What will be your production domain?
   - Backend Cloud Run URL?
   - Frontend Cloud Run URL?
5. **Environment**: 
   - Production Supabase credentials
   - Production Microsoft Graph credentials
   - Production OpenAI API key
6. **Google Cloud Project**: 
   - Project ID
   - Preferred region (e.g., `us-central1`, `europe-west1`)
   - Billing account enabled

### 9. **Next Steps**

1. ✅ Review this checklist
2. ⚠️ Create frontend Dockerfile
3. ⚠️ Update backend CORS to allow only frontend domain
4. ⚠️ Add frontend service to docker-compose.yml (for local testing)
5. ⚠️ Set up Google Cloud project and enable required APIs
6. ⚠️ Create Artifact Registry repositories
7. ⚠️ Set up Secret Manager for sensitive credentials
8. ⚠️ Create Cloud Run services
9. ⚠️ Configure Cloud Scheduler for email polling
10. ⚠️ Set up CI/CD pipeline (Cloud Build recommended)

---

## Quick Reference: Environment Variables Summary

### Backend (.env)
```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_PROJECT_ID=
SUPABASE_STORAGE_BUCKET=invoice_files
GRAPH_TENANT_ID=
GRAPH_CLIENT_ID=
GRAPH_CLIENT_SECRET=
INVOICE_MAIL_ADDRESS=
OPENAI_API_KEY=
PORT=8080
HOST=0.0.0.0
ENABLE_BACKGROUND_POLLING=False
```

### Frontend (.env.local or build-time)
```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=  # If needed
PORT=3000  # Optional
```

