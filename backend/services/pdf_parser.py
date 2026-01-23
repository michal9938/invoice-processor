"""
PDF Parsing Service
Extracts structured data from PDF invoices using OpenAI GPT-4o with logo and text extraction.
"""
import io
import base64
import json
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime
import pdfplumber
from PIL import Image
from openai import OpenAI
from backend.core.logging import logger
from backend.core.config import settings
from backend.supabase_client import supabase_client


class PDFParserService:
    """Service for parsing PDF invoices using OpenAI GPT-4o-mini with GPT-4o fallback"""
    
    def __init__(self):
        """Initialize the PDF parser service"""
        self._openai_client: Optional[OpenAI] = None
        self.default_model = "gpt-4o"
        self.fallback_model = "gpt-4o"
    
    @property
    def openai_client(self) -> OpenAI:
        """Lazy initialization of OpenAI client - only when needed and if API key is available"""
        if self._openai_client is None:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                raise ValueError(
                    "OpenAI API key is not configured. "
                    "Please set OPENAI_API_KEY in your .env file to use OpenAI features."
                )
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client
    
    def extract_logo_image(self, pdf_content: bytes) -> Optional[bytes]:
        """
        Extract logo image from first page top area as PNG/JPG
        
        Args:
            pdf_content: PDF file content as bytes
        
        Returns:
            Logo image as PNG/JPG bytes or None
        """
        try:
            pdf_file = io.BytesIO(pdf_content)
            
            with pdfplumber.open(pdf_file) as pdf:
                if len(pdf.pages) == 0:
                    return None
                
                first_page = pdf.pages[0]
                
                # Extract top area (first 200 points or 30% of page height)
                page_height = first_page.height
                top_area_height = min(200, page_height * 0.3)
                
                # Crop top area
                bbox = (0, 0, first_page.width, top_area_height)
                cropped_page = first_page.crop(bbox)
                
                # Convert to image
                im = cropped_page.to_image(resolution=150)
                pil_image = im.original
                
                # Convert to PNG bytes
                img_bytes = io.BytesIO()
                pil_image.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                logger.info("Extracted logo image from PDF first page")
                return img_bytes.read()
                
        except Exception as e:
            logger.warning(f"Failed to extract logo image: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """
        Extract text content from PDF using pdfplumber
        
        Args:
            pdf_content: PDF file content as bytes
        
        Returns:
            Dictionary with extracted text and tables
        """
        pdf_file = io.BytesIO(pdf_content)
        
        try:
            with pdfplumber.open(pdf_file) as pdf:
                full_text = ""
                tables = []
                
                for page in pdf.pages:
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
                    
                    # Extract tables (common in invoices)
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
                
                return {
                    "text": full_text,
                    "tables": tables,
                    "page_count": len(pdf.pages)
                }
                
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise
    
    def _get_extraction_prompt(self) -> str:
        """Get the strict JSON schema prompt for OpenAI"""
        return """You are an invoice extraction engine. Your task is to extract facts only from the provided PDF text and the provided logo image.

Do not guess. If a field is not explicitly present, output null. Accuracy is very important. Language is Danish.
Regarding the Quantity field, it normally has a PCS suffix. But return number.
Return ONLY valid JSON that matches the schema exactly. No markdown, no commentary.
And ',' in price number means '.'.

Currency : EUR or DKK

Logo stands for supplier.

Product name and SKU number can be in same cell.

supplier_name is one of these :
Alpine, Audinell, Bernafon, Duraxx, Ewanto, GN, Oticon, Phonak, Sivantos, Starkey, Widx

expected output:
{
  "supplier_name": null,
  "invoice_number": null,
  "invoice_date": null,
  "currency": null,
  "subtotal_amount": null,
  "tax_amount": null,
  "total_amount": null,
  "lines": [
    {
      "line_no": 1,
      "sku": null,
      "product_name": null,
      "description": null,
      "quantity": null,
      "unit_price": null,
      "line_total": null
    }
  ],
  "warnings": [
    "TEMPLATE_ONLY: set fields to extracted values; remove this warning in production"
  ]
}"""
    
    def _check_critical_fields_missing(self, extracted_data: Dict[str, Any]) -> bool:
        """
        Check if critical fields are missing from extracted data
        
        Args:
            extracted_data: Extracted invoice data dictionary
        
        Returns:
            True if critical fields are missing, False otherwise
        """
        # Check supplier_name (critical for validation)
        if not extracted_data.get("supplier_name"):
            logger.warning("Critical field missing: supplier_name")
            return True
        
        # Check if we have at least one line item
        lines = extracted_data.get("lines", [])
        if not lines or len(lines) == 0:
            logger.warning("Critical field missing: no invoice lines found")
            return True
        
        # Check if invoice_number is missing (important but not critical)
        if not extracted_data.get("invoice_number"):
            logger.info("Important field missing: invoice_number (will retry with GPT-4o)")
            return True
        
        # Check if total_amount is missing (important for validation)
        if not extracted_data.get("total_amount"):
            logger.info("Important field missing: total_amount (will retry with GPT-4o)")
            return True
        
        return False
    
    async def call_openai_for_extraction(
        self, 
        logo_image: Optional[bytes], 
        raw_text: str,
        model: str = None
    ) -> Dict[str, Any]:
        """
        Call OpenAI to extract invoice data
        
        Args:
            logo_image: Logo image bytes (optional)
            raw_text: Extracted PDF text
            model: Model to use (defaults to default_model)
        
        Returns:
            Extracted invoice data as dictionary
        """
        if model is None:
            model = self.default_model
        
        try:
            messages = [
                {
                    "role": "system",
                    "content": self._get_extraction_prompt()
                }
            ]
            
            content_parts = [
                {
                    "type": "text",
                    "text": f"Extract invoice data from the following PDF text:\n\n{raw_text}"
                }
            ]
            
            # Add logo image if available
            if logo_image:
                base64_image = base64.b64encode(logo_image).decode('utf-8')
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                })
            
            messages.append({
                "role": "user",
                "content": content_parts
            })
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            # Parse JSON response
            response_text = response.choices[0].message.content
            extracted_data = json.loads(response_text)
            
            logger.info(f"Successfully extracted invoice data using {model}")
            return extracted_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse OpenAI JSON response: {e}")
            raise ValueError(f"Invalid JSON response from OpenAI: {e}")
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def download_pdf_from_storage(
        self, 
        storage_bucket: str, 
        storage_path: str
    ) -> bytes:
        """
        Download PDF from Supabase Storage
        
        Args:
            storage_bucket: Storage bucket name
            storage_path: Path to PDF file
        
        Returns:
            PDF file content as bytes
        """
        try:
            storage = supabase_client.client.storage.from_(storage_bucket)
            pdf_bytes = storage.download(storage_path)
            
            logger.info(f"Downloaded PDF from {storage_bucket}/{storage_path}")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"Failed to download PDF from storage: {e}")
            raise
    
    async def parse_invoice(self, invoice_id: UUID) -> Dict[str, Any]:
        """
        Main parsing function: download PDF, extract data using OpenAI, store results
        
        Args:
            invoice_id: Invoice UUID
        
        Returns:
            Dictionary with parsing results
        """
        try:
            # Get invoice from database
            invoices_table = supabase_client.get_table("invoices")
            invoice_result = invoices_table.select("*").eq("id", str(invoice_id)).limit(1).execute()
            
            if not invoice_result.data:
                raise ValueError(f"Invoice {invoice_id} not found")
            
            invoice = invoice_result.data[0]
            
            # Check status
            if invoice["status"] != "received":
                logger.warning(f"Invoice {invoice_id} status is {invoice['status']}, expected 'received'") 
            
            storage_bucket = invoice.get("storage_bucket", "pdfs")
            storage_path = invoice["storage_path"]
            
            # Download PDF
            pdf_content = await self.download_pdf_from_storage(storage_bucket, storage_path)
            
            # Extract logo image
            logo_image = self.extract_logo_image(pdf_content)
            
            # Extract raw text
            extracted_data = self.extract_text_from_pdf(pdf_content)
            raw_text = extracted_data["text"]
            
            # Add table data to text if available
            if extracted_data.get("tables"):
                raw_text += "\n\nTables:\n"
                for i, table in enumerate(extracted_data["tables"], 1):
                    raw_text += f"\nTable {i}:\n"
                    for row in table:
                        raw_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
            
            # Call OpenAI for extraction - try GPT-4o-mini firstnull
            model_used = self.default_model
            extracted_invoice = await self.call_openai_for_extraction(
                logo_image, 
                raw_text, 
                model=self.default_model
            )
            print(extracted_invoice)
            
            # Check if critical fields are missing
            # if self._check_critical_fields_missing(extracted_invoice):
            #     logger.info(f"Critical fields missing from {self.default_model} extraction, retrying with {self.fallback_model}")
                
            #     # Retry with GPT-4o
            #     try:
            #         extracted_invoice = await self.call_openai_for_extraction(
            #             logo_image,
            #             raw_text,
            #             model=self.fallback_model
            #         )
            #         model_used = self.fallback_model
                    
            #         # Check again - if still missing, log warning but proceed
            #         if self._check_critical_fields_missing(extracted_invoice):
            #             logger.warning(f"Critical fields still missing after {self.fallback_model} retry, proceeding anyway")
            #     except Exception as e:
            #         logger.error(f"Fallback to {self.fallback_model} failed: {e}")
            #         logger.info("Proceeding with GPT-4o-mini results despite missing fields")
            
            # Update invoice table
            await self._update_invoice(invoice_id, extracted_invoice)
            
            # Replace invoice lines
            line_count = await self._replace_invoice_lines(invoice_id, extracted_invoice.get("lines", []))
            
            # Add audit log
            await self._log_invoice_parsed(
                invoice_id, 
                line_count, 
                model_used, 
                extracted_invoice.get("warnings", [])
            )
            
            return {
                "status": "parsed",
                "lines_parsed": line_count,
                "model": model_used,
                "warnings": extracted_invoice.get("warnings", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to parse invoice {invoice_id}: {e}")
            # Update status to indicate parsing failure
            try:
                invoices_table = supabase_client.get_table("invoices")
                invoices_table.update({
                    "status": "needs_review"
                }).eq("id", str(invoice_id)).execute()
            except:
                pass
            raise
    
    async def _update_invoice(
        self, 
        invoice_id: UUID, 
        extracted_data: Dict[str, Any]
    ):
        """Update invoice table with extracted header fields"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            
            update_data = {
                "supplier_name": extracted_data.get("supplier_name"),
                "invoice_number": extracted_data.get("invoice_number"),
                "invoice_date": extracted_data.get("invoice_date"),
                "currency": extracted_data.get("currency"),
                "subtotal_amount": extracted_data.get("subtotal_amount"),
                "tax_amount": extracted_data.get("tax_amount"),
                "total_amount": extracted_data.get("total_amount"),
                "status": "parsed",
                "parsed_at": datetime.now().isoformat()
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            invoices_table.update(update_data).eq("id", str(invoice_id)).execute()
            
            logger.info(f"Updated invoice {invoice_id} with extracted header fields")
            
        except Exception as e:
            logger.error(f"Failed to update invoice: {e}")
            raise
    
    async def _replace_invoice_lines(
        self, 
        invoice_id: UUID, 
        lines: List[Dict[str, Any]]
    ) -> int:
        """
        Replace invoice lines: delete old, insert new
        
        Args:
            invoice_id: Invoice UUID
            lines: List of line dictionaries from OpenAI extraction
        
        Returns:
            Number of lines inserted
        """
        try:
            invoice_lines_table = supabase_client.get_table("invoice_lines")
            
            # Delete existing lines
            invoice_lines_table.delete().eq("invoice_id", str(invoice_id)).execute()
            
            # Insert new lines
            if not lines:
                logger.warning(f"No lines to insert for invoice {invoice_id}")
                return 0
            
            line_records = []
            for line in lines:
                line_record = {
                    "id": str(uuid4()),
                    "invoice_id": str(invoice_id),
                    "line_no": line.get("line_no"),
                    "sku": line.get("sku"),
                    "product_name": line.get("product_name"),
                    "description": line.get("description"),
                    "status": None,  # Status will be set by validation service
                    "quantity": line.get("quantity"),
                    "unit_price": line.get("unit_price"),
                    "line_total": line.get("line_total"),
                    "currency": line.get("currency")
                }
                line_records.append(line_record)
            
            # Insert all lines
            for record in line_records:
                invoice_lines_table.insert(record).execute()
            
            logger.info(f"Replaced {len(line_records)} invoice lines for invoice {invoice_id}")
            return len(line_records)
            
        except Exception as e:
            logger.error(f"Failed to replace invoice lines: {e}")
            raise
    
    async def _log_invoice_parsed(
        self, 
        invoice_id: UUID, 
        line_count: int, 
        model: str, 
        warnings: List[str]
    ):
        """Log INVOICE_PARSED action in audit_log"""
        try:
            audit_log_table = supabase_client.get_table("audit_log")
            
            audit_entry = {
                "id": str(uuid4()),
                "entity_type": "invoice",
                "entity_id": str(invoice_id),
                "action": "INVOICE_PARSED",
                "details": {
                    "line_count": line_count,
                    "model": model,
                    "warnings": warnings
                },
                "performed_by": None,  # System action
                "performed_at": datetime.now().isoformat()
            }
            
            audit_log_table.insert(audit_entry).execute()
            
            logger.info(f"Logged INVOICE_PARSED for invoice {invoice_id}")
            
        except Exception as e:
            logger.warning(f"Failed to log invoice parsed: {e}")


# Global service instance
pdf_parser_service = PDFParserService()
