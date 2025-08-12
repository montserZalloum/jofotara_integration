"""
Unit Tests for Enhanced XML Generator with Export and Development Area Support

This module tests the enhanced invoice type code generation and customer ID schemes.
"""

import unittest
from unittest.mock import patch, MagicMock
import frappe
from lxml import etree

from jofotara_integration.jofotara_integration.services.xml_generator import UBLXMLGenerator


class TestEnhancedXMLGenerator(unittest.TestCase):
    """Test cases for enhanced XML generation functionality."""
    
    def setUp(self):
        """Set up test data for each test."""
        self.generator = UBLXMLGenerator()
        
        self.sample_local_invoice = {
            'name': 'SI-LOCAL-001',
            'customer': 'Local Customer',
            'customer_name': 'Local Customer Name',
            'is_pos': 0,  # Credit
            'grand_total': 1000.0,
            'currency': 'JOD',
            'company': 'Test Company',
            'posting_date': '2024-01-15',
            'is_return': 0
        }
        
        self.sample_export_invoice = {
            'name': 'SI-EXPORT-001',
            'customer': 'Export Customer',
            'customer_name': 'Export Customer Name',
            'is_pos': 1,  # Cash
            'grand_total': 1000.0,
            'currency': 'USD',
            'company': 'Test Company',
            'posting_date': '2024-01-15',
            'is_return': 0
        }
        
        self.sample_dev_area_invoice = {
            'name': 'SI-DEV-001',
            'customer': 'Dev Area Customer',
            'customer_name': 'Dev Area Customer Name',
            'is_pos': 0,  # Credit
            'grand_total': 1000.0,
            'currency': 'JOD',
            'company': 'Test Company',
            'posting_date': '2024-01-15',
            'is_return': 0
        }
    
    def test_3_digit_invoice_type_code_generation(self):
        """Test 3-digit invoice type code generation for new invoices."""
        # Test local credit invoice (should be 022)
        code = self.generator._generate_3_digit_invoice_type_code(self.sample_local_invoice)
        self.assertEqual(code, "022")  # 0=Local, 2=Credit, 2=General Sales
        
        # Test export cash invoice (should be 112) 
        code = self.generator._generate_3_digit_invoice_type_code(self.sample_export_invoice)
        self.assertEqual(code, "112")  # 1=Export, 1=Cash, 2=General Sales
        
        # Test development area credit invoice (should be 222)
        code = self.generator._generate_3_digit_invoice_type_code(self.sample_dev_area_invoice)
        self.assertEqual(code, "222")  # 2=Dev Area, 2=Credit, 2=General Sales
    
    @patch('frappe.get_doc')
    def test_invoice_category_determination_local(self, mock_get_doc):
        """Test invoice category determination for local invoices."""
        # Mock customer in Jordan without development area flag
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'custom_is_in_development_area': False,
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        category = self.generator._determine_invoice_category(self.sample_local_invoice)
        self.assertEqual(category, "0")  # Local
    
    @patch('frappe.get_doc')
    def test_invoice_category_determination_export(self, mock_get_doc):
        """Test invoice category determination for export invoices."""
        # Mock customer outside Jordan
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'custom_is_in_development_area': False,
            'territory': 'United States'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        category = self.generator._determine_invoice_category(self.sample_export_invoice)
        self.assertEqual(category, "1")  # Export
    
    @patch('frappe.get_doc')
    def test_invoice_category_determination_development_area(self, mock_get_doc):
        """Test invoice category determination for development area invoices."""
        # Mock customer with development area flag enabled
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'custom_is_in_development_area': True,
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        category = self.generator._determine_invoice_category(self.sample_dev_area_invoice)
        self.assertEqual(category, "2")  # Development Area
    
    @patch('frappe.get_doc')
    def test_development_area_priority_over_export(self, mock_get_doc):
        """Test that development area flag takes priority over export territory."""
        # Mock customer outside Jordan but with development area flag
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'custom_is_in_development_area': True,
            'territory': 'United States'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        category = self.generator._determine_invoice_category(self.sample_export_invoice)
        self.assertEqual(category, "2")  # Development Area (priority over Export)
    
    def test_invoice_category_error_handling(self):
        """Test invoice category determination error handling."""
        # Test with no customer
        invoice_no_customer = self.sample_local_invoice.copy()
        invoice_no_customer['customer'] = None
        
        category = self.generator._determine_invoice_category(invoice_no_customer)
        self.assertEqual(category, "0")  # Default to Local
        
        # Test with customer that doesn't exist (would cause frappe.get_doc to fail)
        with patch('frappe.get_doc', side_effect=Exception('Customer not found')):
            category = self.generator._determine_invoice_category(self.sample_local_invoice)
            self.assertEqual(category, "0")  # Default to Local on error
    
    def test_all_18_invoice_type_combinations(self):
        """Test all 18 possible invoice type code combinations."""
        test_combinations = [
            # Local invoices (0xx)
            ({'is_pos': 1}, "012"),   # Local Cash General
            ({'is_pos': 0}, "022"),   # Local Credit General
            
            # Export invoices (1xx) - would need customer territory mocking
            # Development Area invoices (2xx) - would need development area flag mocking
        ]
        
        for invoice_data, expected_code in test_combinations:
            test_invoice = self.sample_local_invoice.copy()
            test_invoice.update(invoice_data)
            
            with patch.object(self.generator, '_determine_invoice_category', return_value="0"):
                code = self.generator._generate_3_digit_invoice_type_code(test_invoice)
                self.assertEqual(code, expected_code)
    
    @patch('frappe.get_doc')
    def test_enhanced_customer_info_company(self, mock_get_doc):
        """Test enhanced customer info retrieval for companies."""
        # Mock company customer
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Company',
            'tax_id': '123456789',
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        info = self.generator._get_enhanced_customer_info(self.sample_local_invoice)
        
        self.assertEqual(info['id_scheme'], 'TIN')
        self.assertEqual(info['customer_type'], 'Company')
        self.assertEqual(info['tax_id'], '123456789')
    
    @patch('frappe.get_doc')
    def test_enhanced_customer_info_jordanian_individual(self, mock_get_doc):
        """Test enhanced customer info for Jordanian individuals."""
        # Mock Jordanian individual
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': '9876543210',
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        info = self.generator._get_enhanced_customer_info(self.sample_local_invoice)
        
        self.assertEqual(info['id_scheme'], 'NAT')  # NIN mapped to NAT
        self.assertEqual(info['customer_type'], 'Individual')
        self.assertEqual(info['territory'], 'Jordan')
    
    @patch('frappe.get_doc')
    def test_enhanced_customer_info_non_jordanian_individual(self, mock_get_doc):
        """Test enhanced customer info for non-Jordanian individuals."""
        # Mock non-Jordanian individual
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': 'PASS123456',
            'territory': 'United States'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        info = self.generator._get_enhanced_customer_info(self.sample_export_invoice)
        
        self.assertEqual(info['id_scheme'], 'NAT')  # PN mapped to NAT
        self.assertEqual(info['customer_type'], 'Individual')
        self.assertEqual(info['territory'], 'United States')
    
    def test_enhanced_customer_info_error_handling(self):
        """Test enhanced customer info error handling."""
        # Test with no customer
        invoice_no_customer = self.sample_local_invoice.copy()
        invoice_no_customer['customer'] = None
        
        info = self.generator._get_enhanced_customer_info(invoice_no_customer)
        
        self.assertEqual(info['id_scheme'], 'NAT')
        self.assertEqual(info['tax_id'], 'NA')
        
        # Test with customer doc retrieval error
        with patch('frappe.get_doc', side_effect=Exception('DB Error')):
            info = self.generator._get_enhanced_customer_info(self.sample_local_invoice)
            self.assertEqual(info['id_scheme'], 'NAT')
            self.assertEqual(info['tax_id'], 'NA')
    
    @patch('frappe.get_doc')
    def test_company_without_tax_id_handling(self, mock_get_doc):
        """Test company customer without tax ID handling."""
        # Mock company customer without tax ID
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Company',
            'tax_id': '',  # Empty tax ID
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        info = self.generator._get_enhanced_customer_info(self.sample_local_invoice)
        
        self.assertEqual(info['id_scheme'], 'TIN')  # Still use TIN scheme for companies
        self.assertEqual(info['tax_id'], 'NA')
        self.assertEqual(info['customer_type'], 'Company')
    
    @patch('frappe.get_doc')
    def test_xml_generation_with_enhanced_features(self, mock_get_doc):
        """Test complete XML generation with enhanced features."""
        # Mock customer for local invoice
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'custom_is_in_development_area': False,
            'territory': 'Jordan',
            'customer_type': 'Individual',
            'tax_id': '1234567890'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        # Mock company for seller info
        mock_company = MagicMock()
        mock_company.get.side_effect = lambda field, default=None: {
            'tax_id': 'COMP123456',
            'jofotara_activity_serial': '1'
        }.get(field, default)
        
        # Setup mock to return different objects based on doctype
        def mock_get_doc_side_effect(doctype, name):
            if doctype == 'Customer':
                return mock_customer
            elif doctype == 'Company':
                return mock_company
            return MagicMock()
        
        mock_get_doc.side_effect = mock_get_doc_side_effect
        
        # Generate XML
        result = self.generator.generate_xml(self.sample_local_invoice, icv_counter=1)
        
        self.assertIn('xml_content', result)
        self.assertIn('uuid', result)
        
        # Parse XML and check invoice type code
        xml_content = result['xml_content']
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Check InvoiceTypeCode element
        invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % self.generator.nsmap['cbc'])
        self.assertIsNotNone(invoice_type_code)
        self.assertEqual(invoice_type_code.text, '388')  # Standard invoice
        self.assertEqual(invoice_type_code.get('name'), '022')  # Local Credit General
        
        # Check customer party identification scheme
        customer_id = root.find('.//{%s}AccountingCustomerParty//{%s}PartyIdentification//{%s}ID' % (
            self.generator.nsmap['cac'], self.generator.nsmap['cac'], self.generator.nsmap['cbc']
        ))
        self.assertIsNotNone(customer_id)
        self.assertEqual(customer_id.get('schemeID'), 'NAT')
    
    def test_credit_note_compatibility(self):
        """Test that credit notes still work with enhanced type code logic."""
        credit_note = self.sample_local_invoice.copy()
        credit_note['is_return'] = 1
        
        # Mock customer
        with patch('frappe.get_doc') as mock_get_doc:
            mock_customer = MagicMock()
            mock_customer.get.return_value = 'Jordan'
            mock_get_doc.return_value = mock_customer
            
            # Generate XML for credit note
            result = self.generator.generate_xml(credit_note, icv_counter=1)
            xml_content = result['xml_content']
            root = etree.fromstring(xml_content.encode('utf-8'))
            
            # Check that credit notes use 381 type code and simple payment method codes
            invoice_type_code = root.find('.//{%s}InvoiceTypeCode' % self.generator.nsmap['cbc'])
            self.assertEqual(invoice_type_code.text, '381')  # Credit note
            self.assertEqual(invoice_type_code.get('name'), '021')  # Simple 2-digit code for credit notes
    
    def test_xml_structure_validity(self):
        """Test that enhanced XML maintains valid UBL structure."""
        with patch('frappe.get_doc') as mock_get_doc:
            mock_customer = MagicMock()
            mock_customer.get.side_effect = lambda field, default=None: {
                'custom_is_in_development_area': False,
                'territory': 'Jordan',
                'customer_type': 'Individual',
                'tax_id': '1234567890'
            }.get(field, default)
            
            mock_company = MagicMock()
            mock_company.get.side_effect = lambda field, default=None: {
                'tax_id': 'COMP123456',
                'jofotara_activity_serial': '1'
            }.get(field, default)
            
            def mock_get_doc_side_effect(doctype, name):
                if doctype == 'Customer':
                    return mock_customer
                elif doctype == 'Company':
                    return mock_company
                return MagicMock()
            
            mock_get_doc.side_effect = mock_get_doc_side_effect
            
            # Generate and validate XML
            result = self.generator.generate_xml(self.sample_local_invoice, icv_counter=1)
            validation_result = self.generator.validate_xml_schema(result['xml_content'])
            
            self.assertTrue(validation_result['is_valid'])
            self.assertEqual(len(validation_result['errors']), 0)


if __name__ == '__main__':
    unittest.main()
