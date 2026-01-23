"""
FastAPI application main entry point
Sets up the FastAPI app, includes routers, and handles startup/shutdown events
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.logging import logger
from backend.api.v1.api import api_router
from backend.services.email_polling import email_polling_service
from backend.services.pdf_parser import pdf_parser_service
from backend.services.validation_service import validation_service
from backend.supabase_client import supabase_client
from uuid import UUID


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    Handles background tasks like email polling (if enabled)
    For Cloud Run with Cloud Scheduler, set ENABLE_BACKGROUND_POLLING=False
    """
    # Startup
    logger.info("Starting Invoice Control System API")
    logger.info(f"Supabase URL: {settings.SUPABASE_URL}")
    logger.info(f"Email polling interval: {settings.POLL_INTERVAL_MINUTES} minutes")
    
    orchestration_task = None
    polling_task = None
    
    async def process_received_invoices_batch() -> int:
        """Process all invoices with status='received' in batch"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            result = invoices_table.select("id").eq("status", "received").limit(50).execute()
            
            if not result.data:
                return 0
            
            logger.info(f"Processing batch of {len(result.data)} received invoices for parsing")
            processed_count = 0
            
            for invoice in result.data:
                invoice_id = UUID(invoice["id"])
                try:
                    await pdf_parser_service.parse_invoice(invoice_id)
                    processed_count += 1
                    logger.info(f"Successfully parsed invoice {invoice_id}")
                except Exception as e:
                    logger.error(f"Failed to parse invoice {invoice_id}: {e}")
                    # Continue processing other invoices even if one fails
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing received invoices batch: {e}")
            return 0
    
    async def process_parsed_invoices_batch() -> int:
        """Process all invoices with status='parsed' in batch"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            result = invoices_table.select("id").eq("status", "parsed").limit(50).execute()
            
            if not result.data:
                return 0
            
            logger.info(f"Processing batch of {len(result.data)} parsed invoices for validation")
            processed_count = 0
            
            for invoice in result.data:
                invoice_id = UUID(invoice["id"])
                try:
                    await validation_service.validate_invoice(invoice_id)
                    processed_count += 1
                    logger.info(f"Successfully validated invoice {invoice_id}")
                except Exception as e:
                    logger.error(f"Failed to validate invoice {invoice_id}: {e}")
                    # Continue processing other invoices even if one fails
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing parsed invoices batch: {e}")
            return 0
    
    async def invoice_processing_orchestrator():
        """
        Orchestrated pipeline: Poll emails → Parse all received → Validate all parsed
        Runs in sequence to ensure smooth processing of batches
        """
        while True:
            try:
                # Step 1: Poll emails (only if background polling is enabled)
                if settings.ENABLE_BACKGROUND_POLLING:
                    try:
                        await email_polling_service.poll_and_process_emails()
                        logger.info("Email polling completed")
                    except Exception as e:
                        logger.error(f"Email polling error: {e}")
                
                # Step 2: Process all received invoices (parse them)
                # Keep processing until no more received invoices remain
                while True:
                    parsed_count = await process_received_invoices_batch()
                    break;
                    logger.info(f"Parsed {parsed_count} invoices, checking for more...")
                    # Small delay between batches to avoid tight loops
                    await asyncio.sleep(1)
                

                while True:
                    validated_count = await process_parsed_invoices_batch()
                    if validated_count == 0:
                        break
                    logger.info(f"Validated {validated_count} invoices, checking for more...")
                    # Small delay between batches to avoid tight loops
                    await asyncio.sleep(1)
                
                # Wait before next orchestration cycle
                # If background polling is disabled, check more frequently for new invoices
                sleep_interval = 30 if settings.ENABLE_BACKGROUND_POLLING else 10
                await asyncio.sleep(sleep_interval)
                
            except Exception as e:
                logger.error(f"Invoice processing orchestrator error: {e}")
                await asyncio.sleep(30)  # Wait longer on error
    
    # Start background email polling task (optional - for local/dev environments)
    # This runs independently for periodic email checks
    if settings.ENABLE_BACKGROUND_POLLING:
        async def poll_emails_periodically():
            """Background task to poll emails periodically (independent of orchestrator)"""
            while True:
                try:
                    await email_polling_service.poll_and_process_emails()
                    logger.info("Email polling service polled emails (background mode)")
                except Exception as e:
                    logger.error(f"Email polling error: {e}")
                
                # Wait for next polling interval (convert minutes to seconds)
                await asyncio.sleep(settings.POLL_INTERVAL_MINUTES * 60)
        
        # Start polling task
        polling_task = asyncio.create_task(poll_emails_periodically())
        logger.info("Email polling service started (background mode)")
    else:
        logger.info("Email polling service configured for Cloud Scheduler (background polling disabled)")
    
    # Start orchestration task (always runs to process invoices through the pipeline)
    orchestration_task = asyncio.create_task(invoice_processing_orchestrator())
    logger.info("Invoice processing orchestrator started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Invoice Control System API")
    
    # Cancel all background tasks
    tasks_to_cancel = []
    if polling_task:
        tasks_to_cancel.append(polling_task)
    if orchestration_task:
        tasks_to_cancel.append(orchestration_task)
    
    for task in tasks_to_cancel:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    logger.info("All background tasks cancelled")


# Create FastAPI application
app = FastAPI(
    title="Invoice Control System API",
    description="FastAPI backend for invoice processing, validation, and management",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Invoice Control System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/internal/poll-emails")
async def trigger_email_polling():
    """
    Internal endpoint to trigger email polling
    Called by Cloud Scheduler at configured intervals (POLL_INTERVAL_MINUTES)
    This allows the service to scale to zero on Cloud Run while maintaining periodic polling
    """
    try:
        result = await email_polling_service.poll_and_process_emails()
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        logger.error(f"Email polling triggered via endpoint failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    import sys
    from pathlib import Path
    
    # Add parent directory to path if running from backend directory
    backend_dir = Path(__file__).parent
    parent_dir = backend_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )

