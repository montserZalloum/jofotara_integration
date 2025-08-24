import frappe
import unittest
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
from jofotara_integration.jofotara_integration.services.validation_service import ValidationService, is_special_tax_template


class TestValidationService(FrappeTestCase):
    """Test cases for the ValidationService class."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()
        self.validation_service = ValidationService()
        
        # Create test company with unique name and abbreviation
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.test_company = frappe.get_doc({
            'doctype': 'Company',
            'company_name': f'Test Company {unique_id}',
            'abbr': f'TC{unique_id}',
            'country': 'Jordan',
            'default_currency': 'JOD',
            'jofotara_is_active': 1,
            'is_jordan_sales_tax_registered': 0
        })
        self.test_company.insert()
        
        # Create test item tax template names (we'll mock the actual templates)
        self.test_tax_template_name = f'Test Special Tax Template {unique_id}'
        self.test_general_tax_template_name = f'Test General Tax Template {unique_id}'
        
        # Create test sales invoice
        self.test_invoice = {
            'company': self.test_company.name,
            'items': [
                {
                    'item_code': 'TEST-ITEM-001',
                    'item_name': 'Test Item 1',
                    'item_tax_template': self.test_tax_template_name,
                    'qty': 1,
                    'rate': 0.1
                }
            ]
        }
    
    def tearDown(self):
        """Clean up test data."""
        # Delete test documents
        if frappe.db.exists('Company', self.test_company.name):
            self.test_company.delete()
        super().tearDown()
    
    @patch('frappe.get_doc')
    def test_validate_company_item_compliance_unregistered_with_special_items(self, mock_get_doc):
        """Test Scenario 1: Unregistered company + special tax item → Validation error"""
        # Mock the tax template lookup
        mock_tax_template = MagicMock()
        mock_tax_template.is_jofotara_special_tax = 1
        mock_get_doc.return_value = mock_tax_template
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        self.assertFalse(result['success'])
        self.assertIn('Compliance Violation', result['error_message'])
        self.assertIn('not registered for Jordanian sales tax', result['error_message'])
        self.assertEqual(len(result['special_items']), 1)
        self.assertEqual(result['special_items'][0]['item_name'], 'Test Item 1')
    
    @patch('frappe.get_doc')
    def test_validate_company_item_compliance_registered_with_special_items(self, mock_get_doc):
        """Test Scenario 2: Registered company + special tax item → No error"""
        # Mock the tax template lookup
        mock_tax_template = MagicMock()
        mock_tax_template.is_jofotara_special_tax = 1
        mock_get_doc.return_value = mock_tax_template
        
        # Update company to be registered
        self.test_company.is_jordan_sales_tax_registered = 1
        self.test_company.save()
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        self.assertTrue(result['success'])
        self.assertIn('Company is registered, special tax items allowed', result['message'])
    
    @patch('frappe.get_doc')
    def test_validate_company_item_compliance_unregistered_with_general_items(self, mock_get_doc):
        """Test Scenario 3: Unregistered company + general tax item → No error"""
        # Mock the tax template lookup
        mock_tax_template = MagicMock()
        mock_tax_template.is_jofotara_special_tax = 0
        mock_get_doc.return_value = mock_tax_template
        
        # Update invoice to use general tax template
        self.test_invoice['items'][0]['item_tax_template'] = self.test_general_tax_template_name
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        self.assertTrue(result['success'])
        self.assertIn('Validation passed - no special tax items found', result['message'])
    
    def test_validate_company_item_compliance_jofotara_inactive(self):
        """Test Scenario 4: Company with jofotara_is_active = unchecked → No validation"""
        # Update company to have JoFotara inactive
        self.test_company.jofotara_is_active = 0
        self.test_company.save()
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        self.assertTrue(result['success'])
        self.assertIn('JoFotara integration not active for this company', result['message'])
    
    @patch('frappe.get_doc')
    def test_validate_company_item_compliance_mixed_items(self, mock_get_doc):
        """Test Scenario 5: Mixed invoice items (some special, some general) → Validation error"""
        # Mock the tax template lookup - first item is special, second is general
        def mock_get_doc_side_effect(doctype, name):
            mock_template = MagicMock()
            if name == self.test_tax_template_name:
                mock_template.is_jofotara_special_tax = 1
            else:
                mock_template.is_jofotara_special_tax = 0
            return mock_template
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Add a general item to the invoice
        self.test_invoice['items'].append({
            'item_code': 'TEST-ITEM-002',
            'item_name': 'Test Item 2',
            'item_tax_template': self.test_general_tax_template_name,
            'qty': 1,
            'rate': 0.5
        })
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        self.assertFalse(result['success'])
        self.assertIn('Compliance Violation', result['error_message'])
        self.assertEqual(len(result['special_items']), 1)  # Only special items are flagged
    
    def test_validate_company_item_compliance_no_company(self):
        """Test validation when no company is specified"""
        invoice_no_company = {'items': self.test_invoice['items']}
        
        result = self.validation_service.validate_company_item_compliance(invoice_no_company)
        
        self.assertTrue(result['success'])
        self.assertIn('No company specified, skipping validation', result['message'])
    
    def test_validate_company_item_compliance_no_items(self):
        """Test validation when invoice has no items"""
        invoice_no_items = {'company': self.test_company.name, 'items': []}
        
        result = self.validation_service.validate_company_item_compliance(invoice_no_items)
        
        self.assertTrue(result['success'])
        self.assertIn('Validation passed - no special tax items found', result['message'])
    
    def test_validate_company_item_compliance_invalid_tax_template(self):
        """Test validation with invalid tax template"""
        self.test_invoice['items'][0]['item_tax_template'] = 'INVALID-TEMPLATE'
        
        result = self.validation_service.validate_company_item_compliance(self.test_invoice)
        
        # Should handle gracefully and not find special items
        self.assertTrue(result['success'])
        self.assertIn('Validation passed - no special tax items found', result['message'])
    
    def test_get_special_tax_items(self):
        """Test _get_special_tax_items method"""
        special_items = self.validation_service._get_special_tax_items(self.test_invoice)
        
        self.assertEqual(len(special_items), 1)
        self.assertEqual(special_items[0]['item_code'], 'TEST-ITEM-001')
        self.assertEqual(special_items[0]['item_tax_template'], self.test_tax_template.name)
    
    def test_create_validation_error_message_single_item(self):
        """Test error message creation for single item"""
        special_items = [{'item_name': 'Test Item', 'item_code': 'TEST-001'}]
        
        error_message = self.validation_service._create_validation_error_message(special_items)
        
        self.assertIn("item 'Test Item'", error_message)
        self.assertIn('Remove the special tax items', error_message)
        self.assertIn('Register your company', error_message)
    
    def test_create_validation_error_message_multiple_items(self):
        """Test error message creation for multiple items"""
        special_items = [
            {'item_name': 'Test Item 1', 'item_code': 'TEST-001'},
            {'item_name': 'Test Item 2', 'item_code': 'TEST-002'},
            {'item_name': 'Test Item 3', 'item_code': 'TEST-003'}
        ]
        
        error_message = self.validation_service._create_validation_error_message(special_items)
        
        self.assertIn('items: Test Item 1, Test Item 2, Test Item 3', error_message)
    
    def test_create_validation_error_message_many_items(self):
        """Test error message creation for many items (truncated)"""
        special_items = [
            {'item_name': f'Test Item {i}', 'item_code': f'TEST-{i:03d}'}
            for i in range(1, 6)
        ]
        
        error_message = self.validation_service._create_validation_error_message(special_items)
        
        self.assertIn('items including: Test Item 1, Test Item 2, Test Item 3 and 2 more', error_message)
    
    def test_validate_unregistered_company_special_items_success(self):
        """Test validate_unregistered_company_special_items when validation passes"""
        # Use general tax template
        self.test_invoice['items'][0]['item_tax_template'] = self.test_general_tax_template_name
        
        # Should not raise an exception
        try:
            self.validation_service.validate_unregistered_company_special_items(
                MagicMock(as_dict=lambda: self.test_invoice)
            )
        except Exception as e:
            self.fail(f"Validation should pass but raised exception: {e}")
    
    def test_validate_unregistered_company_special_items_failure(self):
        """Test validate_unregistered_company_special_items when validation fails"""
        # Use special tax template
        self.test_invoice['items'][0]['item_tax_template'] = self.test_tax_template_name
        
        mock_doc = MagicMock(as_dict=lambda: self.test_invoice)
        
        with self.assertRaises(frappe.ValidationError):
            self.validation_service.validate_unregistered_company_special_items(mock_doc)


class TestSpecialTaxTemplateAPI(FrappeTestCase):
    """Test cases for the is_special_tax_template API function."""
    
    def setUp(self):
        """Set up test data."""
        super().setUp()
        
        # Create test company with unique name and abbreviation
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.test_company = frappe.get_doc({
            'doctype': 'Company',
            'company_name': f'Test Company API {unique_id}',
            'abbr': f'TCA{unique_id}',
            'country': 'Jordan',
            'default_currency': 'JOD'
        })
        self.test_company.insert()
        
        # Create test tax templates
        self.special_template = frappe.get_doc({
            'doctype': 'Item Tax Template',
            'company': self.test_company.name,
            'title': 'API Special Tax Template',
            'tax_category': 'Special Category',
            'is_jofotara_special_tax': 1,
            'taxes': [
                {
                    'tax_type': 'Sales',
                    'tax_rate': 16.0
                }
            ]
        })
        self.special_template.insert()
        
        self.general_template = frappe.get_doc({
            'doctype': 'Item Tax Template',
            'company': self.test_company.name,
            'title': 'API General Tax Template',
            'tax_category': 'General Category',
            'is_jofotara_special_tax': 0,
            'taxes': [
                {
                    'tax_type': 'Sales',
                    'tax_rate': 16.0
                }
            ]
        })
        self.general_template.insert()
    
    def tearDown(self):
        """Clean up test data."""
        if frappe.db.exists('Item Tax Template', self.special_template.name):
            self.special_template.delete()
        if frappe.db.exists('Item Tax Template', self.general_template.name):
            self.general_template.delete()
        if frappe.db.exists('Company', self.test_company.name):
            self.test_company.delete()
        super().tearDown()
    
    def test_is_special_tax_template_special(self):
        """Test API for special tax template"""
        result = is_special_tax_template(self.special_template.name)
        
        self.assertTrue(result['is_special'])
    
    def test_is_special_tax_template_general(self):
        """Test API for general tax template"""
        result = is_special_tax_template(self.general_template.name)
        
        self.assertFalse(result['is_special'])
    
    def test_is_special_tax_template_none(self):
        """Test API with None tax template"""
        result = is_special_tax_template(None)
        
        self.assertFalse(result['is_special'])
    
    def test_is_special_tax_template_empty(self):
        """Test API with empty tax template"""
        result = is_special_tax_template("")
        
        self.assertFalse(result['is_special'])
    
    def test_is_special_tax_template_invalid(self):
        """Test API with invalid tax template"""
        result = is_special_tax_template("INVALID-TEMPLATE")
        
        self.assertFalse(result['is_special'])


if __name__ == '__main__':
    unittest.main()
