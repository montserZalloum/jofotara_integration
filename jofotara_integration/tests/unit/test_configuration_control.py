import unittest
import frappe
from frappe.test_runner import make_test_records
from unittest.mock import patch, MagicMock

from jofotara_integration.api.background_jobs import (
    should_auto_submit_invoice,
    _validate_company_configuration,
    enqueue_automatic_submission
)
from jofotara_integration.api.company_config import get_company_configuration_status


class TestConfigurationControl(unittest.TestCase):
    """Test Company-Level JoFotara Configuration Controls (Story 2.2)"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        make_test_records("Company")
        # Ensure custom fields are installed
        from jofotara_integration.custom.company import add_custom_fields
        add_custom_fields()
        
    def setUp(self):
        """Set up each test"""
        # Create test company with known configuration
        self.test_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test JoFotara Company",
            "abbr": "TJC",
            "default_currency": "SAR"
        })
        self.test_company.insert()
        
        # Create inactive test company
        self.inactive_company = frappe.get_doc({
            "doctype": "Company", 
            "company_name": "Inactive JoFotara Company",
            "abbr": "IJC",
            "default_currency": "SAR"
        })
        self.inactive_company.insert()
    
    def tearDown(self):
        """Clean up after each test"""
        frappe.delete_doc("Company", self.test_company.name, force=True)
        frappe.delete_doc("Company", self.inactive_company.name, force=True)
    
    def test_inactive_company_validation(self):
        """Test AC: 3 - Inactive companies skip all e-invoicing processing"""
        # Test with jofotara_is_active = False
        self.test_company.jofotara_is_active = 0
        self.test_company.save()
        
        with self.assertRaises(Exception) as context:
            _validate_company_configuration(self.test_company)
        
        self.assertIn("disabled", str(context.exception).lower())
        
    def test_auto_submit_disabled_company(self):
        """Test AC: 4 - Companies with disabled automatic submission require manual trigger"""
        # Set up company with active but no auto-submit
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_auto_submit = 0
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "123456789"
        self.test_company.save()
        
        # Should not auto-submit
        result = should_auto_submit_invoice(self.test_company.name)
        self.assertFalse(result)
        
    def test_auto_submit_enabled_company(self):
        """Test AC: 4 - Automatic submission for enabled companies"""
        # Set up company with active and auto-submit enabled
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_auto_submit = 1
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "123456789"
        self.test_company.save()
        
        # Should auto-submit
        result = should_auto_submit_invoice(self.test_company.name)
        self.assertTrue(result)
        
    @patch('jofotara_integration.api.background_jobs.enqueue_invoice_submission')
    def test_automatic_submission_enqueue(self, mock_enqueue):
        """Test automatic submission enqueueing logic"""
        # Set up company for auto-submit
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_auto_submit = 1
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "123456789"
        self.test_company.save()
        
        mock_job = MagicMock()
        mock_enqueue.return_value = mock_job
        
        # Test automatic enqueue
        result = enqueue_automatic_submission("TEST-INV-001", self.test_company.name)
        
        self.assertIsNotNone(result)
        mock_enqueue.assert_called_once_with("TEST-INV-001", self.test_company.name)
        
    def test_missing_credentials_validation(self):
        """Test validation with missing credentials"""
        # Set active but missing credentials
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_client_id = ""  # Missing
        self.test_company.save()
        
        with self.assertRaises(Exception) as context:
            _validate_company_configuration(self.test_company)
        
        self.assertIn("missing", str(context.exception).lower())
        
    def test_configuration_status_api(self):
        """Test configuration status API response"""
        # Set up complete configuration
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_auto_submit = 1
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "123456789"
        self.test_company.save()
        
        # Test API response
        with patch('frappe.has_permission', return_value=True):
            status = get_company_configuration_status(self.test_company.name)
        
        self.assertEqual(status["company"], self.test_company.name)
        self.assertTrue(status["is_active"])
        self.assertTrue(status["auto_submit"])
        self.assertTrue(status["has_complete_credentials"])
        
    def test_immediate_configuration_effect(self):
        """Test AC: 5 - Configuration changes take effect immediately"""
        # Start with inactive company
        self.test_company.jofotara_is_active = 0
        self.test_company.save()
        
        # Verify inactive
        result = should_auto_submit_invoice(self.test_company.name)
        self.assertFalse(result)
        
        # Change to active with auto-submit
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_auto_submit = 1
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "123456789"
        self.test_company.save()
        
        # Should immediately reflect the change
        result = should_auto_submit_invoice(self.test_company.name)
        self.assertTrue(result)
        
    def test_invalid_activity_serial_format(self):
        """Test validation of Activity Serial Number format"""
        # Set up with invalid activity serial (within length limit but invalid format)
        self.test_company.jofotara_is_active = 1
        self.test_company.jofotara_client_id = "test_client"
        self.test_company.jofotara_secret_key = "test_secret"
        self.test_company.jofotara_activity_serial = "12abc34"  # Contains letters, within 15 chars
        self.test_company.save()
        
        with self.assertRaises(Exception) as context:
            _validate_company_configuration(self.test_company)
        
        self.assertIn("digits", str(context.exception).lower())


if __name__ == '__main__':
    unittest.main()
