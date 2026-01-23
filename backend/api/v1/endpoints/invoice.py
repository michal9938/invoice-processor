"""
Invoice-related API endpoints
Handles invoice creation, retrieval, manual upload, and PDF parsing
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from typing import List, Optional
from uuid import UUID
from backend.schemas.pydantic.invoice import (
    InvoiceCreate,
    InvoiceResponse,
    InvoiceWithLines,
    ManualUploadRequest,
    InvoiceLineResponse
)
from backend.services.email_polling import email_polling_service
from backend.services.pdf_parser import pdf_parser_service
from backend.supabase_client import supabase_client
from backend.core.logging import logger

router = APIRouter()


@router.post("/", response_model=InvoiceResponse, status_code=201)
async def create_invoice(invoice_data: InvoiceCreate):
    """
    Create a new invoice record manually
    
    This endpoint allows manual creation of invoices when email polling fails
    or for invoices received through other channels.
    """
    try:
        from datetime import datetime
        from uuid import uuid4
        
        invoice_id = str(uuid4())
        invoice_record = {
            "id": invoice_id,
            "supplier": invoice_data.supplier,
            "invoice_number": invoice_data.invoice_number,
            "invoice_date": invoice_data.invoice_date.isoformat(),
            "status": invoice_data.status or "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        invoices_table = supabase_client.get_table("invoices")
        result = invoices_table.insert(invoice_record).execute()
        
        if result.data:
            return InvoiceResponse(**result.data[0])
        else:
            raise HTTPException(status_code=500, detail="Failed to create invoice")
            
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[InvoiceResponse])
async def list_invoices(skip: int = 0, limit: int = 100):
    """
    List all invoices with pagination
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
    """
    try:
        invoices_table = supabase_client.get_table("invoices")
        result = invoices_table.select("*").order("created_at", desc=True).range(skip, skip + limit - 1).execute()
        
        return [InvoiceResponse(**invoice) for invoice in result.data]
        
    except Exception as e:
        logger.error(f"Error listing invoices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{invoice_id}", response_model=InvoiceWithLines)
async def get_invoice(invoice_id: UUID):
    """
    Get a specific invoice with its lines
    
    Args:
        invoice_id: Invoice UUID
    """
    try:
        # Get invoice
        invoices_table = supabase_client.get_table("invoices")
        invoice_result = invoices_table.select("*").eq("id", str(invoice_id)).limit(1).execute()
        
        if not invoice_result.data:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        
        invoice_data = invoice_result.data[0]
        
        # Get invoice lines
        invoice_lines_table = supabase_client.get_table("invoice_lines")
        lines_result = invoice_lines_table.select("*").eq("invoice_id", str(invoice_id)).execute()
        
        lines = [InvoiceLineResponse(**line) for line in lines_result.data]
        
        return InvoiceWithLines(**invoice_data, lines=lines)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=InvoiceResponse, status_code=201)
async def upload_invoice_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    supplier: Optional[str] = None,
    invoice_number: Optional[str] = None
):
    """
    Manually upload an invoice PDF file
    
    This endpoint allows manual upload of invoice PDFs for processing.
    The PDF will be parsed and invoice lines will be extracted.
    
    Args:
        file: PDF file to upload
        supplier: Optional supplier name (will try to extract from PDF if not provided)
        invoice_number: Optional invoice number (will generate if not provided)
    """
    try:
        # Validate file type
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read file content
        pdf_content = await file.read()
        
        # Check file size
        from backend.core.config import settings
        max_size = settings.MAX_PDF_SIZE_MB * 1024 * 1024
        if len(pdf_content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum of {settings.MAX_PDF_SIZE_MB}MB"
            )
        
        # Create invoice record
        from datetime import datetime
        from uuid import uuid4
        
        invoice_id = str(uuid4())
        supplier_name = supplier or "Unknown"
        inv_number = invoice_number or f"MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        invoice_record = {
            "id": invoice_id,
            "supplier": supplier_name,
            "invoice_number": inv_number,
            "invoice_date": datetime.now().isoformat(),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        invoices_table = supabase_client.get_table("invoices")
        result = invoices_table.insert(invoice_record).execute()
        
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invoice record")
        
        # Store PDF in Supabase storage
        storage = supabase_client.get_storage()
        file_path = f"invoices/{invoice_id}/{file.filename}"
        storage.upload(file_path, pdf_content, file_options={"content-type": "application/pdf"})
        
        # Create pdfs record
        pdfs_table = supabase_client.get_table("pdfs")
        pdf_record = {
            "id": str(uuid4()),
            "invoice_id": invoice_id,
            "file_path": file_path,
            "file_size": len(pdf_content),
            "created_at": datetime.now().isoformat()
        }
        pdfs_table.insert(pdf_record).execute()
        
        # Parse PDF in background
        background_tasks.add_task(parse_invoice_pdf_background, UUID(invoice_id), pdf_content)
        
        return InvoiceResponse(**result.data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def parse_invoice_pdf_background(invoice_id: UUID, pdf_content: bytes):
    """Background task to parse invoice PDF"""
    try:
        await pdf_parser_service.parse_invoice_pdf(invoice_id, pdf_content)
    except Exception as e:
        logger.error(f"Background PDF parsing failed for invoice {invoice_id}: {e}")


@router.post("/poll-emails", status_code=200)
async def poll_emails(background_tasks: BackgroundTasks):
    """
    Manually trigger email polling
    
    This endpoint triggers the email polling service to check for new invoices.
    Processing happens in the background.
    """
    try:
        # Run email polling in background
        background_tasks.add_task(email_polling_service.poll_and_process_emails)
        
        return {"message": "Email polling started in background"}
        
    except Exception as e:
        logger.error(f"Error starting email polling: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{invoice_id}/lines", response_model=List[InvoiceLineResponse])
async def get_invoice_lines(invoice_id: UUID):
    """
    Get all lines for a specific invoice
    
    Args:
        invoice_id: Invoice UUID
    """
    try:
        invoice_lines_table = supabase_client.get_table("invoice_lines")
        result = invoice_lines_table.select("*").eq("invoice_id", str(invoice_id)).execute()
        
        return [InvoiceLineResponse(**line) for line in result.data]
        
    except Exception as e:
        logger.error(f"Error getting invoice lines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

