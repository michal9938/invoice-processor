# Invoice Control System - FastAPI Backend

A comprehensive invoice processing system built with FastAPI that handles invoice intake via email polling, PDF parsing, validation against price records, and mismatch resolution.

## Features

- **Email Polling Service**: Automatically polls Microsoft Graph API for invoice emails with PDF attachments
- **PDF Parsing**: Extracts structured data from PDF invoices using pdfplumber (non-OCR)
- **Scanned PDF Detection**: Flags scanned PDFs for future OCR processing
- **Invoice Validation**: Validates invoice lines against buying_price_records and supplier_sku_mappings
- **Mismatch Resolution**: Handles price acceptance, disputes, and audit logging
- **Manual Upload**: Web interface for manual invoice upload
- **Audit Logging**: Comprehensive logging of all price changes and disputes


test scripts : 
py test_email_polling.py

## Architecture

```
invoice/
├── backend/
│   ├── api/v1/endpoints/     # API endpoints
│   ├── services/              # Business logic services
│   ├── schemas/pydantic/      # Pydantic schemas
│   ├── core/                 # Configuration and logging
│   ├── main.py               # FastAPI app entry point
│   ├── Dockerfile            # Docker configuration
│   └── requirements.txt      # Python dependencies
├── docker-compose.yml        # Docker Compose configuration
└── README.md
```

## Prerequisites

- Python 3.11+
- Supabase account with configured database and storage
- Microsoft Azure AD app registration for Graph API access
- Docker (optional, for containerized deployment)

## Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd invoice
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```


### 3. Database Setup

Ensure your Supabase database has the following tables:
- `invoices`
- `invoice_lines`
- `buying_price_records`
- `supplier_sku_mappings`
- `products`
- `invoice_files`
- `audit_log`
- `users`
- `suppliers` (referenced but may need to be created)

### 5. Run the application

#### Development mode:


**Option 2: Run using main.py directly:**
```bash
cd backend
python main.py
```

**Option 3: Run directly from backend directory:**
```bash
cd backend
# Windows CMD:
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
# Windows PowerShell:
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
# Linux/Mac:
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

Note: The path is automatically configured in `main.py`, so no PYTHONPATH setup is needed.

