"""
Test for PDFParserService - End-to-End test with OpenAI
Tests: logo extraction, text extraction, table extraction, and OpenAI extraction
"""
import asyncio
import sys
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime

# Add parent directory to path so we can import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.pdf_parser import pdf_parser_service
from backend.supabase_client import supabase_client


async def test_pdf_parser():
    """Test PDF parser service end-to-end with OpenAI extraction"""
    print("=" * 60)
    print("Testing PDFParserService - End-to-End with OpenAI")
    print("=" * 60)
    
    # Path to test PDF file
    test_pdf_path = Path(__file__).parent / "test.PDF"
    
    if not test_pdf_path.exists():
        print(f"\n❌ Error: test.PDF not found at {test_pdf_path}")
        print("   Please ensure test.PDF is in the backend/ directory")
        return False
    
    print(f"\n✓ Found test.PDF at: {test_pdf_path}")
    print(f"  File size: {test_pdf_path.stat().st_size:,} bytes")
    
    try:
        # Read PDF file
        print("\n1. Reading PDF file...")
        with open(test_pdf_path, "rb") as f:
            pdf_content = f.read()
        print(f"   ✓ Read {len(pdf_content):,} bytes")
        
        # Step 1: Extract logo image
        print("\n2. Extracting logo image from first page top area...")
        logo_image = pdf_parser_service.extract_logo_image(pdf_content)
        
        if logo_image:
            print(f"   ✓ Logo image extracted: {len(logo_image):,} bytes")
            print(f"   ✓ Format: PNG")
            # Optionally save logo for inspection
            logo_path = Path(__file__).parent / "extracted_logo.png"
            with open(logo_path, "wb") as f:
                f.write(logo_image)
            print(f"   ✓ Saved logo to: {logo_path}")
        else:
            print("   ⚠ No logo image could be extracted")
            print("   (This is okay - some PDFs may not have extractable images)")
        
        # Step 2: Extract text and tables
        print("\n3. Extracting text and tables from PDF...")
        extracted_data = pdf_parser_service.extract_text_from_pdf(pdf_content)
        
        print(f"   ✓ Extracted data from {extracted_data['page_count']} page(s)")
        print(f"   ✓ Found {len(extracted_data['tables'])} table(s)")
        
        # Step 3: Display extracted text
        print("\n4. Extracted Text Content:")
        print("-" * 60)
        text = extracted_data["text"]
        if text and text.strip():
            # Show first 1500 characters, then indicate if more
            display_text = text[:1500] if len(text) > 1500 else text
            print(display_text)
            if len(text) > 1500:
                print(f"\n... (showing first 1500 of {len(text)} characters)")
            print(f"\n   Total text length: {len(text):,} characters")
        else:
            print("   (No text extracted)")
            print("   ⚠ This PDF might be image-based/scanned")
        
        # Step 4: Display extracted tables
        print("\n5. Extracted Tables:")
        print("-" * 60)
        if extracted_data["tables"]:
            for i, table in enumerate(extracted_data["tables"], 1):
                print(f"\nTable #{i} ({len(table)} rows):")
                # Show first 15 rows
                for row_idx, row in enumerate(table[:15], 1):
                    # Format row nicely
                    row_str = " | ".join(str(cell) if cell else "" for cell in row)
                    print(f"  Row {row_idx}: {row_str}")
                if len(table) > 15:
                    print(f"  ... (showing first 15 of {len(table)} rows)")
        else:
            print("   (No tables found)")
        
        # Step 5: Prepare data for OpenAI
        print("\n6. Preparing data for OpenAI...")
        print("-" * 60)
        print("   ✓ Logo image: " + ("Available" if logo_image else "Not available"))
        print(f"   ✓ Raw text: {len(text):,} characters")
        print(f"   ✓ Tables: {len(extracted_data['tables'])} table(s)")
        
        # Prepare text with tables
        raw_text = text
        if extracted_data.get("tables"):
            raw_text += "\n\nTables:\n"
            for i, table in enumerate(extracted_data["tables"], 1):
                raw_text += f"\nTable {i}:\n"
                for row in table:
                    raw_text += " | ".join(str(cell) if cell else "" for cell in row) + "\n"
            print(f"   ✓ Combined text with tables: {len(raw_text):,} characters")
        
        # Step 6: Call OpenAI for extraction
        print("\n7. Calling OpenAI for invoice extraction...")
        print("-" * 60)
        try:
            extracted_invoice = await pdf_parser_service.call_openai_for_extraction(
                logo_image,
                raw_text,
                model=pdf_parser_service.default_model
            )
            print(f"   ✓ Successfully extracted invoice data using {pdf_parser_service.default_model}")
            
            # Step 7: Display extracted invoice data
            print("\n8. Extracted Invoice Data:")
            print("=" * 60)
            print(json.dumps(extracted_invoice, indent=2, ensure_ascii=False))
            
            # Step 8: Display formatted summary
            print("\n9. Formatted Invoice Summary:")
            print("=" * 60)
            print(f"  Supplier Name: {extracted_invoice.get('supplier_name', 'N/A')}")
            print(f"  Invoice Number: {extracted_invoice.get('invoice_number', 'N/A')}")
            print(f"  Invoice Date: {extracted_invoice.get('invoice_date', 'N/A')}")
            print(f"  Currency: {extracted_invoice.get('currency', 'N/A')}")
            print(f"  Subtotal: {extracted_invoice.get('subtotal_amount', 'N/A')}")
            print(f"  Tax Amount: {extracted_invoice.get('tax_amount', 'N/A')}")
            print(f"  Total Amount: {extracted_invoice.get('total_amount', 'N/A')}")
            
            lines = extracted_invoice.get('lines', [])
            print(f"\n  Invoice Lines: {len(lines)}")
            if lines:
                print("  " + "-" * 58)
                for line in lines[:10]:  # Show first 10 lines
                    print(f"    Line {line.get('line_no', 'N/A')}:")
                    print(f"      SKU: {line.get('sku', 'N/A')}")
                    print(f"      Product: {line.get('product_name', 'N/A')}")
                    print(f"      Description: {line.get('description', 'N/A')}")
                    print(f"      Quantity: {line.get('quantity', 'N/A')}")
                    print(f"      Unit Price: {line.get('unit_price', 'N/A')}")
                    print(f"      Line Total: {line.get('line_total', 'N/A')}")
                    print()
                if len(lines) > 10:
                    print(f"    ... (showing first 10 of {len(lines)} lines)")
            
            warnings = extracted_invoice.get('warnings', [])
            if warnings:
                print(f"\n  Warnings ({len(warnings)}):")
                for warning in warnings:
                    print(f"    ⚠ {warning}")
            
        except ValueError as e:
            if "OpenAI API key" in str(e):
                print(f"   ❌ Error: {e}")
                print("   Please set OPENAI_API_KEY in your .env file")
                return False
            else:
                raise
        except Exception as e:
            print(f"   ❌ Error calling OpenAI: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Final Summary
        print("\n" + "=" * 60)
        print("📊 End-to-End Test Summary:")
        print("=" * 60)
        print(f"  PDF File: {test_pdf_path.name}")
        print(f"  File Size: {len(pdf_content):,} bytes")
        print(f"  Pages: {extracted_data['page_count']}")
        print(f"  Logo Image: {'✓ Extracted' if logo_image else '✗ Not available'}")
        if logo_image:
            print(f"    - Size: {len(logo_image):,} bytes")
        print(f"  Text Length: {len(text):,} characters")
        print(f"  Tables Found: {len(extracted_data['tables'])}")
        print(f"  OpenAI Model: {pdf_parser_service.default_model}")
        print(f"  Supplier: {extracted_invoice.get('supplier_name', 'N/A')}")
        print(f"  Invoice Number: {extracted_invoice.get('invoice_number', 'N/A')}")
        print(f"  Total Amount: {extracted_invoice.get('total_amount', 'N/A')} {extracted_invoice.get('currency', '')}")
        print(f"  Lines Extracted: {len(extracted_invoice.get('lines', []))}")
        
        print("\n✅ End-to-End test completed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_insert_invoice_data():
    """Test inserting invoice data into invoices and invoice_lines tables"""
    print("=" * 60)
    print("Testing Invoice Data Insertion")
    print("=" * 60)
    
    try:
        # Step 1: Create a test invoice record
        print("\n1. Creating test invoice record...")
        invoice_id = uuid4()
        invoice_data = {
            "id": str(invoice_id),
            "source_provider": "test",
            "source_message_id": f"test-{datetime.now().isoformat()}",
            "storage_bucket": "pdfs",
            "storage_path": "test/test_invoice.pdf",
            "status": "received",
        }
        
        invoices_table = supabase_client.get_table("invoices")
        result = invoices_table.insert(invoice_data).execute()
        
        if result.data:
            print(f"   ✓ Created invoice: {invoice_id}")
            print(f"   ✓ Invoice status: {result.data[0].get('status')}")
        else:
            print("   ❌ Failed to create invoice")
            return False
        
        # Step 2: Prepare test extracted invoice data
        print("\n2. Preparing test extracted invoice data...")
        extracted_data = {
            "supplier_name": "Test Supplier",
            "invoice_number": "TEST-001",
            "invoice_date": "2024-01-15",
            "currency": "EUR",
            "subtotal_amount": 1000.00,
            "tax_amount": 200.00,
            "total_amount": 1200.00,
            "lines": [
                {
                    "line_no": 1,
                    "sku": "SKU-001",
                    "product_name": "Test Product 1",
                    "description": "Test Description 1",
                    "quantity": 10.0,
                    "unit_price": 50.0,
                    "line_total": 500.0
                },
                {
                    "line_no": 2,
                    "sku": "SKU-002",
                    "product_name": "Test Product 2",
                    "description": "Test Description 2",
                    "quantity": 5.0,
                    "unit_price": 100.0,
                    "line_total": 500.0
                }
            ]
        }
        
        print(f"   ✓ Supplier: {extracted_data['supplier_name']}")
        print(f"   ✓ Invoice Number: {extracted_data['invoice_number']}")
        print(f"   ✓ Total Amount: {extracted_data['total_amount']} {extracted_data['currency']}")
        print(f"   ✓ Lines: {len(extracted_data['lines'])}")
        
        # Step 3: Update invoice with extracted data
        print("\n3. Updating invoice with extracted header data...")
        await pdf_parser_service._update_invoice(invoice_id, extracted_data)
        
        # Verify invoice was updated
        updated_invoice = invoices_table.select("*").eq("id", str(invoice_id)).limit(1).execute()
        if updated_invoice.data:
            invoice = updated_invoice.data[0]
            print(f"   ✓ Invoice updated successfully")
            print(f"   ✓ Status: {invoice.get('status')}")
            print(f"   ✓ Supplier: {invoice.get('supplier_name')}")
            print(f"   ✓ Invoice Number: {invoice.get('invoice_number')}")
            print(f"   ✓ Total: {invoice.get('total_amount')} {invoice.get('currency')}")
        else:
            print("   ❌ Failed to verify invoice update")
            return False
        
        # Step 4: Insert invoice lines
        print("\n4. Inserting invoice lines...")
        line_count = await pdf_parser_service._replace_invoice_lines(
            invoice_id, 
            extracted_data["lines"]
        )
        
        print(f"   ✓ Inserted {line_count} invoice lines")
        
        # Step 5: Verify invoice lines were inserted
        print("\n5. Verifying invoice lines...")
        invoice_lines_table = supabase_client.get_table("invoice_lines")
        lines_result = invoice_lines_table.select("*").eq("invoice_id", str(invoice_id)).order("line_no").execute()
        
        if lines_result.data:
            lines = lines_result.data
            print(f"   ✓ Found {len(lines)} invoice lines in database")
            
            for line in lines:
                print(f"\n   Line {line.get('line_no')}:")
                print(f"     - ID: {line.get('id')}")
                print(f"     - SKU: {line.get('sku')}")
                print(f"     - Product: {line.get('product_name')}")
                print(f"     - Quantity: {line.get('quantity')}")
                print(f"     - Unit Price: {line.get('unit_price')}")
                print(f"     - Line Total: {line.get('line_total')}")
                print(f"     - Status: {line.get('status')} (should be NULL initially)")
                
                # Verify status is None
                if line.get('status') is not None:
                    print(f"     ⚠ Warning: Status is not NULL (expected NULL before validation)")
                else:
                    print(f"     ✓ Status is NULL (correct)")
        else:
            print("   ❌ No invoice lines found")
            return False
        
        # Step 6: Cleanup - Delete test invoice and lines
        print("\n6. Cleaning up test data...")
        try:
            invoice_lines_table.delete().eq("invoice_id", str(invoice_id)).execute()
            invoices_table.delete().eq("id", str(invoice_id)).execute()
            print(f"   ✓ Deleted test invoice and lines")
        except Exception as e:
            print(f"   ⚠ Warning: Failed to cleanup test data: {e}")
            print(f"   Please manually delete invoice {invoice_id}")
        
        # Final Summary
        print("\n" + "=" * 60)
        print("📊 Invoice Data Insertion Test Summary:")
        print("=" * 60)
        print(f"  Invoice ID: {invoice_id}")
        print(f"  Supplier: {extracted_data['supplier_name']}")
        print(f"  Invoice Number: {extracted_data['invoice_number']}")
        print(f"  Total Amount: {extracted_data['total_amount']} {extracted_data['currency']}")
        print(f"  Lines Inserted: {line_count}")
        print(f"  Lines Verified: {len(lines_result.data) if lines_result.data else 0}")
        print("\n✅ Invoice data insertion test completed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "insert":
        # Run insertion test
        asyncio.run(test_insert_invoice_data())
    else:
        # Run default extraction test
        asyncio.run(test_pdf_parser())
