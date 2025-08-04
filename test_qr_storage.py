#!/usr/bin/env python3
"""
Test script to verify QR code storage functionality
"""

import frappe
import base64

def test_qr_code_storage():
    """Test that QR code data can be stored and retrieved correctly"""
    
    # Initialize Frappe
    frappe.init(site='site1.local')
    frappe.connect()
    
    try:
        # Create a test Sales Invoice
        test_invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "company": "_Test Company",
            "customer": "_Test Customer",
            "posting_date": frappe.utils.today(),
            "due_date": frappe.utils.add_days(frappe.utils.today(), 30),
            "currency": "USD",
            "items": [{
                "item_code": "_Test Item",
                "item_name": "_Test Item",
                "description": "_Test Item",
                "qty": 1,
                "rate": 100,
                "amount": 100
            }]
        })
        
        test_invoice.insert()
        print(f"Created test invoice: {test_invoice.name}")
        
        # Test QR code storage
        test_qr_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        # Update the invoice with QR code data
        frappe.db.set_value('Sales Invoice', test_invoice.name, {
            'custom_einvoice_qr_code': test_qr_data,
            'custom_einvoice_status': 'Accepted',
            'custom_einvoice_uuid': 'test-uuid-123'
        })
        frappe.db.commit()
        
        # Retrieve and verify
        updated_invoice = frappe.get_doc('Sales Invoice', test_invoice.name)
        
        print(f"QR Code stored: {bool(updated_invoice.custom_einvoice_qr_code)}")
        print(f"QR Code length: {len(updated_invoice.custom_einvoice_qr_code) if updated_invoice.custom_einvoice_qr_code else 0}")
        print(f"Status: {updated_invoice.custom_einvoice_status}")
        print(f"UUID: {updated_invoice.custom_einvoice_uuid}")
        
        # Test base64 validation
        if updated_invoice.custom_einvoice_qr_code:
            try:
                decoded = base64.b64decode(updated_invoice.custom_einvoice_qr_code)
                print(f"Base64 validation: PASS (decoded {len(decoded)} bytes)")
            except Exception as e:
                print(f"Base64 validation: FAIL - {e}")
        
        # Clean up
        test_invoice.delete()
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        frappe.db.rollback()
    finally:
        frappe.destroy()

if __name__ == "__main__":
    test_qr_code_storage() 