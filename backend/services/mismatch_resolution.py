"""
Mismatch Resolution Service
Handles discrepancies between invoice values and expected values.
Manages price acceptance, disputes, and audit logging.
"""
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from backend.core.logging import logger
from backend.supabase_client import supabase_client


class MismatchResolutionService:
    """Service for resolving invoice mismatches and price updates"""
    
    def __init__(self):
        """Initialize the mismatch resolution service"""
        pass
    
    async def accept_price(self, invoice_line_id: UUID, new_price: float, reason: str, valid_from: datetime, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Accept a new price and create a new buying_price_record
        
        Args:
            invoice_line_id: Invoice line ID
            new_price: New price to accept
            reason: Reason for price acceptance
            valid_from: Valid from date for the new price
            user_id: User ID who accepted the price (optional)
        
        Returns:
            Dictionary with result details
        """
        try:
            # Get invoice line data
            invoice_lines_table = supabase_client.get_table("invoice_lines")
            line_result = invoice_lines_table.select("*, invoices(*)").eq("id", str(invoice_line_id)).limit(1).execute()
            
            if not line_result.data:
                raise ValueError(f"Invoice line {invoice_line_id} not found")
            
            line_data = line_result.data[0]
            invoice_data = line_data.get("invoices", {})
            
            # Get product mapping
            sku = line_data["sku"]
            supplier_name = invoice_data.get("supplier")
            
            # Find supplier and product
            from backend.services.validation_service import validation_service
            supplier_id = await validation_service.get_supplier_id_by_name(supplier_name)
            if not supplier_id:
                raise ValueError(f"Supplier '{supplier_name}' not found")
            
            product_mapping = await validation_service.find_product_by_sku(sku, supplier_id)
            if not product_mapping:
                raise ValueError(f"Product mapping for SKU '{sku}' not found")
            
            product_id = UUID(product_mapping["product_id"])
            
            # Close old price record
            await self._close_old_price_record(product_id, supplier_id, valid_from)
            
            # Create new price record
            from uuid import uuid4
            price_records_table = supabase_client.get_table("buying_price_records")
            new_price_record = {
                "id": str(uuid4()),
                "product_id": str(product_id),
                "supplier_id": str(supplier_id),
                "price": new_price,
                "valid_from": valid_from.isoformat(),
                "valid_to": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            price_records_table.insert(new_price_record).execute()
            
            # Log price acceptance in audit_log
            await self._log_price_acceptance(
                invoice_line_id,
                product_id,
                new_price,
                reason,
                user_id
            )
            
            # Revalidate the invoice
            invoice_id = UUID(line_data["invoice_id"])
            from backend.services.validation_service import validation_service
            await validation_service.validate_invoice(invoice_id)
            
            logger.info(f"Accepted new price {new_price} for product {product_id}")
            
            return {
                "status": "accepted",
                "new_price": new_price,
                "product_id": str(product_id),
                "valid_from": valid_from.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to accept price: {e}")
            raise
    
    async def _close_old_price_record(self, product_id: UUID, supplier_id: UUID, valid_from: datetime):
        """Close old price record by setting valid_to date"""
        try:
            price_records_table = supabase_client.get_table("buying_price_records")
            
            # Find active price records
            result = price_records_table.select("*").eq("product_id", str(product_id)).eq("supplier_id", str(supplier_id)).is_("valid_to", "null").execute()
            
            # Close all active records
            for record in result.data:
                price_records_table.update({
                    "valid_to": valid_from.isoformat(),
                    "updated_at": datetime.now().isoformat()
                }).eq("id", record["id"]).execute()
            
        except Exception as e:
            logger.error(f"Failed to close old price record: {e}")
            raise
    
    async def dispute_invoice(self, invoice_id: UUID, reason: str, line_ids: Optional[list] = None, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Dispute an invoice or specific invoice lines
        
        Args:
            invoice_id: Invoice UUID
            reason: Reason for dispute
            line_ids: Optional list of specific line IDs to dispute
            user_id: User ID who initiated the dispute (optional)
        
        Returns:
            Dictionary with dispute details
        """
        try:
            invoices_table = supabase_client.get_table("invoices")
            
            # Update invoice status to disputed
            invoices_table.update({
                "status": "disputed",
                "updated_at": datetime.now().isoformat()
            }).eq("id", str(invoice_id)).execute()
            
            # Update specific lines if provided
            if line_ids:
                invoice_lines_table = supabase_client.get_table("invoice_lines")
                for line_id in line_ids:
                    invoice_lines_table.update({
                        "status": "no_match",  # Use no_match status for disputed lines
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", str(line_id)).execute()
            
            # Generate dispute summary
            dispute_summary = await self._generate_dispute_summary(invoice_id, line_ids)
            
            # Log dispute in audit_log
            await self._log_dispute(invoice_id, reason, dispute_summary, user_id)
            
            logger.info(f"Invoice {invoice_id} disputed: {reason}")
            
            return {
                "invoice_id": invoice_id,
                "status": "disputed",
                "dispute_summary": dispute_summary,
                "disputed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to dispute invoice: {e}")
            raise
    
    async def _generate_dispute_summary(self, invoice_id: UUID, line_ids: Optional[list] = None) -> str:
        """Generate a summary of the dispute"""
        try:
            invoice_lines_table = supabase_client.get_table("invoice_lines")
            
            query = invoice_lines_table.select("*").eq("invoice_id", str(invoice_id))
            if line_ids:
                query = query.in_("id", [str(lid) for lid in line_ids])
            
            result = query.execute()
            lines = result.data
            
            summary_parts = [f"Dispute for invoice {invoice_id}"]
            summary_parts.append(f"Affected lines: {len(lines)}")
            
            for line in lines:
                summary_parts.append(
                    f"Line {line['sku']}: Unit Price={line['unit_price']}, "
                    f"Quantity={line['quantity']}, Total={line['line_total']}"
                )
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.warning(f"Failed to generate dispute summary: {e}")
            return f"Dispute for invoice {invoice_id}"
    
    async def _log_price_acceptance(self, invoice_line_id: UUID, product_id: UUID, new_price: float, reason: str, user_id: Optional[UUID]):
        """Log price acceptance in audit_log"""
        try:
            audit_log_table = supabase_client.get_table("audit_log")
            
            from uuid import uuid4
            audit_entry = {
                "id": str(uuid4()),
                "action_type": "price_acceptance",
                "table_name": "buying_price_records",
                "record_id": str(product_id),
                "action_details": f"Accepted new price {new_price} for invoice line {invoice_line_id}. Reason: {reason}",
                "user_id": str(user_id) if user_id else None,
                "created_at": datetime.now().isoformat()
            }
            
            audit_log_table.insert(audit_entry).execute()
            
        except Exception as e:
            logger.warning(f"Failed to log price acceptance: {e}")
    
    async def _log_dispute(self, invoice_id: UUID, reason: str, summary: str, user_id: Optional[UUID]):
        """Log dispute in audit_log"""
        try:
            audit_log_table = supabase_client.get_table("audit_log")
            
            from uuid import uuid4
            audit_entry = {
                "id": str(uuid4()),
                "action_type": "invoice_dispute",
                "table_name": "invoices",
                "record_id": str(invoice_id),
                "action_details": f"Dispute initiated. Reason: {reason}\nSummary: {summary}",
                "user_id": str(user_id) if user_id else None,
                "created_at": datetime.now().isoformat()
            }
            
            audit_log_table.insert(audit_entry).execute()
            
        except Exception as e:
            logger.warning(f"Failed to log dispute: {e}")


# Global service instance
mismatch_resolution_service = MismatchResolutionService()