#### Using Docker(recommended):

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8080`

## API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## API Endpoints

### Invoice Endpoints

- `POST /api/v1/invoices/` - Create a new invoice manually
- `GET /api/v1/invoices/` - List all invoices
- `GET /api/v1/invoices/{invoice_id}` - Get invoice with lines
- `POST /api/v1/invoices/upload` - Upload invoice PDF manually
- `POST /api/v1/invoices/poll-emails` - Manually trigger email polling
- `GET /api/v1/invoices/{invoice_id}/lines` - Get invoice lines

### Validation Endpoints

- `POST /api/v1/validation/invoice/{invoice_id}` - Validate an invoice
- `POST /api/v1/validation/accept-price` - Accept a new price
- `POST /api/v1/validation/dispute` - Dispute an invoice
- `GET /api/v1/validation/invoice/{invoice_id}/status` - Get validation status

## Workflow

1. **Email Polling**: The service periodically checks the configured inbox for invoice emails
2. **PDF Download**: PDF attachments are downloaded and stored in Supabase storage
3. **Metadata Extraction**: Invoice metadata (supplier, invoice number, date) is extracted and stored
4. **PDF Parsing**: The PDF is parsed to extract line items (SKU, quantity, price, total)
5. **Validation**: Each line is validated against buying_price_records and supplier_sku_mappings
6. **Mismatch Resolution**: Discrepancies can be resolved by accepting new prices or disputing invoices
7. **Audit Logging**: All actions are logged in the audit_log table

## Services

### Email Polling Service (`backend/services/email_polling.py`)
- Polls Microsoft Graph API for unread emails with PDF attachments
- Downloads PDFs and stores them in Supabase storage
- Creates invoice records with extracted metadata
- Handles email deduplication

### PDF Parser Service (`backend/services/pdf_parser.py`)
- Detects if PDF is scanned or text-based
- Extracts structured data from text-based PDFs using pdfplumber
- Flags scanned PDFs for future OCR processing
- Stores parsed invoice lines in the database

### Validation Service (`backend/services/validation_service.py`)
- Validates invoice lines against price records
- Compares expected vs invoiced values with configurable tolerance
- Flags mismatches and updates invoice status
- Logs validation results in audit_log

### Mismatch Resolution Service (`backend/services/mismatch_resolution.py`)
- Handles price acceptance (creates new price records)
- Manages invoice disputes
- Closes old price records when new prices are accepted
- Comprehensive audit logging

## Future Enhancements

- **OCR Integration**: Process scanned PDFs using OCR (Tesseract/Adobe OCR)
- **Supplier-Specific Parsers**: Custom parsers for different supplier invoice formats
- **Email Templates**: Automated email generation for supplier disputes
- **Webhook Support**: Real-time notifications for invoice processing events
- **Advanced Analytics**: Reporting and analytics dashboard

## Google Cloud Run Deployment

### Prerequisites
- Google Cloud SDK installed and configured
- Docker installed
- Google Cloud project with Cloud Run API enabled

### Deployment Steps

1. **Build and Deploy to Cloud Run:**

```bash
gcloud run deploy invoice-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 10 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars "ENABLE_BACKGROUND_POLLING=False,POLL_INTERVAL_MINUTES=3"
```

**Or set environment variables via Cloud Run Console:**
- `ENABLE_BACKGROUND_POLLING=False` - Disables background polling (use Cloud Scheduler)
- `POLL_INTERVAL_MINUTES=3` - Polling interval in minutes (must match Cloud Scheduler)
- Set all other required environment variables from `env.example`

2. **Create Cloud Scheduler Job for Email Polling:**

```bash
# Calculate schedule from POLL_INTERVAL_MINUTES (e.g., 3 minutes = */3 * * * *)
gcloud scheduler jobs create http poll-emails-job \
  --location=us-central1 \
  --schedule="*/3 * * * *" \
  --uri="https://your-service-url.run.app/internal/poll-emails" \
  --http-method=POST \
  --time-zone="UTC"
```

**For authenticated endpoint (recommended for production):**

```bash
# First, grant Cloud Scheduler service account permission
gcloud run services add-iam-policy-binding invoice-api \
  --region=us-central1 \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/run.invoker

# Create job with OIDC authentication
gcloud scheduler jobs create http poll-emails-job \
  --location=us-central1 \
  --schedule="*/3 * * * *" \
  --uri="https://your-service-url.run.app/internal/poll-emails" \
  --http-method=POST \
  --oidc-service-account-email=PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --oidc-token-audience=https://your-service-url.run.app \
  --time-zone="UTC"
```

Replace `PROJECT_NUMBER` with your Google Cloud project number.

3. **Verify the Setup:**

```bash
# Check Cloud Run service
gcloud run services describe invoice-api --region=us-central1

# Test the polling endpoint manually
curl -X POST https://your-service-url.run.app/internal/poll-emails

# Check Cloud Scheduler job
gcloud scheduler jobs describe poll-emails-job --location=us-central1
```

### Polling Modes

- **Cloud Run with Cloud Scheduler** (Recommended):
  - Set `ENABLE_BACKGROUND_POLLING=False`
  - Service can scale to zero
  - Cloud Scheduler calls `/internal/poll-emails` endpoint at intervals
  - Cost-effective for production

- **Local/Development with Background Polling**:
  - Set `ENABLE_BACKGROUND_POLLING=True`
  - Service polls automatically in background
  - Better for local development and testing

### Schedule Format Reference

Common schedules based on `POLL_INTERVAL_MINUTES`:
- `1` minute: `* * * * *`
- `3` minutes: `*/3 * * * *`
- `5` minutes: `*/5 * * * *`
- `15` minutes: `*/15 * * * *`
- `30` minutes: `*/30 * * * *`

## Notes

- The PDF parser uses basic pattern matching and may need enhancement for specific invoice formats
- Supplier-specific parsers can be added to improve parsing accuracy
- OCR functionality is prepared but not yet implemented
- Email polling runs via Cloud Scheduler on Cloud Run or automatically in background for local/dev
- All price changes are tracked in the audit_log for compliance

## License

[Your License Here]

