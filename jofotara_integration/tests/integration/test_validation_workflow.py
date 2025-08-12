"""
Integration Tests for Complete Validation Workflow

This module tests the end-to-end validation workflow including
buyer validation, XML generation, and submission process.
"""

import unittest
from unittest.mock import patch, MagicMock
import frappe
from frappe.test_runner import make_test_records

from jofotara_integration.jofotara_integration.utils.buyer_validation import validate_pre_submission
from jofotara_integration.jofotara_integration.services.xml_generator import UBLXMLGenerator
from jofotara_integration.api.background_jobs import process_invoice_submission


class TestValidationWorkflow(unittest.TestCase):
    """Integration tests for complete validation workflow."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        make_test_records("Company")
        make_test_records("Customer")
        make_test_records("Currency")
        make_test_records("Territory")
    
    def setUp(self):
        """Set up test data for each test."""
        self.test_company = "Test Company"
        self.test_customer = "Test Customer"
        
        # Sample invoice data for different scenarios
        self.valid_credit_invoice_data = {
            'name': 'SI-VALID-CREDIT-001',
            'customer': self.test_customer,
            'customer_name': 'Valid Customer Name',
            'is_pos': 0,  # Credit
            'grand_total': 5000.0,
            'currency': 'JOD',
            'company': self.test_company,
            'posting_date': '2024-01-15',
            'is_return': 0,
            'items': [
                {
                    'item_code': 'TEST-ITEM-001',
                    'item_name': 'Test Item',
                    'qty': 1,
                    'rate': 5000.0,
                    'amount': 5000.0,
                    'uom': 'Nos'
                }
            ],
            'net_total': 5000.0,
            'total_taxes_and_charges': 0.0,
            'discount_amount': 0.0
        }
        
        self.invalid_credit_invoice_data = {
            'name': 'SI-INVALID-CREDIT-001',
            'customer': self.test_customer,
            'customer_name': '',  # Missing buyer name
            'is_pos': 0,  # Credit
            'grand_total': 5000.0,
            'currency': 'JOD',
            'company': self.test_company,
            'posting_date': '2024-01-15',
            'is_return': 0,
            'items': [
                {
                    'item_code': 'TEST-ITEM-001',
                    'item_name': 'Test Item',
                    'qty': 1,
                    'rate': 5000.0,
                    'amount': 5000.0,
                    'uom': 'Nos'
                }
            ],
            'net_total': 5000.0,
            'total_taxes_and_charges': 0.0,
            'discount_amount': 0.0
        }
        
        self.high_value_cash_invoice_data = {
            'name': 'SI-HIGH-CASH-001',
            'customer': self.test_customer,
            'customer_name': 'High Value Customer',
            'is_pos': 1,  # Cash
            'grand_total': 15000.0,
            'currency': 'JOD',
            'company': self.test_company,
            'posting_date': '2024-01-15',
            'is_return': 0,
            'items': [
                {
                    'item_code': 'TEST-ITEM-001',
                    'item_name': 'High Value Item',
                    'qty': 1,
                    'rate': 15000.0,
                    'amount': 15000.0,
                    'uom': 'Nos'
                }
            ],
            'net_total': 15000.0,
            'total_taxes_and_charges': 0.0,
            'discount_amount': 0.0
        }
        
        self.export_invoice_data = {
            'name': 'SI-EXPORT-001',
            'customer': 'Export Customer',
            'customer_name': 'Export Customer Name',
            'is_pos': 1,  # Cash
            'grand_total': 8000.0,
            'currency': 'USD',
            'company': self.test_company,
            'posting_date': '2024-01-15',
            'is_return': 0,
            'items': [
                {
                    'item_code': 'TEST-ITEM-001',
                    'item_name': 'Export Item',
                    'qty': 1,
                    'rate': 8000.0,
                    'amount': 8000.0,
                    'uom': 'Nos'
                }
            ],
            'net_total': 8000.0,
            'total_taxes_and_charges': 0.0,
            'discount_amount': 0.0
        }
    
    @patch('frappe.get_doc')
    def test_end_to_end_valid_credit_invoice_workflow(self, mock_get_doc):
        """Test complete workflow for valid credit invoice."""
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = self.valid_credit_invoice_data
        
        # Mock Customer document (Jordanian individual)
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': '1234567890',
            'territory': 'Jordan',
            'custom_is_in_development_area': False
        }.get(field, default)
        
        # Mock Company document
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'tax_id': 'COMP123456',
            'jofotara_activity_serial': '1',
            'jofotara_is_active': True,
            'jofotara_client_id': 'test_client',
            'jofotara_secret_key': 'test_secret'
        }.get(field, default)
        mock_company.get_password.return_value = 'test_secret'
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Customer':
                return mock_customer
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Step 1: Pre-submission validation
        validation_result = validate_pre_submission('SI-VALID-CREDIT-001')
        
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        self.assertIn('buyer_validation', validation_result)
        self.assertIn('id_scheme_validation', validation_result)
        
        # Step 2: XML Generation
        xml_generator = UBLXMLGenerator()
        xml_result = xml_generator.generate_xml(self.valid_credit_invoice_data, icv_counter=1)
        
        self.assertIn('xml_content', xml_result)
        self.assertIn('uuid', xml_result)
        
        # Validate XML structure
        validation_result = xml_generator.validate_xml_schema(xml_result['xml_content'])
        self.assertTrue(validation_result['is_valid'])
        
        # Step 3: Verify invoice type code in XML
        from lxml import etree
        root = etree.fromstring(xml_result['xml_content'].encode('utf-8'))
        invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % xml_generator.nsmap['cbc'])
        
        self.assertEqual(invoice_type_code.text, '388')  # Standard invoice
        self.assertEqual(invoice_type_code.get('name'), '022')  # Local Credit General
    
    @patch('frappe.get_doc')
    def test_end_to_end_invalid_credit_invoice_workflow(self, mock_get_doc):
        """Test workflow rejection for invalid credit invoice."""
        # Mock Sales Invoice document with missing buyer name
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = self.invalid_credit_invoice_data
        mock_get_doc.return_value = mock_invoice
        
        # Pre-submission validation should fail
        validation_result = validate_pre_submission('SI-INVALID-CREDIT-001')
        
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
        self.assertIn('Credit invoices require buyer name', validation_result['errors'][0])
    
    @patch('frappe.get_doc')
    def test_high_value_cash_invoice_workflow(self, mock_get_doc):
        """Test workflow for high-value cash invoice requiring buyer name."""
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = self.high_value_cash_invoice_data
        
        # Mock Customer document
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': '1234567890',
            'territory': 'Jordan',
            'custom_is_in_development_area': False
        }.get(field, default)
        
        # Mock Company document
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'tax_id': 'COMP123456',
            'jofotara_activity_serial': '1'
        }.get(field, default)
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Customer':
                return mock_customer
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Pre-submission validation should pass (buyer name provided)
        validation_result = validate_pre_submission('SI-HIGH-CASH-001')
        
        self.assertTrue(validation_result['is_valid'])
        self.assertIn('customer_name', validation_result['buyer_validation']['required_fields'])
        
        # XML generation should produce cash invoice code
        xml_generator = UBLXMLGenerator()
        xml_result = xml_generator.generate_xml(self.high_value_cash_invoice_data, icv_counter=1)
        
        from lxml import etree
        root = etree.fromstring(xml_result['xml_content'].encode('utf-8'))
        invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % xml_generator.nsmap['cbc'])
        
        self.assertEqual(invoice_type_code.get('name'), '012')  # Local Cash General
    
    @patch('frappe.get_doc')
    def test_export_invoice_workflow(self, mock_get_doc):
        """Test workflow for export invoice."""
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = self.export_invoice_data
        
        # Mock Export Customer (US territory)
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': 'PASS123456',
            'territory': 'United States',
            'custom_is_in_development_area': False
        }.get(field, default)
        
        # Mock Company document
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'tax_id': 'COMP123456',
            'jofotara_activity_serial': '1'
        }.get(field, default)
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Customer':
                return mock_customer
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Pre-submission validation
        validation_result = validate_pre_submission('SI-EXPORT-001')
        self.assertTrue(validation_result['is_valid'])
        
        # Verify customer ID scheme for non-Jordanian
        id_scheme = validation_result['id_scheme_validation']['recommended_scheme']
        self.assertEqual(id_scheme, 'NAT')  # PN mapped to NAT
        
        # XML generation should produce export invoice code
        xml_generator = UBLXMLGenerator()
        xml_result = xml_generator.generate_xml(self.export_invoice_data, icv_counter=1)
        
        from lxml import etree
        root = etree.fromstring(xml_result['xml_content'].encode('utf-8'))
        invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % xml_generator.nsmap['cbc'])
        
        self.assertEqual(invoice_type_code.get('name'), '112')  # Export Cash General
    
    @patch('frappe.get_doc')
    def test_development_area_invoice_workflow(self, mock_get_doc):
        """Test workflow for development area invoice."""
        # Create development area invoice data
        dev_area_invoice = self.valid_credit_invoice_data.copy()
        dev_area_invoice['name'] = 'SI-DEV-AREA-001'
        
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = dev_area_invoice
        
        # Mock Development Area Customer
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': '1234567890',
            'territory': 'Jordan',
            'custom_is_in_development_area': True  # Development area flag
        }.get(field, default)
        
        # Mock Company document
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'tax_id': 'COMP123456',
            'jofotara_activity_serial': '1'
        }.get(field, default)
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Customer':
                return mock_customer
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # XML generation should produce development area invoice code
        xml_generator = UBLXMLGenerator()
        xml_result = xml_generator.generate_xml(dev_area_invoice, icv_counter=1)
        
        from lxml import etree
        root = etree.fromstring(xml_result['xml_content'].encode('utf-8'))
        invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % xml_generator.nsmap['cbc'])
        
        self.assertEqual(invoice_type_code.get('name'), '222')  # Development Area Credit General
    
    @patch('frappe.get_doc')
    @patch('frappe.db.get_value')
    def test_multi_currency_validation_workflow(self, mock_db_get_value, mock_get_doc):
        """Test workflow for multi-currency invoice with threshold validation."""
        # Mock exchange rate
        mock_db_get_value.return_value = 0.71  # 1 USD = 0.71 JOD
        
        # USD invoice that exceeds JOD threshold after conversion
        usd_invoice = self.export_invoice_data.copy()
        usd_invoice['grand_total'] = 15000.0  # 15000 USD = 10650 JOD (above threshold)
        usd_invoice['is_pos'] = 1  # Cash invoice
        
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = usd_invoice
        
        # Mock Customer document
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': 'PASS123456',
            'territory': 'United States',
            'custom_is_in_development_area': False
        }.get(field, default)
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Customer':
                return mock_customer
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Pre-submission validation should require buyer name due to high converted value
        validation_result = validate_pre_submission('SI-EXPORT-USD-HIGH-001')
        
        self.assertTrue(validation_result['is_valid'])
        self.assertIn('customer_name', validation_result['buyer_validation']['required_fields'])
        self.assertGreater(len(validation_result['warnings']), 0)
    
    @patch('jofotara_integration.jofotara_integration.utils.buyer_validation.validate_pre_submission')
    @patch('jofotara_integration.jofotara_integration.services.xml_generator.UBLXMLGenerator')
    @patch('jofotara_integration.jofotara_integration.services.jofotara_client.JoFotaraClient')
    @patch('frappe.get_doc')
    def test_background_job_validation_integration(self, mock_get_doc, mock_client_class, mock_generator_class, mock_validate_pre_submission):
        """Test that background job properly integrates buyer validation."""
        # Mock validation failure
        mock_validate_pre_submission.return_value = {
            'is_valid': False,
            'errors': ['Credit invoices require buyer name information'],
            'warnings': []
        }
        
        # Mock invoice document
        mock_invoice = MagicMock()
        mock_invoice.get.return_value = 0  # Not a return
        mock_get_doc.return_value = mock_invoice
        
        # Mock company document
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'jofotara_is_active': True,
            'jofotara_client_id': 'test_client',
            'jofotara_secret_key': 'test_secret',
            'jofotara_activity_serial': '1'
        }.get(field, default)
        mock_company.get_password.return_value = 'test_secret'
        
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Sales Invoice':
                return mock_invoice
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Background job should fail due to validation error
        with self.assertRaises(Exception) as context:
            process_invoice_submission('SI-INVALID-001', 'Test Company')
        
        self.assertIn('Buyer validation failed', str(context.exception))
        mock_validate_pre_submission.assert_called_once_with('SI-INVALID-001')
    
    def test_validation_checklist_completeness(self):
        """Test that validation checklist covers all required scenarios."""
        from jofotara_integration.jofotara_integration.utils.buyer_validation import get_validation_checklist
        
        # Test different invoice types
        test_scenarios = [
            ('Credit Invoice', self.valid_credit_invoice_data),
            ('High-Value Cash', self.high_value_cash_invoice_data),
            ('Export Invoice', self.export_invoice_data)
        ]
        
        for scenario_name, invoice_data in test_scenarios:
            with self.subTest(scenario=scenario_name):
                checklist = get_validation_checklist(invoice_data)
                
                # Verify checklist structure
                self.assertIsInstance(checklist, list)
                self.assertGreater(len(checklist), 0)
                
                # Verify required checklist items
                checklist_items = [item['check'] for item in checklist]
                self.assertIn('Buyer Name Requirement', checklist_items)
                self.assertIn('Customer ID Scheme', checklist_items)
                self.assertIn('Invoice Classification', checklist_items)
                
                # Verify each item has required fields
                for item in checklist:
                    self.assertIn('check', item)
                    self.assertIn('status', item)
                    self.assertIn('required', item)
                    self.assertIn('message', item)
                    self.assertIn('details', item)
    
    def test_error_message_accuracy(self):
        """Test that error messages accurately reflect validation failures."""
        from jofotara_integration.jofotara_integration.utils.buyer_validation import (
            _get_buyer_name_error_message
        )
        
        # Test error message for credit invoice
        credit_msg = _get_buyer_name_error_message(0, 5000.0, 'JOD')
        self.assertIn('Credit invoices require buyer name', credit_msg)
        
        # Test error message for high-value cash invoice
        cash_msg = _get_buyer_name_error_message(1, 15000.0, 'JOD')
        self.assertIn('Cash invoices of JOD 15,000.00', cash_msg)
        self.assertIn('require buyer name', cash_msg)
        
        # Test error message for multi-currency invoice
        usd_msg = _get_buyer_name_error_message(1, 12000.0, 'USD')
        self.assertIn('Cash invoices of USD 12,000.00', usd_msg)
        self.assertIn('require buyer name', usd_msg)


if __name__ == '__main__':
    unittest.main()
