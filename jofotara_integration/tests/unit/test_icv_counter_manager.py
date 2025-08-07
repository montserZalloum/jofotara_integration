import unittest
import frappe
from frappe.test_runner import make_test_records
from jofotara_integration.api.icv_counter import ICVCounterManager, icv_counter_manager


class TestICVCounterManager(unittest.TestCase):
    """Unit tests for ICV Counter Manager"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        # Create test company
        cls.test_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test ICV Company",
            "abbr": "TIC",
            "default_currency": "USD",
            "jofotara_is_active": 1,
            "jofotara_client_id": "test_client_123",
            "jofotara_secret_key": "test_secret_key",
            "jofotara_activity_serial": "12345",
            "current_icv_counter": 0
        })
        
        try:
            cls.test_company.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            cls.test_company = frappe.get_doc("Company", "Test ICV Company")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        try:
            if frappe.db.exists("Company", "Test ICV Company"):
                frappe.delete_doc("Company", "Test ICV Company", force=True)
            frappe.db.commit()
        except:
            pass
    
    def setUp(self):
        """Reset counter before each test"""
        frappe.db.set_value("Company", "Test ICV Company", "current_icv_counter", 0)
        frappe.db.commit()
    
    def test_get_next_icv_first_call(self):
        """Test getting first ICV returns 1"""
        counter_manager = ICVCounterManager()
        next_icv = counter_manager.get_next_icv("Test ICV Company")
        
        self.assertEqual(next_icv, 1)
        
        # Verify counter was updated in database
        current_counter = frappe.db.get_value("Company", "Test ICV Company", "current_icv_counter")
        self.assertEqual(current_counter, 1)
    
    def test_get_next_icv_sequential(self):
        """Test sequential ICV assignment"""
        counter_manager = ICVCounterManager()
        
        # Get first three ICVs
        icv1 = counter_manager.get_next_icv("Test ICV Company")
        icv2 = counter_manager.get_next_icv("Test ICV Company")
        icv3 = counter_manager.get_next_icv("Test ICV Company")
        
        self.assertEqual(icv1, 1)
        self.assertEqual(icv2, 2)
        self.assertEqual(icv3, 3)
        
        # Verify final counter state
        current_counter = frappe.db.get_value("Company", "Test ICV Company", "current_icv_counter")
        self.assertEqual(current_counter, 3)
    
    def test_get_next_icv_invalid_company(self):
        """Test error handling for invalid company"""
        counter_manager = ICVCounterManager()
        
        with self.assertRaises(Exception):
            counter_manager.get_next_icv("Nonexistent Company")
    
    def test_get_next_icv_empty_company(self):
        """Test error handling for empty company name"""
        counter_manager = ICVCounterManager()
        
        with self.assertRaises(Exception):
            counter_manager.get_next_icv("")
        
        with self.assertRaises(Exception):
            counter_manager.get_next_icv(None)
    
    def test_initialize_counter(self):
        """Test counter initialization"""
        counter_manager = ICVCounterManager()
        
        # Set counter to some value first
        frappe.db.set_value("Company", "Test ICV Company", "current_icv_counter", 5)
        frappe.db.commit()
        
        # Initialize counter
        result = counter_manager.initialize_counter("Test ICV Company")
        self.assertTrue(result)
        
        # Verify counter was reset to 0
        current_counter = frappe.db.get_value("Company", "Test ICV Company", "current_icv_counter")
        self.assertEqual(current_counter, 0)
        
        # Next ICV should be 1
        next_icv = counter_manager.get_next_icv("Test ICV Company")
        self.assertEqual(next_icv, 1)
    
    def test_get_current_counter(self):
        """Test reading current counter value"""
        counter_manager = ICVCounterManager()
        
        # Initially should be 0
        current = counter_manager.get_current_counter("Test ICV Company")
        self.assertEqual(current, 0)
        
        # After getting next ICV, should be 1
        counter_manager.get_next_icv("Test ICV Company")
        current = counter_manager.get_current_counter("Test ICV Company")
        self.assertEqual(current, 1)
        
        # Test with nonexistent company
        current = counter_manager.get_current_counter("Nonexistent Company")
        self.assertEqual(current, 0)
    
    def test_validate_counter_integrity_valid(self):
        """Test counter integrity validation with valid state"""
        counter_manager = ICVCounterManager()
        
        # Get some ICVs
        counter_manager.get_next_icv("Test ICV Company")
        counter_manager.get_next_icv("Test ICV Company")
        
        # Create mock sales invoices with matching ICVs
        self._create_test_sales_invoice("INV-001", 1)
        self._create_test_sales_invoice("INV-002", 2)
        
        try:
            # Validate integrity
            result = counter_manager.validate_counter_integrity("Test ICV Company")
            
            self.assertTrue(result["is_valid"])
            self.assertEqual(result["current_counter"], 2)
            self.assertEqual(result["max_icv_in_invoices"], 2)
            self.assertEqual(result["discrepancy"], 0)
        finally:
            # Clean up test invoices
            self._cleanup_test_sales_invoices()
    
    def test_validate_counter_integrity_invalid(self):
        """Test counter integrity validation with invalid state"""
        counter_manager = ICVCounterManager()
        
        # Set counter to lower value than existing invoices
        frappe.db.set_value("Company", "Test ICV Company", "current_icv_counter", 1)
        
        # Create mock sales invoice with higher ICV
        self._create_test_sales_invoice("INV-003", 3)
        
        try:
            # Validate integrity
            result = counter_manager.validate_counter_integrity("Test ICV Company")
            
            self.assertFalse(result["is_valid"])
            self.assertEqual(result["current_counter"], 1)
            self.assertEqual(result["max_icv_in_invoices"], 3)
        finally:
            # Clean up test invoices
            self._cleanup_test_sales_invoices()
    
    def test_global_instance(self):
        """Test that global instance works correctly"""
        # Test using global instance
        next_icv = icv_counter_manager.get_next_icv("Test ICV Company")
        self.assertEqual(next_icv, 1)
        
        # Verify it maintains state
        next_icv = icv_counter_manager.get_next_icv("Test ICV Company")
        self.assertEqual(next_icv, 2)
    
    def _create_test_sales_invoice(self, invoice_name, icv_value):
        """Helper to create test sales invoice"""
        try:
            # Check if invoice already exists
            if frappe.db.exists("Sales Invoice", invoice_name):
                return
            
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "name": invoice_name,
                "customer": "_Test Customer",
                "company": "Test ICV Company",
                "custom_icv_counter": icv_value,
                "docstatus": 1,  # Submitted
                "posting_date": frappe.utils.today(),
                "items": [{
                    "item_code": "_Test Item",
                    "qty": 1,
                    "rate": 100
                }]
            })
            invoice.insert()
            invoice.submit()
            frappe.db.commit()
        except Exception as e:
            # Skip if test data creation fails
            pass
    
    def _cleanup_test_sales_invoices(self):
        """Helper to clean up test sales invoices"""
        try:
            invoices = frappe.db.sql("""
                SELECT name FROM `tabSales Invoice` 
                WHERE company = 'Test ICV Company' 
                AND name LIKE 'INV-%'
            """)
            
            for invoice in invoices:
                frappe.delete_doc("Sales Invoice", invoice[0], force=True)
            
            frappe.db.commit()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
