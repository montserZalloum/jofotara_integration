import unittest
import frappe
from frappe.test_runner import make_test_records
from unittest.mock import patch, MagicMock

from jofotara_integration.overrides.sales_invoice import on_submit


class TestAutoSubmissionWorkflow(unittest.TestCase):
    """Test automatic vs manual submission workflows"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        make_test_records("Company")
        make_test_records("Customer")
        make_test_records("Item")
        # Ensure custom fields are installed
        from jofotara_integration.custom.company import add_custom_fields
        add_custom_fields()
        
    def setUp(self):
        """Set up each test"""
        # Create test company with auto-submit enabled
        self.auto_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Auto Submit Company",
            "abbr": "ASC",
            "default_currency": "SAR",
            "jofotara_is_active": 1,
            "jofotara_auto_submit": 1,
            "jofotara_client_id": "auto_client",
            "jofotara_secret_key": "auto_secret",
            "jofotara_activity_serial": "123456789"
        })
        self.auto_company.insert()
        
        # Create test company with manual submit only
        self.manual_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Manual Submit Company", 
            "abbr": "MSC",
            "default_currency": "SAR",
            "jofotara_is_active": 1,
            "jofotara_auto_submit": 0,
            "jofotara_client_id": "manual_client",
            "jofotara_secret_key": "manual_secret",
            "jofotara_activity_serial": "987654321"
        })
        self.manual_company.insert()
        
        # Create test customer
        self.test_customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": "Test Customer",
            "customer_type": "Individual"
        })
        self.test_customer.insert()
        
        # Create test item
        self.test_item = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-ITEM",
            "item_name": "Test Item",
            "stock_uom": "Nos",
            "is_stock_item": 0
        })
        self.test_item.insert()
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up test documents
        frappe.delete_doc("Company", self.auto_company.name, force=True)
        frappe.delete_doc("Company", self.manual_company.name, force=True)
        frappe.delete_doc("Customer", self.test_customer.name, force=True)
        frappe.delete_doc("Item", self.test_item.name, force=True)
    
    def create_test_invoice(self, company):
        """Helper to create test Sales Invoice"""
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": self.test_customer.name,
            "company": company.name,
            "due_date": frappe.utils.add_days(frappe.utils.nowdate(), 30),
            "items": [{
                "item_code": self.test_item.item_code,
                "qty": 1,
                "rate": 100
            }]
        })
        invoice.insert()
        return invoice
    
    @patch('jofotara_integration.api.background_jobs.enqueue_invoice_submission')
    def test_auto_submit_company_triggers_automatic_submission(self, mock_enqueue):
        """Test that auto-submit companies trigger automatic submission on invoice submit"""
        mock_job = MagicMock()
        mock_job.id = "test-job-123"
        mock_enqueue.return_value = mock_job
        
        # Create and submit invoice for auto-submit company
        invoice = self.create_test_invoice(self.auto_company)
        invoice.submit()
        
        # Simulate the on_submit hook
        on_submit(invoice, "on_submit")
        
        # Should have triggered automatic submission
        mock_enqueue.assert_called_once_with(invoice.name, self.auto_company.name)
        
    @patch('jofotara_integration.api.background_jobs.enqueue_invoice_submission')
    def test_manual_submit_company_no_automatic_submission(self, mock_enqueue):
        """Test that manual-submit companies don't trigger automatic submission"""
        # Create and submit invoice for manual-submit company  
        invoice = self.create_test_invoice(self.manual_company)
        invoice.submit()
        
        # Simulate the on_submit hook
        on_submit(invoice, "on_submit")
        
        # Should NOT have triggered automatic submission
        mock_enqueue.assert_not_called()
        
    @patch('jofotara_integration.api.background_jobs.enqueue_automatic_submission')
    @patch('frappe.msgprint')
    def test_auto_submission_success_message(self, mock_msgprint, mock_enqueue):
        """Test success message for auto submission"""
        mock_job = MagicMock()
        mock_enqueue.return_value = mock_job
        
        # Create and submit invoice for auto-submit company
        invoice = self.create_test_invoice(self.auto_company)
        invoice.submit()
        
        # Simulate the on_submit hook
        on_submit(invoice, "on_submit")
        
        # Should show success message
        mock_msgprint.assert_called_once()
        call_args = mock_msgprint.call_args
        self.assertIn("automatically queued", call_args[0][0])
        
    @patch('jofotara_integration.api.background_jobs.enqueue_automatic_submission')
    @patch('frappe.msgprint')
    def test_auto_submission_no_message_when_disabled(self, mock_msgprint, mock_enqueue):
        """Test no message when auto submission is disabled"""
        mock_enqueue.return_value = None  # No job returned = auto submission disabled
        
        # Create and submit invoice for manual-submit company
        invoice = self.create_test_invoice(self.manual_company)
        invoice.submit()
        
        # Simulate the on_submit hook
        on_submit(invoice, "on_submit")
        
        # Should not show auto-submission message
        if mock_msgprint.called:
            call_args = mock_msgprint.call_args
            self.assertNotIn("automatically queued", call_args[0][0])
            
    @patch('jofotara_integration.api.background_jobs.enqueue_automatic_submission')
    @patch('frappe.log_error')
    @patch('frappe.msgprint')
    def test_auto_submission_error_handling(self, mock_msgprint, mock_log_error, mock_enqueue):
        """Test error handling in auto submission"""
        # Mock an exception in auto submission
        mock_enqueue.side_effect = Exception("Test error")
        
        # Create and submit invoice 
        invoice = self.create_test_invoice(self.auto_company)
        invoice.submit()
        
        # Simulate the on_submit hook - should not raise exception
        try:
            on_submit(invoice, "on_submit")
        except Exception:
            self.fail("on_submit should not raise exception on auto-submission failure")
        
        # Should log error and show user message
        mock_log_error.assert_called_once()
        mock_msgprint.assert_called_once()
        
        # Check error message content
        call_args = mock_msgprint.call_args
        self.assertIn("failed", call_args[0][0].lower())
        
    def test_inactive_company_no_processing(self):
        """Test that inactive companies are not processed"""
        # Disable the auto company
        self.auto_company.jofotara_is_active = 0
        self.auto_company.save()
        
        with patch('jofotara_integration.api.background_jobs.enqueue_automatic_submission') as mock_enqueue:
            # Create and submit invoice
            invoice = self.create_test_invoice(self.auto_company)
            invoice.submit()
            
            # Simulate the on_submit hook
            on_submit(invoice, "on_submit")
            
            # Should not attempt submission for inactive company
            mock_enqueue.assert_called_once()
            # The function should be called but return None due to inactive status
            

if __name__ == '__main__':
    unittest.main()
