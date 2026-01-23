"""
Invoice Validation Service
Validates each parsed invoice line against buying_price_records using SKU-first matching strategy.
Updates invoice_lines.status and creates buying_price_records as needed.
"""
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, date
from decimal import Decimal
from backend.core.logging import logger
from backend.supabase_client import supabase_client


class ValidationService:
    """Service for validating invoice lines against price records"""
    
    def __init__(self):
        """Initialize the validation service"""
        pass
    
    async def validate_invoice(self, invoice_id: UUID) -> Dict[str, Any]:
        """
        Validate all lines of an invoice
        
        Args:
            invoice_id: Invoice UUID
        
        Returns:
            Validation result dictionary with overall status and summary
        """
        try:
            # Get invoice data
            invoices_table = supabase_client.get_table("invoices")
            invoice_result = invoices_table.select("*").eq("id", str(invoice_id)).limit(1).execute()
            
            if not invoice_result.data:
                raise ValueError(f"Invoice {invoice_id} not found")
            
            invoice = invoice_result.data[0]
            
            # Check status
            if invoice["status"] != "parsed":
                logger.warning(f"Invoice {invoice_id} status is {invoice['status']}, expected 'parsed'")
            
            # Get all invoice lines
            invoice_lines_table = supabase_client.get_table("invoice_lines")
            lines_result = invoice_lines_table.select("*").eq("invoice_id", str(invoice_id)).order("line_no").execute()
            
            invoice_lines = lines_result.data
            
            if not invoice_lines:
                logger.warning(f"No invoice lines found for invoice {invoice_id}")
                await self._update_invoice_status(invoice_id, "needs_review", None)
                await self._log_audit(
                    "invoice",
                    invoice_id,
                    "MARKED_NEED_REVIEW",
                    {"reason": "no invoice lines found"}
                )
                return {
                    "invoice_id": invoice_id,
                    "status": "needs_review",
                    "total_lines": 0,
                    "match_count": 0,
                    "mismatch_count": 0,
                    "created_price_record_count": 0,
                    "no_match_count": 0
                }
            
            # Validate each line
            match_count = 0
            mismatch_count = 0
            created_price_record_count = 0
            no_match_count = 0
            
            supplier_name = invoice.get("supplier_name")
            invoice_date_str = invoice.get("invoice_date")
            invoice_date = None
            if invoice_date_str:
                try:
                    invoice_date = datetime.fromisoformat(invoice_date_str.replace("Z", "+00:00")).date()
                except:
                    pass
            invoice_currency = invoice.get("currency")
            
            for line in invoice_lines:
                validation_result = await self._validate_invoice_line(
                    line,
                    invoice_id,
                    supplier_name,
                    invoice_date,
                    invoice_currency
                )
                
                status = validation_result["status"]
                
                if status == "match":
                    match_count += 1
                elif status == "mismatch":
                    mismatch_count += 1
                elif status == "created_price_record":
                    created_price_record_count += 1
                elif status == "no_match":
                    no_match_count += 1
            
            # Determine overall invoice status
            if mismatch_count > 0 or created_price_record_count > 0 or no_match_count > 0:
                overall_status = "needs_review"
            else:
                overall_status = "validated"
            
            # Update invoice status
            validated_at = datetime.now() if overall_status == "validated" else None
            await self._update_invoice_status(invoice_id, overall_status, validated_at)
            
            # Log validation summary
            await self._log_audit(
                "invoice",
                invoice_id,
                "INVOICE_VALIDATED",
                {
                    "status": overall_status,
                    "total_lines": len(invoice_lines),
                    "match_count": match_count,
                    "mismatch_count": mismatch_count,
                    "created_price_record_count": created_price_record_count,
                    "no_match_count": no_match_count
                }
            )
            
            return {
                "invoice_id": invoice_id,
                "status": overall_status,
                "total_lines": len(invoice_lines),
                "match_count": match_count,
                "mismatch_count": mismatch_count,
                "created_price_record_count": created_price_record_count,
                "no_match_count": no_match_count,
                "validated_at": validated_at.isoformat() if validated_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to validate invoice {invoice_id}: {e}")
            raise
    
    async def _validate_invoice_line(
        self,
        line: Dict[str, Any],
        invoice_id: UUID,
        supplier_name: Optional[str],
        invoice_date: Optional[date],
        invoice_currency: Optional[str]
    ) -> Dict[str, Any]:
        """
        Validate a single invoice line against buying_price_records
        
        Args:
            line: Invoice line dictionary from database
            supplier_name: Supplier name from invoice
            invoice_date: Invoice date (optional)
            invoice_currency: Invoice currency (optional)
        
        Returns:
            Validation result dictionary with status
        """
        line_id = UUID(line["id"])
        sku = line.get("sku")
        product_name = line.get("product_name")
        unit_price = line.get("unit_price")
        line_currency = line.get("currency") or invoice_currency
        
        # Determine matching key
        if sku:
            # Match on (supplier_name, sku)
            buying_price_record = await self._find_buying_price_by_sku(
                supplier_name, 
                sku, 
                invoice_date
            )
        elif product_name:
            # Match on (supplier_name, product_name) - case-insensitive
            buying_price_record = await self._find_buying_price_by_product_name(
                supplier_name,
                product_name,
                invoice_date
            )
        else:
            # No matching key available
            await self._update_invoice_line_status(line_id, "no_match")
            await self._log_audit(
                "invoice",
                invoice_id,
                "MARKED_NEED_REVIEW",
                {
                    "reason": "missing sku/product_name",
                    "invoice_line_id": str(line_id)
                }
            )
            return {"status": "no_match"}
        
        if not buying_price_record:
            # No match found - try to create price record
            if supplier_name and (sku or product_name) and line_currency and unit_price:
                # Enough data to create price record
                new_price_record_id = await self._create_buying_price_record(
                    supplier_name,
                    sku,
                    product_name,
                    line_currency,
                    unit_price,
                    invoice_date
                )
                
                await self._update_invoice_line_status(line_id, "created_price_record")
                
                await self._log_audit(
                    "buying_price_record",
                    new_price_record_id,
                    "PRICE_RECORD_CREATED",
                    {
                        "supplier_name": supplier_name,
                        "sku": sku,
                        "product_name": product_name,
                        "unit_price": unit_price,
                        "currency": line_currency
                    }
                )
                
                return {"status": "created_price_record", "buying_price_record_id": new_price_record_id}
            else:
                # Not enough data
                await self._update_invoice_line_status(line_id, "no_match")
                await self._log_audit(
                    "invoice",
                    invoice_id,
                    "MARKED_NEED_REVIEW",
                    {
                        "reason": "missing sku/product_name or unit_price",
                        "invoice_line_id": str(line_id)
                    }
                )
                return {"status": "no_match"}
        
        # Match found - check if prices match
        expected_unit_price = float(buying_price_record["unit_price"])
        actual_unit_price = float(unit_price) if unit_price else None
        
        if actual_unit_price is None:
            # No unit price to compare
            await self._update_invoice_line_status(line_id, "no_match")
            return {"status": "no_match"}
        
        diff_unit_price = actual_unit_price - expected_unit_price
        
        if abs(diff_unit_price) < 0.0001:  # Consider equal if difference < 0.0001
            # MATCH
            await self._update_invoice_line_status(line_id, "match")
            return {"status": "match"}
        else:
            # MISMATCH
            await self._update_invoice_line_status(line_id, "mismatch")
            
            await self._log_audit(
                "invoice_line",
                line_id,
                "PRICE_MISMATCH",
                {
                    "expected": expected_unit_price,
                    "got": actual_unit_price,
                    "diff": diff_unit_price,
                    "sku": sku,
                    "product_name": product_name,
                    "buying_price_record_id": str(buying_price_record["id"])
                }
            )
            
            return {"status": "mismatch"}
    
    async def _find_buying_price_by_sku(
        self,
        supplier_name: Optional[str],
        sku: str,
        invoice_date: Optional[date]
    ) -> Optional[Dict[str, Any]]:
        """Find buying_price_record by supplier_name and sku"""
        if not supplier_name or not sku:
            return None
        
        try:
            buying_price_table = supabase_client.get_table("buying_price_records")
            
            query = buying_price_table.select("*").eq("supplier_name", supplier_name).eq("sku", sku).eq("status", "active")
            
            result = query.execute()
            
            if not result.data:
                return None
            
            # Filter by date validity if invoice_date is available
            candidates = result.data
            if invoice_date:
                valid_candidates = []
                for candidate in candidates:
                    valid_from = candidate.get("valid_from")
                    valid_to = candidate.get("valid_to")
                    
                    # Parse dates if they're strings
                    if valid_from and isinstance(valid_from, str):
                        try:
                            valid_from = datetime.fromisoformat(valid_from.replace("Z", "+00:00")).date()
                        except:
                            valid_from = None
                    if valid_to and isinstance(valid_to, str):
                        try:
                            valid_to = datetime.fromisoformat(valid_to.replace("Z", "+00:00")).date()
                        except:
                            valid_to = None
                    
                    # Check validity
                    if (valid_from is None or valid_from <= invoice_date) and (valid_to is None or invoice_date <= valid_to):
                        valid_candidates.append(candidate)
                
                candidates = valid_candidates
            
            # Return first candidate (or None)
            return candidates[0] if candidates else None
            
        except Exception as e:
            logger.error(f"Error finding buying price by SKU: {e}")
            return None
    
    async def _find_buying_price_by_product_name(
        self,
        supplier_name: Optional[str],
        product_name: str,
        invoice_date: Optional[date]
    ) -> Optional[Dict[str, Any]]:
        """Find buying_price_record by supplier_name and product_name (case-insensitive)"""
        if not supplier_name or not product_name:
            return None
        
        try:
            buying_price_table = supabase_client.get_table("buying_price_records")
            
            # Use case-insensitive match (PostgreSQL ilike)
            # Note: Supabase PostgREST doesn't directly support ilike, so we'll filter in Python
            query = buying_price_table.select("*").eq("supplier_name", supplier_name).eq("status", "active")
            
            result = query.execute()
            
            if not result.data:
                return None
            
            # Filter by case-insensitive product_name match
            candidates = [
                r for r in result.data 
                if r.get("product_name") and r["product_name"].lower() == product_name.lower()
            ]
            
            # Filter by date validity if invoice_date is available
            if invoice_date:
                valid_candidates = []
                for candidate in candidates:
                    valid_from = candidate.get("valid_from")
                    valid_to = candidate.get("valid_to")
                    
                    # Parse dates if they're strings
                    if valid_from and isinstance(valid_from, str):
                        try:
                            valid_from = datetime.fromisoformat(valid_from.replace("Z", "+00:00")).date()
                        except:
                            valid_from = None
                    if valid_to and isinstance(valid_to, str):
                        try:
                            valid_to = datetime.fromisoformat(valid_to.replace("Z", "+00:00")).date()
                        except:
                            valid_to = None
                    
                    # Check validity
                    if (valid_from is None or valid_from <= invoice_date) and (valid_to is None or invoice_date <= valid_to):
                        valid_candidates.append(candidate)
                
                candidates = valid_candidates
            
            # Return first candidate (or None)
            return candidates[0] if candidates else None
            
        except Exception as e:
            logger.error(f"Error finding buying price by product name: {e}")
            return None
    
    async def _create_buying_price_record(
        self,
        supplier_name: str,
        sku: Optional[str],
        product_name: Optional[str],
        currency: str,
        unit_price: float,
        valid_from: Optional[date]
    ) -> UUID:
        """Create a new buying_price_record from invoice line"""
        try:
            buying_price_table = supabase_client.get_table("buying_price_records")
            
            # Check if a recent record with same SKU and status 'need_review' already exists
            if sku:
                existing_query = buying_price_table.select("*").eq("supplier_name", supplier_name).eq("sku", sku).eq("status", "need_review")
                existing_result = existing_query.execute()
                
                if existing_result.data:
                    # Found existing record with same SKU and 'need_review' status, skip insert
                    existing_id = UUID(existing_result.data[0]["id"])
                    logger.info(f"Skipping insert: existing buying_price_record {existing_id} with same SKU '{sku}' and status 'need_review'")
                    return existing_id
            
            record = {
                "id": str(uuid4()),
                "supplier_name": supplier_name,
                "sku": sku,
                "product_name": product_name,
                "currency": currency,
                "unit_price": unit_price,
                "status": "need_review",
                "valid_from": valid_from.isoformat() if valid_from else None,
                "valid_to": None,
                "source": "learned_from_invoice",
                "note": None
            }
            result = buying_price_table.insert(record).execute()
            
            new_id = UUID(result.data[0]["id"])
            logger.info(f"Created buying_price_record {new_id} from invoice line")
            return new_id
            
        except Exception as e:
            logger.error(f"Failed to create buying_price_record: {e}")
            raise
    
    async def _update_invoice_line_status(
        self,
        invoice_line_id: UUID,
        status: str
    ):
        """Update invoice_line status field"""
        try:
            invoice_lines_table = supabase_client.get_table("invoice_lines")
            print("")
            print("status : ", status)
            print("")
            invoice_lines_table.update({
                "status": status
            }).eq("id", str(invoice_line_id)).execute()
            
            logger.debug(f"Updated invoice_line {invoice_line_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Failed to update invoice_line status: {e}")
            raise
    
    async def _update_invoice_status(
        self,
        invoice_id: UUID,
        status: str,
        validated_at: Optional[datetime]
    ):
        """Update invoice status and validated_at"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            
            update_data = {
                "status": status
            }
            
            if validated_at:
                update_data["validated_at"] = validated_at.isoformat()
            
            invoices_table.update(update_data).eq("id", str(invoice_id)).execute()
            
            logger.info(f"Updated invoice {invoice_id} status to {status}")
            
        except Exception as e:
            logger.error(f"Failed to update invoice status: {e}")
            raise
    
    async def _log_audit(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        details: Optional[Dict[str, Any]]
    ):
        """Log action in audit_log"""
        try:
            audit_log_table = supabase_client.get_table("audit_log")
            
            audit_entry = {
                "id": str(uuid4()),
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "action": action,
                "details": details,
                "performed_by": None,  # System action
                "performed_at": datetime.now().isoformat()
            }
            
            audit_log_table.insert(audit_entry).execute()
            
            logger.debug(f"Logged {action} for {entity_type} {entity_id}")
            
        except Exception as e:
            logger.warning(f"Failed to log audit: {e}")


# Global service instance
validation_service = ValidationService()
