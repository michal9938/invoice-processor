"""
Invoice validation API endpoints
Handles invoice validation, price acceptance, and dispute resolution
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from uuid import UUID
from backend.schemas.pydantic.validation import (
    ValidationResult,
    PriceAcceptanceRequest,
    DisputeRequest,
    DisputeResponse
)
from backend.services.validation_service import validation_service
from backend.services.mismatch_resolution import mismatch_resolution_service
from backend.core.logging import logger

router = APIRouter()


@router.post("/invoice/{invoice_id}", response_model=ValidationResult)
async def validate_invoice(invoice_id: UUID):
    """
    Validate an invoice and all its lines
    
    Compares invoice line items against buying_price_records and supplier_sku_mappings.
    Flags any mismatches based on configured tolerance.
    
    Args:
        invoice_id: Invoice UUID to validate
    """
    try:
        result = await validation_service.validate_invoice(invoice_id)
        return ValidationResult(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error validating invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accept-price", response_model=dict)
async def accept_price(price_request: PriceAcceptanceRequest):
    """
    Accept a new price for an invoice line
    
    Creates a new buying_price_record and closes the old one.
    Revalidates the invoice after price acceptance.
    
    Args:
        price_request: Price acceptance request with invoice line ID, new price, and reason
    """
    try:
        result = await mismatch_resolution_service.accept_price(
            invoice_line_id=price_request.invoice_line_id,
            new_price=price_request.new_price,
            reason=price_request.reason,
            valid_from=price_request.valid_from
        )
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error accepting price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dispute", response_model=DisputeResponse)
async def dispute_invoice(dispute_request: DisputeRequest):
    """
    Dispute an invoice or specific invoice lines
    
    Marks the invoice as disputed and logs the dispute in audit_log.
    Can dispute the entire invoice or specific lines.
    
    Args:
        dispute_request: Dispute request with invoice ID, reason, and optional line IDs
    """
    try:
        result = await mismatch_resolution_service.dispute_invoice(
            invoice_id=dispute_request.invoice_id,
            reason=dispute_request.reason,
            line_ids=[UUID(lid) for lid in dispute_request.line_ids] if dispute_request.line_ids else None
        )
        return DisputeResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error disputing invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/invoice/{invoice_id}/status", response_model=dict)
async def get_validation_status(invoice_id: UUID):
    """
    Get validation status for an invoice
    
    Returns the current validation status and summary of validated/error lines.
    
    Args:
        invoice_id: Invoice UUID
    """
    try:
        from backend.supabase_client import supabase_client
        
        # Get invoice
        invoices_table = supabase_client.get_table("invoices")
        invoice_result = invoices_table.select("status").eq("id", str(invoice_id)).limit(1).execute()
        
        if not invoice_result.data:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
        
        # Get invoice lines with validation status
        invoice_lines_table = supabase_client.get_table("invoice_lines")
        lines_result = invoice_lines_table.select("status").eq("invoice_id", str(invoice_id)).execute()
        
        lines = lines_result.data
        match_count = sum(1 for line in lines if line.get("status") == "match")
        error_count = sum(1 for line in lines if line.get("status") in ["mismatch", "no_match", "created_price_record"])
        
        return {
            "invoice_id": str(invoice_id),
            "status": invoice_result.data[0]["status"],
            "total_lines": len(lines),
            "match_count": match_count,
            "error_count": error_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting validation status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

