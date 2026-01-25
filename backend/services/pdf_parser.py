"""
PDF Parsing Service
Extracts structured data from PDF invoices using OpenAI GPT-4o with logo and text extraction.
"""
import io
import base64
import json
import re
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, date
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
        # Danish month names mapping
        self.danish_months = {
            'januar': 1, 'februar': 2, 'marts': 3, 'april': 4,
            'maj': 5, 'juni': 6, 'juli': 7, 'august': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'december': 12
        }
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse date string from various formats (including Danish) to ISO format (YYYY-MM-DD)
        
        Args:
            date_str: Date string in various formats (e.g., "9. januar 2026", "2026-01-09", etc.)
        
        Returns:
            ISO format date string (YYYY-MM-DD) or None if parsing fails
        """
        if not date_str:
            return None
        
        try:
            # Try parsing Danish format: "9. januar 2026" or "9 januar 2026"
            danish_pattern = r'(\d{1,2})\.?\s+(\w+)\s+(\d{4})'
            match = re.match(danish_pattern, date_str.strip(), re.IGNORECASE)
            if match:
                day = int(match.group(1))
                month_name = match.group(2).lower()
                year = int(match.group(3))
                
                if month_name in self.danish_months:
                    month = self.danish_months[month_name]
                    parsed_date = date(year, month, day)
                    return parsed_date.isoformat()
            
            # Try ISO format: "2026-01-09"
            try:
                parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return parsed_date.date().isoformat()
            except:
                pass
            
            # Try DD.MM.YYYY format: "09.01.2026"
            try:
                parsed_date = datetime.strptime(date_str.strip(), '%d.%m.%Y')
                return parsed_date.date().isoformat()
            except:
                pass
            
            # Try common formats: "09/01/2026", "09-01-2026", etc.
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                try:
                    parsed_date = datetime.strptime(date_str.strip(), fmt)
                    return parsed_date.date().isoformat()
                except:
                    continue
            
            logger.warning(f"Could not parse date format: {date_str}")
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing date '{date_str}': {e}")
            return None
    
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
                
                # Ensure we have a valid crop area
                if top_area_height <= 0 or first_page.width <= 0:
                    logger.warning("Invalid page dimensions for logo extraction")
                    return None
                
                # Crop top area - pdfplumber bbox format: (x0, top, x1, bottom)
                # where top and bottom are distances from the top of the page
                bbox = (0, 0, first_page.width, top_area_height)
                cropped_page = first_page.crop(bbox)
                
                # Convert to image
                im = cropped_page.to_image(resolution=150)
                pil_image = im.original
                
                # Ensure image is in RGB mode (required for PNG saving)
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # Check if image has valid dimensions
                if pil_image.size[0] == 0 or pil_image.size[1] == 0:
                    logger.warning("Extracted logo image has invalid dimensions")
                    return None
                
                # Convert to PNG bytes
                img_bytes = io.BytesIO()
                pil_image.save(img_bytes, format='PNG', optimize=True)
                img_bytes.seek(0)
                image_data = img_bytes.read()
                img_bytes.close()
                
                logger.info(f"Extracted logo image from PDF first page (size: {pil_image.size[0]}x{pil_image.size[1]})")
                return image_data
                
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

 You MUST extract ALL invoice lines (line items) from the invoice. Invoice lines are the products, services, or items listed in the invoice table/rows. Each line item represents one product or service being invoiced.

Do not guess. If a field is not explicitly present, output null. Accuracy is very important. Language is Danish.
Regarding the Quantity field, return number.
Return ONLY valid JSON that matches the schema exactly. No markdown, no commentary.
And ',' in price number means '.'.

Currency : EUR or DKK : 

Logo stands for supplier.

Product name and SKU number can be in same cell.

Please extract quantity exactly. Languages are Danish in PDF text. And they can have suffix PCS, STK, etc.

DISCOUNT EXTRACTION RULES:
- Discount information can appear in various formats in the PDF (percentage, fixed amount, or both)
- Look for discount columns in the invoice table/rows (e.g., "Rabat", "Discount", "Afslag" in Danish)
- Discount can be shown as:
  * Percentage (e.g., "10%", "15%", "20%") - extract as a number (e.g., 10, 15, 20)
  * Fixed amount (e.g., "50.00", "100.00") - extract as a number
  * Both percentage and fixed amount may be present
- The "discount" field should contain the discount percentage or amount as a number
- The "discount_total" field should contain the total discount amount applied to the line item
- If discount is shown as percentage, calculate discount_total = (unit_price * quantity) * (discount / 100)
- If discount is shown as fixed amount, use that value for discount_total
- If no discount is present, set both "discount" and "discount_total" to null
- Extract discount information accurately from the invoice - do not skip or ignore discount fields

Response will be written in English.

INVOICE LINES EXTRACTION RULES:
- The "lines" array MUST contain ALL line items from the invoice table/rows
- Each row in the invoice table is one line item
- Even if some fields (sku, product_name, etc.) are missing, you MUST still include the line item
- Line numbers (line_no) should be sequential starting from 1
- Look for tables with columns like: Line Number, Product Name, SKU, Quantity, Unit Price, Total, etc.
- Extract ALL rows from the invoice line items table, not just the first few
- If the invoice has multiple pages, extract lines from ALL pages

supplier_name is one of these. Logo image ususally stands for Supplier, but you can confirm that from earlier part of invoice text. e.x. Sivantos A/S Anway you should extract it correctly from one of these:
Alpine, Audinell, Bernafon, Duraxx, Ewanto, GN, Oticon, Phonak, Sivantos, Starkey, Widex, unitron

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
      "unit": null,
      "unit_price": null,
      "discount": null,
      "discount_total": null,
      "net_amount": null,
      "vat_percentage": null,
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
            
            # Try to update invoice table with header fields (but NOT status yet)
            # If this fails, we still want to insert invoice lines
            header_update_success = False
            try:
                await self._update_invoice_header_fields(invoice_id, extracted_invoice)
                header_update_success = True
            except Exception as e:
                logger.error(f"Failed to update invoice header fields for {invoice_id}: {e}")
                logger.info("Continuing to insert invoice lines despite header update failure")
            
            # Replace invoice lines - this is critical, do it even if header update failed
            # Clean and normalize the invoice lines data before insertion
            cleaned_lines = self._clean_invoice_lines(extracted_invoice.get("lines", []))
            line_count = await self._replace_invoice_lines(invoice_id, cleaned_lines)
            
            # Now update status to "parsed" after invoice lines are successfully extracted
            # Status should be "parsed" after extraction, NOT "needs_review"
            # "needs_review" is only set by validation service if there are issues
            if line_count > 0:
                await self._update_invoice_status_to_parsed(invoice_id)
            else:
                logger.warning(f"No invoice lines extracted for {invoice_id}, keeping status as 'received'")
            
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
            # Keep status as "received" if parsing fails - don't set to "needs_review"
            # Status should only be set to "needs_review" by validation service after validation
            # This allows the invoice to be retried for parsing
            raise
    
    async def _update_invoice_header_fields(
        self, 
        invoice_id: UUID, 
        extracted_data: Dict[str, Any]
    ):
        """Update invoice table with extracted header fields (without changing status)"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            
            # Parse date to ISO format if present
            invoice_date = extracted_data.get("invoice_date")
            if invoice_date:
                invoice_date = self._parse_date(invoice_date)
            
            update_data = {
                "supplier_name": extracted_data.get("supplier_name"),
                "invoice_number": extracted_data.get("invoice_number"),
                "invoice_date": invoice_date,  # Now in ISO format or None
                "currency": extracted_data.get("currency"),
                "subtotal_amount": extracted_data.get("subtotal_amount"),
                "tax_amount": extracted_data.get("tax_amount"),
                "total_amount": extracted_data.get("total_amount"),
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            if not update_data:
                logger.warning(f"No header fields to update for invoice {invoice_id}")
                return
            
            invoices_table.update(update_data).eq("id", str(invoice_id)).execute()
            
            logger.info(f"Updated invoice {invoice_id} with extracted header fields")
            
        except Exception as e:
            logger.error(f"Failed to update invoice header fields: {e}")
            raise
    
    def _clean_invoice_lines(self, lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean and normalize invoice lines data before insertion
        - Convert vat_percentage from "25%" to 25.0 (numeric)
        - Ensure numeric fields are proper numbers or None
        - Handle string numbers that need conversion
        """
        cleaned_lines = []
        for line in lines:
            cleaned_line = line.copy()
            
            # Clean vat_percentage: remove % sign and convert to float
            vat_percentage = cleaned_line.get("vat_percentage")
            if vat_percentage:
                if isinstance(vat_percentage, str):
                    # Remove % sign and whitespace
                    vat_str = vat_percentage.replace('%', '').strip()
                    try:
                        cleaned_line["vat_percentage"] = float(vat_str)
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse vat_percentage: {vat_percentage}, setting to None")
                        cleaned_line["vat_percentage"] = None
                elif isinstance(vat_percentage, (int, float)):
                    cleaned_line["vat_percentage"] = float(vat_percentage)
                else:
                    cleaned_line["vat_percentage"] = None
            else:
                cleaned_line["vat_percentage"] = None
            
            # Ensure numeric fields are proper numbers
            numeric_fields = ["quantity", "unit_price", "discount", "discount_total", "net_amount", "line_total"]
            for field in numeric_fields:
                value = cleaned_line.get(field)
                if value is not None:
                    if isinstance(value, str):
                        # Try to convert string to float
                        try:
                            # Remove any currency symbols, spaces, and handle comma as decimal
                            cleaned_value = value.replace(',', '.').replace(' ', '').replace('€', '').replace('$', '').replace('kr', '').replace('DKK', '').replace('EUR', '')
                            cleaned_line[field] = float(cleaned_value)
                        except (ValueError, TypeError):
                            logger.warning(f"Could not parse {field}: {value}, setting to None")
                            cleaned_line[field] = None
                    elif isinstance(value, (int, float)):
                        cleaned_line[field] = float(value)
                    else:
                        cleaned_line[field] = None
                else:
                    cleaned_line[field] = None
            
            cleaned_lines.append(cleaned_line)
        
        return cleaned_lines
    
    async def _update_invoice_status_to_parsed(self, invoice_id: UUID):
        """Update invoice status to 'parsed' after invoice lines are successfully extracted"""
        try:
            invoices_table = supabase_client.get_table("invoices")
            
            invoices_table.update({
                "status": "parsed",
                "parsed_at": datetime.now().isoformat()
            }).eq("id", str(invoice_id)).execute()
            
            logger.info(f"Updated invoice {invoice_id} status to 'parsed' after extracting invoice lines")
            
        except Exception as e:
            logger.error(f"Failed to update invoice status to parsed: {e}")
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
                    "unit": line.get("unit"),  # Unit of measure (e.g., "PCS", "STK")
                    "unit_price": line.get("unit_price"),
                    "discount": line.get("discount"),  # Discount amount per line
                    "discount_total": line.get("discount_total"),  # Total discount for the line
                    "net_amount": line.get("net_amount"),  # Net amount after discount
                    "vat_percentage": line.get("vat_percentage"),  # VAT percentage (numeric, not string with %)
                    "line_total": line.get("line_total"),
                    "currency": line.get("currency")
                }
                line_records.append(line_record)
            
            # Insert all lines - handle errors per line to ensure maximum insertion
            inserted_count = 0
            failed_count = 0
            for record in line_records:
                try:
                    invoice_lines_table.insert(record).execute()
                    inserted_count += 1
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to insert invoice line {record.get('line_no')} for invoice {invoice_id}: {e}")
                    # Continue inserting other lines even if one fails
            
            if failed_count > 0:
                logger.warning(f"Inserted {inserted_count} out of {len(line_records)} invoice lines for invoice {invoice_id}. {failed_count} lines failed.")
            else:
                logger.info(f"Replaced {inserted_count} invoice lines for invoice {invoice_id}")
            
            return inserted_count
            
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
