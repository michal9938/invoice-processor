"""
Email Polling Service
Polls Microsoft Graph API for invoice emails with PDF attachments.
Uploads PDFs to pdfs bucket, inserts invoices (source_message_id, storage_path, status=received),
writes EMAIL_INGESTED/PDF_STORED audit log entries, and marks emails as read.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4
import httpx
from backend.core.config import settings
from backend.core.logging import logger
from backend.supabase_client import supabase_client


class EmailPollingService:
    """Service for polling Microsoft Graph API for invoice emails"""
    
    def __init__(self):
        """Initialize the email polling service"""
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.processed_message_ids: set = set()  # Track processed emails for deduplication
    
    async def get_access_token(self) -> str:
        """
        Obtain OAuth2 access token from Microsoft Graph API
        Uses client credentials flow for app-only authentication
        
        Returns:
            Access token string
        """
        # Check if token is still valid
        if self.access_token and self.token_expires_at:
            if datetime.now() < self.token_expires_at - timedelta(minutes=5):
                return self.access_token
        
        # Request new token
        token_url = f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token"
        
        data = {
            "client_id": settings.GRAPH_CLIENT_ID,
            "client_secret": settings.GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(token_url, data=data)
                response.raise_for_status()
                token_data = response.json()
                
                self.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info("Successfully obtained Microsoft Graph API access token")
                return self.access_token
                
        except Exception as e:
            logger.error(f"Failed to obtain access token: {e}")
            raise
    
    async def fetch_emails(self, max_emails: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch unread emails from the invoice mailbox
        
        Args:
            max_emails: Maximum number of emails to fetch (defaults to MAX_EMAILS_PER_RUN)
        
        Returns:
            List of email message dictionaries
        """
        max_emails = max_emails or settings.MAX_EMAILS_PER_RUN
        access_token = await self.get_access_token()
        
        # Microsoft Graph API endpoint for messages
        graph_url = f"https://graph.microsoft.com/v1.0/users/{settings.INVOICE_MAIL_ADDRESS}/messages"
        
        # Filter for unread messages
        # Note: hasAttachments cannot be used in $filter, so we filter in code after fetching
        params = {
            "$filter": "isRead eq false",
            "$top": str(max_emails * 2),  # Fetch more to account for filtering
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,sender,receivedDateTime,hasAttachments"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(graph_url, headers=headers, params=params)
                
                # Better error handling - show actual error response
                if response.status_code != 200:
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("error", {}).get("message", str(error_data))
                    except:
                        error_detail = response.text
                    
                    logger.error(f"Failed to fetch emails: {response.status_code} - {error_detail}")
                    raise Exception(f"Graph API error {response.status_code}: {error_detail}")
                
                data = response.json()
                all_emails = data.get("value", [])
                
                # Filter for emails with attachments (hasAttachments can't be used in $filter)
                emails = [email for email in all_emails if email.get("hasAttachments", False)]
                
                # Limit to requested number
                emails = emails[:max_emails]
                
                # logger.info(f"Fetched {len(emails)} unread emails with attachments (from {len(all_emails)} total unread)")
                return emails
                
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            raise
    
    async def save_pdf_to_pdfs_bucket(self, pdf_content: bytes, filename: str) -> str:
        """
        Save PDF to the pdfs bucket in Supabase storage immediately after finding it
        
        Args:
            pdf_content: PDF file content as bytes
            filename: Original filename
        
        Returns:
            Storage path/URL of the stored file (just the filename)
        """
        pdfs_storage = supabase_client.get_pdfs_storage()
        
        # Generate unique filename with timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = filename.replace(" ", "_").replace("/", "_")
        file_path = f"{timestamp}_{safe_filename}"
        
        try:
            # Upload file directly to pdfs bucket root
            pdfs_storage.upload(file_path, pdf_content, file_options={"content-type": "application/pdf"})
            
            logger.info(f"Stored PDF in pdfs bucket: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to store PDF in pdfs bucket: {e}")
            raise
    
    async def get_email_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Get PDF attachments from an email message and save them to pdfs bucket immediately
        
        Args:
            message_id: Microsoft Graph message ID
        
        Returns:
            List of attachment dictionaries with storage_path added
        """
        access_token = await self.get_access_token()
        graph_url = f"https://graph.microsoft.com/v1.0/users/{settings.INVOICE_MAIL_ADDRESS}/messages/{message_id}/attachments"
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(graph_url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                attachments = data.get("value", [])
                
                # Filter for PDF attachments only
                pdf_attachments = [
                    att for att in attachments 
                    if att.get("contentType") == "application/pdf" or 
                       att.get("name", "").lower().endswith(".pdf")
                ]
                
                logger.info(f" - - - I Found {len(pdf_attachments)} PDF attachments in message {message_id}")
                
                # Download and save PDF to pdfs bucket immediately (only one PDF per email)
                if pdf_attachments:
                    attachment = pdf_attachments[0]  # Only process first PDF
                    try:
                        attachment_id = attachment.get("id")
                        filename = attachment.get("name", f"invoice_{message_id}.pdf")
                        
                        # Download PDF content
                        pdf_content = await self.download_attachment(message_id, attachment_id)
                        
                        # Save to pdfs bucket (directly to root, no folders)
                        storage_path = await self.save_pdf_to_pdfs_bucket(pdf_content, filename)
                        
                        attachment["storage_path"] = storage_path
                        
                    except Exception as e:
                        logger.error(f"Failed to save PDF {attachment.get('name')} to pdfs bucket: {e}")
                        attachment["storage_path"] = None
                
                return pdf_attachments
                
        except Exception as e:
            logger.error(f"Failed to get attachments for message {message_id}: {e}")
            raise
    
    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """
        Download attachment content from Microsoft Graph API
        
        Args:
            message_id: Microsoft Graph message ID
            attachment_id: Attachment ID
        
        Returns:
            Attachment content as bytes
        """
        access_token = await self.get_access_token()
        graph_url = f"https://graph.microsoft.com/v1.0/users/{settings.INVOICE_MAIL_ADDRESS}/messages/{message_id}/attachments/{attachment_id}/$value"
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(graph_url, headers=headers)
                response.raise_for_status()
                
                content = response.content
                return content
                
        except Exception as e:
            logger.error(f"Failed to download attachment {attachment_id}: {e}")
            raise
    
    async def insert_invoice(self, source_message_id: str, storage_path: str) -> str:
        """
        Insert invoice into invoices table.
        
        Args:
            source_message_id: Microsoft Graph message ID
            storage_path: Path in pdfs bucket
        
        Returns:
            Invoice UUID
        """
        invoice_id = str(uuid4())
        invoice_data = {
            "id": invoice_id,
            "source_message_id": source_message_id,
            "storage_bucket": "pdfs",
            "storage_path": storage_path,
            "status": "received",
        }
        try:
            supabase_client.get_table("invoices").insert(invoice_data).execute()
            logger.info(f"Inserted invoice {invoice_id} (source_message_id={source_message_id})")
            return invoice_id
        except Exception as e:
            logger.error(f"Failed to insert invoice: {e}")
            raise

    def _insert_audit_log(self, action: str, invoice_id: str, details: str):
        """Insert a single audit_log row for an invoice."""
        try:
            audit_log_table = supabase_client.get_table("audit_log")
            audit_log_table.insert({
                "entity_type": "invoice",
                "entity_id": invoice_id,
                "action": action,
                "details": {"message": details},
                "performed_by": None,
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to insert audit_log {action}: {e}")

    async def mark_emails_as_read(self, message_id: str):
        """
        Mark email as read (Microsoft Graph API).
        
        Args:
            message_id: Microsoft Graph message ID
        """
        access_token = await self.get_access_token()
        graph_url = f"https://graph.microsoft.com/v1.0/users/{settings.INVOICE_MAIL_ADDRESS}/messages/{message_id}"
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                response = await client.patch(graph_url, headers=headers, json={"isRead": True})
                response.raise_for_status()
                logger.info(f"Marked email {message_id} as read")
        except Exception as e:
            logger.warning(f"Failed to mark email as read: {e}")

    async def process_email(self, email_data: Dict[str, Any]) -> bool:
        """
        Process a single email with invoice PDF: upload PDF to pdfs, insert invoice, audit, mark read.
        
        Args:
            email_data: Email message data from Graph API
        
        Returns:
            True if processing succeeded, False otherwise
        """
        message_id = email_data.get("id")
        
        if message_id in self.processed_message_ids:
            logger.info(f"Email {message_id} already processed, skipping")
            return False
        
        try:
            attachments = await self.get_email_attachments(message_id)
            if not attachments:
                return False
            
            attachment = attachments[0]
            storage_path = attachment.get("storage_path")
            if not storage_path:
                return False
            
            filename = attachment.get("name", f"invoice_{message_id}.pdf")
            file_size = attachment.get("size", 0)
            max_size_bytes = settings.MAX_PDF_SIZE_MB * 1024 * 1024
            if file_size > max_size_bytes:
                logger.warning(f"PDF {filename} exceeds size limit: {file_size} bytes")
                return False
            
            # Insert invoice (source_message_id, storage_bucket='pdfs', storage_path, status='received')
            invoice_id = await self.insert_invoice(message_id, storage_path)
            
            # Audit: EMAIL_INGESTED, PDF_STORED on invoice
            self._insert_audit_log("EMAIL_INGESTED", invoice_id, f"Email {message_id} ingested; PDF stored at {storage_path}")
            self._insert_audit_log("PDF_STORED", invoice_id, f"PDF stored in pdfs bucket: {storage_path}")
            
            await self.mark_emails_as_read(message_id)
            self.processed_message_ids.add(message_id)
            
            logger.info(f"Processed email {message_id}, invoice {invoice_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process email {message_id}: {e}")
            return False
    
    async def poll_and_process_emails(self) -> Dict[str, Any]:
        """
        Main polling function: fetch emails and process them
        
        Returns:
            Dictionary with processing statistics
        """
        processed_count = 0
        failed_count = 0
        try:
            emails = await self.fetch_emails()
            for email in emails:
                success = await self.process_email(email)
                if success:
                    processed_count += 1
                else:
                    failed_count += 1
            
            result = {
                "total_emails": len(emails),
                "processed": processed_count,
                "failed": failed_count,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Email polling completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Email polling failed: {e}")
            raise


# Global service instance
email_polling_service = EmailPollingService()

