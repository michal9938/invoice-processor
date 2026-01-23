"""
Supabase client initialization
Handles database, storage, and auth interactions with Supabase
"""
from supabase import create_client, Client
from backend.core.config import settings
from backend.core.logging import logger


class SupabaseClient:
    """Wrapper for Supabase client with helper methods"""
    
    def __init__(self):
        """Initialize Supabase client with service role key for admin operations"""
        try:
            # Ensure SUPABASE_URL has a trailing slash for storage operations
            supabase_url = settings.SUPABASE_URL
            if not supabase_url.endswith('/'):
                supabase_url = supabase_url + '/'
            
            self.client: Client = create_client(
                supabase_url,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    def get_client(self) -> Client:
        """Get the Supabase client instance"""
        return self.client
    
    def get_storage(self):
        """Get Supabase storage bucket for file operations"""
        return self.client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
    
    def get_pdfs_storage(self):
        """Get Supabase PDFs storage bucket for PDF files"""
        return self.client.storage.from_("pdfs")
    
    def get_table(self, table_name: str):
        """Get a Supabase table for database operations"""
        return self.client.table(table_name)


# Global Supabase client instance
supabase_client = SupabaseClient()

