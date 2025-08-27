import unittest
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


class TestSalesInvoiceFields(unittest.TestCase):
    """Unit tests for Sales Invoice custom fields"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        # Ensure custom fields are created
        from jofotara_integration.custom.sales_invoice import add_custom_fields
        add_custom_fields()
        frappe.db.commit()
    
    def test_custom_icv_counter_field_exists(self):
        """Test that custom_icv_counter field exists in Sales Invoice"""
        # Check if field exists in custom fields
        field_exists = frappe.db.exists("Custom Field", {
            "dt": "Sales Invoice",
            "fieldname": "custom_icv_counter"
        })
        
        self.assertTrue(field_exists, "custom_icv_counter field should exist in Sales Invoice")
    
    def test_custom_icv_counter_field_properties(self):
        """Test custom_icv_counter field properties"""
        try:
            field = frappe.get_doc("Custom Field", {
                "dt": "Sales Invoice",
                "fieldname": "custom_icv_counter"
            })
            
            # Test field properties
            self.assertEqual(field.fieldtype, "Int")
            self.assertEqual(field.label, "JoFotara ICV")
            self.assertEqual(field.read_only, 1)
            self.assertEqual(field.no_copy, 1)
            self.assertIn("Invoice Counter Value", field.description)
            
        except frappe.DoesNotExistError:
            self.fail("custom_icv_counter field not found")
    
    def test_field_in_sales_invoice_meta(self):
        """Test that field appears in Sales Invoice meta"""
        meta = frappe.get_meta("Sales Invoice")
        field = meta.get_field("custom_icv_counter")
        
        self.assertIsNotNone(field, "custom_icv_counter field should be in Sales Invoice meta")
        self.assertEqual(field.fieldtype, "Int")
        self.assertEqual(field.read_only, 1)
    
    def test_field_value_assignment(self):
        """Test that ICV field can be set and retrieved"""
        # Create test company first
        test_company = self._get_or_create_test_company()
        
        try:
            # Create a test sales invoice
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": "_Test Customer",
                "company": test_company.name,
                "posting_date": frappe.utils.today(),
                "items": [{
                    "item_code": "_Test Item",
                    "qty": 1,
                    "rate": 100
                }]
            })
            
            # Test setting ICV value
            invoice.custom_icv_counter = "TEST-123"
            invoice.insert()
            
            # Retrieve and verify
            saved_invoice = frappe.get_doc("Sales Invoice", invoice.name)
            self.assertEqual(saved_invoice.custom_icv_counter, "TEST-123")
            
        except Exception as e:
            self.fail(f"Failed to test field value assignment: {str(e)}")
        finally:
            # Clean up
            self._cleanup_test_invoices()
    
    def test_field_read_only_validation(self):
        """Test that field is properly read-only"""
        meta = frappe.get_meta("Sales Invoice")
        field = meta.get_field("custom_icv_counter")
        
        self.assertEqual(field.read_only, 1, "custom_icv_counter should be read-only")
    
    def test_field_no_copy_validation(self):
        """Test that field has no_copy set"""
        try:
            field = frappe.get_doc("Custom Field", {
                "dt": "Sales Invoice",
                "fieldname": "custom_icv_counter"
            })
            
            self.assertEqual(field.no_copy, 1, "custom_icv_counter should have no_copy=1")
            
        except frappe.DoesNotExistError:
            self.fail("custom_icv_counter field not found")
    
    def test_field_default_value(self):
        """Test field default behavior"""
        test_company = self._get_or_create_test_company()
        
        try:
            # Create invoice without setting ICV
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": "_Test Customer",
                "company": test_company.name,
                "posting_date": frappe.utils.today(),
                "items": [{
                    "item_code": "_Test Item",
                    "qty": 1,
                    "rate": 100
                }]
            })
            
            invoice.insert()
            
            # Should be empty string or None initially
            self.assertIn(invoice.custom_icv_counter, ["", None])
            
        except Exception as e:
            self.fail(f"Failed to test field default value: {str(e)}")
        finally:
            self._cleanup_test_invoices()
    
    def test_field_string_validation(self):
        """Test that field accepts string values with company abbreviation format"""
        test_company = self._get_or_create_test_company()
        
        try:
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": "_Test Customer",
                "company": test_company.name,
                "posting_date": frappe.utils.today(),
                "items": [{
                    "item_code": "_Test Item",
                    "qty": 1,
                    "rate": 100
                }]
            })
            
            # Test various string values with company abbreviation format
            test_values = ["TEST-1", "TEST-100", "TEST-999", "TEST-1234567"]
            
            for value in test_values:
                invoice.custom_icv_counter = value
                invoice.insert()
                
                saved_invoice = frappe.get_doc("Sales Invoice", invoice.name)
                self.assertEqual(saved_invoice.custom_icv_counter, value)
                
                # Delete for next iteration
                frappe.delete_doc("Sales Invoice", invoice.name, force=True)
                
        except Exception as e:
            self.fail(f"Failed to test string validation: {str(e)}")
        finally:
            self._cleanup_test_invoices()
    
    def _get_or_create_test_company(self):
        """Helper to get or create test company"""
        try:
            return frappe.get_doc("Company", "Test Sales Invoice Company")
        except frappe.DoesNotExistError:
            company = frappe.get_doc({
                "doctype": "Company",
                "company_name": "Test Sales Invoice Company",
                "abbr": "TSIC",
                "default_currency": "USD"
            })
            company.insert()
            frappe.db.commit()
            return company
    
    def _cleanup_test_invoices(self):
        """Helper to clean up test invoices"""
        try:
            invoices = frappe.db.sql("""
                SELECT name FROM `tabSales Invoice` 
                WHERE company = 'Test Sales Invoice Company'
            """)
            
            for invoice in invoices:
                frappe.delete_doc("Sales Invoice", invoice[0], force=True)
            
            frappe.db.commit()
        except Exception:
            pass
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        try:
            # Clean up test company
            if frappe.db.exists("Company", "Test Sales Invoice Company"):
                frappe.delete_doc("Company", "Test Sales Invoice Company", force=True)
            frappe.db.commit()
        except:
            pass


if __name__ == "__main__":
    unittest.main()
