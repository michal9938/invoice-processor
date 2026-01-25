# Deployment Guide

## Cloud Run Deployment

### Prerequisites

1. Google Cloud Project with Cloud Build and Cloud Run APIs enabled
2. Docker image will be built and deployed to Cloud Run

### Setting Up Build-Time Environment Variables

Next.js requires `NEXT_PUBLIC_*` environment variables to be available at **build time** (not just runtime) because they are baked into the JavaScript bundle during the build process.

#### Option 1: Cloud Build Trigger Configuration (Recommended)

1. Go to Cloud Build > Triggers in the Google Cloud Console
2. Edit your trigger (or create a new one)
3. Under "Substitution variables", add:
   - `_NEXT_PUBLIC_SUPABASE_URL` = Your Supabase project URL
   - `_NEXT_PUBLIC_SUPABASE_ANON_KEY` = Your Supabase anonymous key
   - `_NEXT_PUBLIC_BACKEND_URL` = Your backend URL (usually empty string for same domain)

#### Option 2: Command Line

When triggering builds manually, pass substitutions:

```bash
gcloud builds submit \
  --substitutions=_NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co,_NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key,_NEXT_PUBLIC_BACKEND_URL=
```

#### Option 3: Using Secret Manager (For Sensitive Values)

For better security, you can use Secret Manager:

1. Create secrets:
```bash
echo -n "https://your-project.supabase.co" | gcloud secrets create next-public-supabase-url --data-file=-
echo -n "your-anon-key" | gcloud secrets create next-public-supabase-anon-key --data-file=-
```

2. Update `cloudbuild.yaml` to use secrets (requires additional configuration)

### Runtime Environment Variables

Set these in Cloud Run console under "Environment variables":

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

### Important Notes

- **Build-time vs Runtime**: `NEXT_PUBLIC_*` variables MUST be set at build time. Setting them only at runtime will not work.
- **Security**: The `NEXT_PUBLIC_SUPABASE_ANON_KEY` is safe to expose in the build (it's designed to be public), but you should still use proper access controls in Supabase.
- **Rebuild Required**: If you change `NEXT_PUBLIC_*` variables, you must rebuild and redeploy the Docker image.
