# Deployment Guide

## Cloud Run Deployment

### Prerequisites

1. Google Cloud Project with Cloud Build and Cloud Run APIs enabled
2. Docker image will be built and deployed to Cloud Run

### Environment Variables

Set these in Cloud Run console under "Environment variables":

**Backend Variables:**
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_PROJECT_ID`
- `SUPABASE_STORAGE_BUCKET`
- `GRAPH_TENANT_ID`
- `GRAPH_CLIENT_ID`
- `GRAPH_CLIENT_SECRET`
- `INVOICE_MAIL_ADDRESS`
- `OPENAI_API_KEY`
- `PORT=8080`
- `HOST=0.0.0.0`
- `MAX_EMAILS_PER_RUN=5`
- `POLL_INTERVAL_MINUTES=90`
- `ENABLE_BACKGROUND_POLLING=false`

**Frontend Variables (if needed at runtime):**
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
