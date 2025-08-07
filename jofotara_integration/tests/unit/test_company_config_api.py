import unittest
import frappe
from frappe.test_runner import make_test_records
from unittest.mock import patch

from jofotara_integration.api.company_config import (
    get_company_configuration_status,
    get_all_companies_configuration,
    test_company_connection
)


class TestCompanyConfigAPI(unittest.TestCase):
    """Test Company Configuration API endpoints"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        make_test_records("Company")
        # Ensure custom fields are installed
        from jofotara_integration.custom.company import add_custom_fields
        add_custom_fields()
        
    def setUp(self):
        """Set up each test"""
        # Create test companies with different configurations
        self.active_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Active Company",
            "abbr": "AC",
            "default_currency": "SAR",
            "jofotara_is_active": 1,
            "jofotara_auto_submit": 1,
            "jofotara_client_id": "active_client",
            "jofotara_secret_key": "active_secret",
            "jofotara_activity_serial": "123456789"
        })
        self.active_company.insert()
        
        self.inactive_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Inactive Company",
            "abbr": "IC",
            "default_currency": "SAR",
            "jofotara_is_active": 0
        })
        self.inactive_company.insert()
        
        self.incomplete_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Incomplete Company",
            "abbr": "INC",
            "default_currency": "SAR",
            "jofotara_is_active": 1,
            "jofotara_auto_submit": 0,
            "jofotara_client_id": "incomplete_client"
            # Missing secret_key and activity_serial
        })
        self.incomplete_company.insert()
    
    def tearDown(self):
        """Clean up after each test"""
        frappe.delete_doc("Company", self.active_company.name, force=True)
        frappe.delete_doc("Company", self.inactive_company.name, force=True)
        frappe.delete_doc("Company", self.incomplete_company.name, force=True)
    
    @patch('frappe.has_permission')
    def test_get_company_configuration_status_active(self, mock_permission):
        """Test configuration status for active company"""
        mock_permission.return_value = True
        
        status = get_company_configuration_status(self.active_company.name)
        
        self.assertEqual(status["company"], self.active_company.name)
        self.assertTrue(status["is_active"])
        self.assertTrue(status["auto_submit"])
        self.assertTrue(status["has_complete_credentials"])
        self.assertEqual(status["status_summary"], "Auto Submit Enabled")
        
    @patch('frappe.has_permission')
    def test_get_company_configuration_status_inactive(self, mock_permission):
        """Test configuration status for inactive company"""
        mock_permission.return_value = True
        
        status = get_company_configuration_status(self.inactive_company.name)
        
        self.assertEqual(status["company"], self.inactive_company.name)
        self.assertFalse(status["is_active"])
        self.assertFalse(status["auto_submit"])
        self.assertTrue(status["has_complete_credentials"])  # No validation when inactive
        self.assertEqual(status["status_summary"], "Integration Disabled")
        
    @patch('frappe.has_permission')
    def test_get_company_configuration_status_incomplete(self, mock_permission):
        """Test configuration status for company with incomplete credentials"""
        mock_permission.return_value = True
        
        status = get_company_configuration_status(self.incomplete_company.name)
        
        self.assertEqual(status["company"], self.incomplete_company.name)
        self.assertTrue(status["is_active"])
        self.assertFalse(status["auto_submit"])
        self.assertFalse(status["has_complete_credentials"])
        self.assertEqual(status["status_summary"], "Missing Credentials")
        
    @patch('frappe.has_permission')
    def test_get_company_configuration_status_permission_denied(self, mock_permission):
        """Test permission denied scenario"""
        mock_permission.return_value = False
        
        with self.assertRaises(frappe.ValidationError):
            get_company_configuration_status(self.active_company.name)
            
    @patch('frappe.has_permission')
    def test_get_company_configuration_status_company_not_found(self, mock_permission):
        """Test company not found scenario"""
        mock_permission.return_value = True
        
        with self.assertRaises(frappe.ValidationError):
            get_company_configuration_status("Nonexistent Company")
            
    @patch('frappe.has_permission')
    def test_get_all_companies_configuration(self, mock_permission):
        """Test getting configuration for all companies"""
        mock_permission.return_value = True
        
        # Mock frappe.get_all to return our test companies
        with patch('frappe.get_all') as mock_get_all:
            mock_get_all.return_value = [
                {
                    "name": self.active_company.name,
                    "company_name": self.active_company.company_name,
                    "jofotara_is_active": 1,
                    "jofotara_auto_submit": 1,
                    "jofotara_client_id": "active_client",
                    "jofotara_secret_key": "active_secret",
                    "jofotara_activity_serial": "123456789"
                },
                {
                    "name": self.inactive_company.name,
                    "company_name": self.inactive_company.company_name,
                    "jofotara_is_active": 0,
                    "jofotara_auto_submit": 0,
                    "jofotara_client_id": None,
                    "jofotara_secret_key": None,
                    "jofotara_activity_serial": None
                }
            ]
            
            configs = get_all_companies_configuration()
            
            self.assertEqual(len(configs), 2)
            
            # Check active company
            active_config = next(c for c in configs if c["company"] == self.active_company.name)
            self.assertTrue(active_config["is_active"])
            self.assertTrue(active_config["has_complete_credentials"])
            self.assertEqual(active_config["status_summary"], "Auto Submit Enabled")
            
            # Check inactive company
            inactive_config = next(c for c in configs if c["company"] == self.inactive_company.name)
            self.assertFalse(inactive_config["is_active"])
            self.assertEqual(inactive_config["status_summary"], "Integration Disabled")
            
    @patch('frappe.has_permission')
    @patch('jofotara_integration.api.background_jobs._validate_company_configuration')
    def test_test_company_connection_success(self, mock_validate, mock_permission):
        """Test successful connection test"""
        mock_permission.return_value = True
        # Mock validation to pass
        mock_validate.return_value = None
        
        result = test_company_connection(self.active_company.name)
        
        self.assertTrue(result["success"])
        self.assertIn("valid", result["message"].lower())
        
    @patch('frappe.has_permission')
    @patch('jofotara_integration.api.background_jobs._validate_company_configuration')
    def test_test_company_connection_failure(self, mock_validate, mock_permission):
        """Test failed connection test"""
        mock_permission.return_value = True
        # Mock validation to fail
        mock_validate.side_effect = Exception("Invalid credentials")
        
        result = test_company_connection(self.active_company.name)
        
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid credentials")
        self.assertIn("failed", result["message"].lower())
        
    @patch('frappe.has_permission')
    def test_test_company_connection_permission_denied(self, mock_permission):
        """Test connection test with insufficient permissions"""
        mock_permission.return_value = False
        
        result = test_company_connection(self.active_company.name)
        
        self.assertFalse(result["success"])
        self.assertIn("permission", result["error"].lower())


if __name__ == '__main__':
    unittest.main()
