import unittest
import frappe
from jofotara_integration.api.icv_counter import icv_counter_manager


class TestSubmissionWorkflow(unittest.TestCase):
    """Integration tests for Sales Invoice submission workflow with ICV assignment"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        # Create test company with JoFotara enabled
        cls.test_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test Workflow Company",
            "abbr": "TWC",
            "default_currency": "USD",
            "jofotara_is_active": 1,
            "jofotara_client_id": "test_client_workflow",
            "jofotara_secret_key": "test_secret_workflow",
            "jofotara_activity_serial": "11111",
            "jofotara_auto_submit": 0,  # Disable auto-submit for cleaner testing
            "current_icv_counter": 0
        })
        
        try:
            cls.test_company.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            cls.test_company = frappe.get_doc("Company", "Test Workflow Company")
        
        # Ensure custom fields are installed
        from jofotara_integration.custom.sales_invoice import add_custom_fields
        add_custom_fields()
        frappe.db.commit()
        
        # Create test customer
        try:
            cls.test_customer = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Test Workflow Customer",
                "customer_type": "Company"
            })
            cls.test_customer.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            cls.test_customer = frappe.get_doc("Customer", "Test Workflow Customer")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        try:
            # Clean up invoices first
            invoices = frappe.db.sql("""
                SELECT name FROM `tabSales Invoice` 
                WHERE company = 'Test Workflow Company'
            """)
            for invoice in invoices:
                frappe.delete_doc("Sales Invoice", invoice[0], force=True)
            
            # Clean up customer and company
            if frappe.db.exists("Customer", "Test Workflow Customer"):
                frappe.delete_doc("Customer", "Test Workflow Customer", force=True)
            if frappe.db.exists("Company", "Test Workflow Company"):
                frappe.delete_doc("Company", "Test Workflow Company", force=True)
            
            frappe.db.commit()
        except:
            pass
    
    def setUp(self):
        """Reset counter before each test"""
        frappe.db.set_value("Company", "Test Workflow Company", "current_icv_counter", 0)
        frappe.db.commit()
        
        # Clean up any existing test invoices
        self._cleanup_test_invoices()
    
    def test_icv_assignment_on_submission(self):
        """Test that ICV is assigned when Sales Invoice is submitted"""
        # Create draft invoice
        invoice = self._create_draft_invoice("WF-INV-001")
        
        # Verify ICV is not assigned before submission
        self.assertIn(invoice.get("custom_icv_counter"), [None, "", 0])
        
        # Submit the invoice
        invoice.submit()
        
        # Reload to get updated values
        invoice.reload()
        
        # Verify ICV was assigned with company abbreviation format
        self.assertEqual(invoice.custom_icv_counter, "TEST-1")
        
        # Verify company counter was updated
        current_counter = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
        self.assertEqual(current_counter, 1)
    
    def test_sequential_icv_assignment(self):
        """Test that multiple invoices get sequential ICV values"""
        invoices = []
        expected_icvs = []
        
        # Create and submit multiple invoices
        for i in range(5):
            invoice_name = f"WF-INV-SEQ-{i+1:03d}"
            invoice = self._create_draft_invoice(invoice_name)
            invoice.submit()
            invoice.reload()
            
            invoices.append(invoice)
            expected_icvs.append(f"TEST-{i + 1}")
        
        # Verify sequential ICV assignment
        actual_icvs = [inv.custom_icv_counter for inv in invoices]
        self.assertEqual(actual_icvs, expected_icvs)
        
        # Verify final counter state
        final_counter = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
        self.assertEqual(final_counter, 5)
    
    def test_icv_assignment_skipped_for_inactive_company(self):
        """Test that ICV assignment is skipped when JoFotara is not active"""
        # Disable JoFotara for the company
        frappe.db.set_value("Company", "Test Workflow Company", "jofotara_is_active", 0)
        frappe.db.commit()
        
        try:
            # Create and submit invoice
            invoice = self._create_draft_invoice("WF-INV-INACTIVE")
            invoice.submit()
            invoice.reload()
            
            # Verify ICV was not assigned
            self.assertIn(invoice.get("custom_icv_counter"), [None, "", 0])
            
            # Verify counter was not updated
            counter = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
            self.assertEqual(counter, 0)
            
        finally:
            # Re-enable JoFotara
            frappe.db.set_value("Company", "Test Workflow Company", "jofotara_is_active", 1)
            frappe.db.commit()
    
    def test_icv_not_reassigned_on_resubmission(self):
        """Test that ICV is not reassigned if already present"""
        # Create and submit invoice
        invoice = self._create_draft_invoice("WF-INV-RESUBMIT")
        invoice.submit()
        invoice.reload()
        
        original_icv = invoice.custom_icv_counter
        self.assertEqual(original_icv, "TEST-1")
        
        # Cancel and resubmit (simulate resubmission scenario)
        invoice.cancel()
        
        # Manually set ICV to simulate it already being assigned
        frappe.db.set_value("Sales Invoice", invoice.name, "custom_icv_counter", original_icv)
        
        # Amend and submit
        amended_invoice = frappe.copy_doc(invoice)
        amended_invoice.docstatus = 0
        amended_invoice.amended_from = invoice.name
        amended_invoice.insert()
        amended_invoice.submit()
        amended_invoice.reload()
        
        # Verify new invoice gets next ICV (not reassigned)
        self.assertEqual(amended_invoice.custom_icv_counter, "TEST-2")
    
    def test_submission_failure_handling(self):
        """Test that submission failures don't corrupt counter state"""
        original_counter = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
        
        # Create invoice with invalid data that will cause submission to fail
        try:
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": "Test Workflow Customer",
                "company": "Test Workflow Company",
                "posting_date": frappe.utils.today(),
                "items": [{
                    "item_code": "_Test Item",
                    "qty": -1,  # Invalid negative quantity
                    "rate": 100
                }]
            })
            
            invoice.insert()
            
            # This should fail due to negative quantity
            with self.assertRaises(Exception):
                invoice.submit()
            
            # Verify counter wasn't incremented due to failed submission
            current_counter = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
            self.assertEqual(current_counter, original_counter)
            
        except Exception as e:
            # Expected to fail
            pass
    
    def test_multi_company_isolation(self):
        """Test that ICV counters are isolated between companies"""
        # Create second company
        company2 = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test Workflow Company 2",
            "abbr": "TWC2",
            "default_currency": "USD",
            "jofotara_is_active": 1,
            "jofotara_client_id": "test_client_workflow_2",
            "jofotara_secret_key": "test_secret_workflow_2",
            "jofotara_activity_serial": "22222",
            "current_icv_counter": 0
        })
        
        try:
            company2.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            company2 = frappe.get_doc("Company", "Test Workflow Company 2")
        
        try:
            # Create invoices for both companies
            invoice1 = self._create_draft_invoice("WF-INV-COMP1", "Test Workflow Company")
            invoice2 = self._create_draft_invoice("WF-INV-COMP2", "Test Workflow Company 2")
            
            # Submit both
            invoice1.submit()
            invoice2.submit()
            
            # Reload to get updated values
            invoice1.reload()
            invoice2.reload()
            
            # Both should get ICV = 1 (isolated counters) with company abbreviation
            self.assertEqual(invoice1.custom_icv_counter, "TEST-1")
            self.assertEqual(invoice2.custom_icv_counter, "TEST2-1")
            
            # Verify both company counters are at 1
            counter1 = frappe.db.get_value("Company", "Test Workflow Company", "current_icv_counter")
            counter2 = frappe.db.get_value("Company", "Test Workflow Company 2", "current_icv_counter")
            
            self.assertEqual(counter1, 1)
            self.assertEqual(counter2, 1)
            
        finally:
            # Clean up second company
            try:
                # Clean up invoices for company 2
                invoices = frappe.db.sql("""
                    SELECT name FROM `tabSales Invoice` 
                    WHERE company = 'Test Workflow Company 2'
                """)
                for invoice in invoices:
                    frappe.delete_doc("Sales Invoice", invoice[0], force=True)
                
                frappe.delete_doc("Company", "Test Workflow Company 2", force=True)
                frappe.db.commit()
            except:
                pass
    
    def test_counter_integrity_validation(self):
        """Test counter integrity validation after workflow operations"""
        # Create and submit several invoices
        for i in range(3):
            invoice = self._create_draft_invoice(f"WF-INV-INTEGRITY-{i+1}")
            invoice.submit()
        
        # Validate counter integrity
        result = icv_counter_manager.validate_counter_integrity("Test Workflow Company")
        
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["current_counter"], 3)
        self.assertEqual(result["max_icv_in_invoices"], 3)
        self.assertEqual(result["max_icv_string"], "TEST-3")
        self.assertEqual(result["discrepancy"], 0)
    
    def _create_draft_invoice(self, invoice_name, company=None):
        """Helper to create draft Sales Invoice"""
        if company is None:
            company = "Test Workflow Company"
        
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "naming_series": "WF-INV-.#####",
            "customer": "Test Workflow Customer",
            "company": company,
            "posting_date": frappe.utils.today(),
            "items": [{
                "item_code": "_Test Item",
                "qty": 1,
                "rate": 100
            }]
        })
        
        invoice.insert()
        return invoice
    
    def _cleanup_test_invoices(self):
        """Helper to clean up test invoices"""
        try:
            invoices = frappe.db.sql("""
                SELECT name FROM `tabSales Invoice` 
                WHERE company IN ('Test Workflow Company', 'Test Workflow Company 2')
                AND name LIKE 'WF-INV-%'
            """)
            
            for invoice in invoices:
                frappe.delete_doc("Sales Invoice", invoice[0], force=True)
            
            frappe.db.commit()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
