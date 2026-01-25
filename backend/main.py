"""
FastAPI application main entry point
Sets up the FastAPI app, includes routers, and handles startup/shutdown events
"""
import sys
from pathlib import Path

# Add parent directory to path if running from backend directory
# This allows imports to work when running: py -m uvicorn main:app from backend folder
backend_dir = Path(__file__).parent
parent_dir = backend_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

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
    logger.info(f"Batch size: {settings.MAX_EMAILS_PER_RUN} invoices per batch")
    
    orchestration_task = None
    polling_task = None
    
    async def process_received_invoices_batch() -> int:
        """Process invoices with status='received' in small batches for stability"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            result = invoices_table.select("id").eq("status", "received").limit(settings.MAX_EMAILS_PER_RUN).execute()
            
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
        """Process invoices with status='parsed' in small batches for stability"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            result = invoices_table.select("id").eq("status", "parsed").limit(settings.MAX_EMAILS_PER_RUN).execute()
            
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
        Processes in small batches for stability and accuracy
        """
        while True:
            try:
                # Step 1: Poll emails (only if background polling is disabled)
                # If ENABLE_BACKGROUND_POLLING is True, polling happens in separate task
                if not settings.ENABLE_BACKGROUND_POLLING:
                    try:
                        await email_polling_service.poll_and_process_emails()
                        logger.info("Email polling completed")
                    except Exception as e:
                        logger.error(f"Email polling error: {e}")
                
                # Step 2: Process all received invoices (parse them) - continue until done
                total_parsed = 0
                while True:
                    parsed_count = await process_received_invoices_batch()
                    if parsed_count == 0:
                        break  # No more received invoices
                    total_parsed += parsed_count
                    logger.info(f"Parsed {parsed_count} invoices (total: {total_parsed}), checking for more...")
                    # Small delay between batches to avoid tight loops
                    await asyncio.sleep(1)
                
                if total_parsed > 0:
                    logger.info(f"Completed parsing phase: {total_parsed} invoices processed")
                
                # Step 3: Process all parsed invoices (validate them) - continue until done
                total_validated = 0
                while True:
                    validated_count = await process_parsed_invoices_batch()
                    if validated_count == 0:
                        break  # No more parsed invoices
                    total_validated += validated_count
                    logger.info(f"Validated {validated_count} invoices (total: {total_validated}), checking for more...")
                    # Small delay between batches to avoid tight loops
                    await asyncio.sleep(1)
                
                if total_validated > 0:
                    logger.info(f"Completed validation phase: {total_validated} invoices processed")
                
                # Wait for polling interval before next orchestration cycle
                # After completing all three pipelines (poll → parse → validate), wait for the full interval
                sleep_interval = settings.POLL_INTERVAL_MINUTES * 60
                logger.info(f"All pipelines completed. Orchestrator cycle complete, sleeping for {settings.POLL_INTERVAL_MINUTES} minutes ({sleep_interval} seconds)")
                await asyncio.sleep(sleep_interval)
                
            except Exception as e:
                logger.error(f"Invoice processing orchestrator error: {e}")
                await asyncio.sleep(30)  # Wait longer on error
    
    # Start background email polling task (optional - for local/dev environments)
    # NOTE: When background polling is enabled, it runs independently and does NOT coordinate
    # with the orchestrator. The orchestrator will still process invoices but won't poll emails.
    # For proper orchestration, set ENABLE_BACKGROUND_POLLING=False and let orchestrator handle everything.
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
                logger.info(f"Email polling service waiting for next polling interval: {settings.POLL_INTERVAL_MINUTES} minutes")
                await asyncio.sleep(60)
        
        # Start polling task
        polling_task = asyncio.create_task(poll_emails_periodically())
        logger.info("Email polling service started (background mode - runs independently of orchestrator)")
        logger.warning("NOTE: Background polling runs independently. Orchestrator will process invoices but not poll emails.")
    else:
        logger.info("Email polling service configured for orchestrator control (background polling disabled)")
    
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
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )

