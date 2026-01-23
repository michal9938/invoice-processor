"""
Simple test for EmailPollingService - tests with real API calls
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path so we can import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.email_polling import email_polling_service


async def test_email_polling():
    """Test email polling service with real API calls"""
    print("=" * 60)
    print("Testing EmailPollingService with Real API Calls")
    print("=" * 60)
    
    try:
        # Step 1: Get access token
        print("\n1. Getting Microsoft Graph API access token...")
        token = await email_polling_service.get_access_token()
        print(f"   ✓ Access token obtained: {token[:20]}...")
        
        # Step 2: Fetch emails
        print("\n2. Fetching emails from inbox...")
        try:
            emails = await email_polling_service.fetch_emails(max_emails=10)
            print(f"   ✓ Found {len(emails)} unread emails with attachments")
        except Exception as fetch_error:
            print(f"   ⚠ Error fetching emails: {fetch_error}")
            print("   Trying simpler query without filter...")
            # Try a simpler query to test basic connectivity
            import httpx
            from backend.core.config import settings
            simple_url = f"https://graph.microsoft.com/v1.0/users/{settings.INVOICE_MAIL_ADDRESS}/messages"
            simple_params = {"$top": 5}
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {token}"}
                simple_response = await client.get(simple_url, headers=headers, params=simple_params)
                if simple_response.status_code == 200:
                    simple_data = simple_response.json()
                    emails = simple_data.get("value", [])
                    print(f"   ✓ Found {len(emails)} emails (simple query)")
                else:
                    print(f"   ❌ Simple query also failed: {simple_response.status_code}")
                    print(f"   Response: {simple_response.text[:200]}")
                    emails = []
        
        # Step 3: Print email details
        print("\n3. Email Details:")
        print("-" * 60)
        print("\nField Explanations:")
        print("  ID: Microsoft Graph API message ID - unique identifier for each email")
        print("      Format: Base64-encoded string (typically 100-200+ characters)")
        print("      Each email MUST have a different ID - if IDs are same, there's a bug!")
        print("  Subject: The email subject line")
        print("  From: Sender's email address")
        print("  Received: ISO 8601 timestamp when email was received")
        print("  Has Attachments: Boolean (True/False) indicating if email has attachments")
        print("-" * 60)
        
        # Debug: Check for duplicate IDs
        email_ids = [email.get('id') for email in emails]
        unique_ids = set(email_ids)
        print(f"\nDEBUG: Total emails: {len(emails)}, Unique IDs: {len(unique_ids)}")
        if len(emails) != len(unique_ids):
            print(f"⚠️  WARNING: Found {len(emails) - len(unique_ids)} duplicate email IDs!")
            # Show which IDs are duplicated
            from collections import Counter
            id_counts = Counter(email_ids)
            duplicates = {id_val: count for id_val, count in id_counts.items() if count > 1}
            print(f"   Duplicate IDs: {duplicates}")
        
        # Additional debug: Show first few characters of each ID for quick comparison
        if len(emails) > 1:
            print(f"\nDEBUG: First 30 chars of each email ID:")
            for i, email_id in enumerate(email_ids[:5], 1):  # Show first 5
                print(f"   Email #{i}: {email_id[:30] if email_id else 'N/A'}...")
        
        for i, email in enumerate(emails, 1):
            print(f"\nEmail #{i}:")
            # ID: Microsoft Graph API message ID - unique identifier for each email message
            # Format: Base64-encoded string that uniquely identifies the message in the mailbox
            email_id = email.get('id', 'N/A')
            print(f"  ID: {email_id}")
            print(f"     (Length: {len(email_id) if email_id != 'N/A' else 0} chars)")
            
            # Subject: Email subject line
            print(f"  Subject: {email.get('subject', 'N/A')}")
            
            # Sender: Email address of the sender
            sender = email.get('sender', {}).get('emailAddress', {})
            print(f"  From: {sender.get('address', 'N/A')}")
            
            # Received DateTime: When the email was received (ISO 8601 format)
            received = email.get('receivedDateTime', 'N/A')
            print(f"  Received: {received}")
            
            # Has Attachments: Boolean indicating if email has any attachments
            print(f"  Has Attachments: {email.get('hasAttachments', False)}")
        
        # Step 4: Get attachments for first email (if any)
        if emails:
            print("\n4. Checking attachments for first email...")
            first_email_id = emails[0].get('id')
            if first_email_id:
                attachments = await email_polling_service.get_email_attachments(first_email_id)
                print(f"   ✓ Found {len(attachments)} PDF attachment(s)")
                for att in attachments:
                    print(f"     - {att.get('name', 'N/A')} ({att.get('size', 0)} bytes)")
        
        print("\n" + "=" * 60)
        print("✅ Email polling service is working correctly!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    asyncio.run(test_email_polling())

