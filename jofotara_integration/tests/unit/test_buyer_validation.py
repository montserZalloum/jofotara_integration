"""
Unit Tests for Buyer Information Validation Module

This module contains comprehensive tests for buyer validation logic
including Credit/Cash validation, currency conversion, and ID schemes.
"""

import unittest
from unittest.mock import patch, MagicMock
import frappe
from frappe.test_runner import make_test_records

from jofotara_integration.jofotara_integration.utils.buyer_validation import (
    validate_buyer_requirements,
    validate_customer_id_scheme,
    validate_pre_submission,
    _determine_buyer_name_requirement,
    _convert_currency_to_jod,
    _get_buyer_name_error_message,
    get_validation_checklist
)


class TestBuyerValidation(unittest.TestCase):
    """Test cases for buyer validation functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        # Setup test data
        make_test_records("Company")
        make_test_records("Customer") 
        make_test_records("Territory")
    
    def setUp(self):
        """Set up test data for each test."""
        self.sample_credit_invoice = {
            'name': 'SI-TEST-CREDIT-001',
            'customer': 'Test Customer',
            'customer_name': 'Test Customer Name',
            'is_pos': 0,  # Credit invoice
            'grand_total': 5000.0,
            'currency': 'JOD',
            'company': 'Test Company'
        }
        
        self.sample_cash_invoice_high = {
            'name': 'SI-TEST-CASH-HIGH-001',
            'customer': 'Test Customer',
            'customer_name': 'Test Customer Name',
            'is_pos': 1,  # Cash invoice
            'grand_total': 15000.0,
            'currency': 'JOD',
            'company': 'Test Company'
        }
        
        self.sample_cash_invoice_low = {
            'name': 'SI-TEST-CASH-LOW-001',
            'customer': 'Test Customer',
            'customer_name': 'Test Customer Name',
            'is_pos': 1,  # Cash invoice
            'grand_total': 5000.0,
            'currency': 'JOD',
            'company': 'Test Company'
        }
        
        self.sample_cash_invoice_threshold = {
            'name': 'SI-TEST-CASH-THRESHOLD-001',
            'customer': 'Test Customer',
            'customer_name': 'Test Customer Name',
            'is_pos': 1,  # Cash invoice
            'grand_total': 10000.0,  # Exactly 10,000 JOD
            'currency': 'JOD',
            'company': 'Test Company'
        }
    
    def test_credit_invoice_always_requires_buyer_name(self):
        """Test that Credit invoices always require buyer name regardless of amount."""
        # Test with buyer name present
        result = validate_buyer_requirements(self.sample_credit_invoice)
        self.assertTrue(result['is_valid'])
        self.assertIn('customer_name', result['required_fields'])
        
        # Test with missing buyer name
        invoice_no_name = self.sample_credit_invoice.copy()
        invoice_no_name['customer_name'] = ''
        result = validate_buyer_requirements(invoice_no_name)
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['errors']), 0)
        self.assertIn('Credit invoices require buyer name', result['errors'][0])
    
    def test_cash_invoice_high_value_requires_buyer_name(self):
        """Test that Cash invoices ≥10,000 JOD require buyer name."""
        # Test high-value cash invoice with buyer name
        result = validate_buyer_requirements(self.sample_cash_invoice_high)
        self.assertTrue(result['is_valid'])
        self.assertIn('customer_name', result['required_fields'])
        
        # Test high-value cash invoice without buyer name
        invoice_no_name = self.sample_cash_invoice_high.copy()
        invoice_no_name['customer_name'] = ''
        result = validate_buyer_requirements(invoice_no_name)
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['errors']), 0)
    
    def test_cash_invoice_low_value_no_buyer_required(self):
        """Test that Cash invoices <10,000 JOD don't require buyer name."""
        # Test low-value cash invoice without buyer name
        invoice_no_name = self.sample_cash_invoice_low.copy()
        invoice_no_name['customer_name'] = ''
        result = validate_buyer_requirements(invoice_no_name)
        self.assertTrue(result['is_valid'])
        self.assertNotIn('customer_name', result['required_fields'])
    
    def test_exactly_10000_jod_threshold(self):
        """Test that exactly 10,000 JOD invoices require buyer name (FR17)."""
        # Test exactly 10,000 JOD with buyer name
        result = validate_buyer_requirements(self.sample_cash_invoice_threshold)
        self.assertTrue(result['is_valid'])
        self.assertIn('customer_name', result['required_fields'])
        
        # Test exactly 10,000 JOD without buyer name
        invoice_no_name = self.sample_cash_invoice_threshold.copy()
        invoice_no_name['customer_name'] = ''
        result = validate_buyer_requirements(invoice_no_name)
        self.assertFalse(result['is_valid'])
    
    def test_buyer_name_minimum_length_validation(self):
        """Test buyer name minimum length requirement."""
        # Test with 1 character (should fail)
        invoice_short_name = self.sample_credit_invoice.copy()
        invoice_short_name['customer_name'] = 'A'
        result = validate_buyer_requirements(invoice_short_name)
        self.assertFalse(result['is_valid'])
        self.assertIn('at least 2 characters', result['errors'][0])
        
        # Test with 2 characters (should pass)
        invoice_valid_name = self.sample_credit_invoice.copy()
        invoice_valid_name['customer_name'] = 'AB'
        result = validate_buyer_requirements(invoice_valid_name)
        self.assertTrue(result['is_valid'])
    
    @patch('jofotara_integration.jofotara_integration.utils.buyer_validation.frappe.db.get_value')
    def test_currency_conversion_usd_to_jod(self, mock_get_value):
        """Test currency conversion from USD to JOD."""
        # Mock exchange rate
        mock_get_value.return_value = 0.71  # 1 USD = 0.71 JOD
        
        # Test USD invoice that converts to above threshold
        usd_invoice = self.sample_cash_invoice_low.copy()
        usd_invoice['currency'] = 'USD'
        usd_invoice['grand_total'] = 15000.0  # 15000 USD = 10650 JOD (above threshold)
        
        result = validate_buyer_requirements(usd_invoice)
        self.assertIn('customer_name', result['required_fields'])
    
    @patch('jofotara_integration.jofotara_integration.utils.buyer_validation.frappe.db.get_value')
    def test_currency_conversion_fallback_rates(self, mock_get_value):
        """Test currency conversion with fallback rates when no exact rate found."""
        # Mock no exchange rate found
        mock_get_value.return_value = None
        
        # Test EUR conversion with fallback rate
        eur_invoice = self.sample_cash_invoice_low.copy()
        eur_invoice['currency'] = 'EUR'
        eur_invoice['grand_total'] = 14000.0  # Should use fallback rate
        
        jod_amount = _convert_currency_to_jod(14000.0, 'EUR')
        self.assertEqual(jod_amount, 14000.0 * 0.76)  # Fallback EUR rate
    
    @patch('frappe.get_doc')
    def test_customer_id_scheme_detection_company(self, mock_get_doc):
        """Test customer ID scheme detection for companies."""
        # Mock company customer with tax ID
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Company',
            'tax_id': '123456789',
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        test_invoice = self.sample_credit_invoice.copy()
        result = validate_customer_id_scheme(test_invoice)
        
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['recommended_scheme'], 'TIN')
        self.assertEqual(result['customer_info']['customer_type'], 'Company')
    
    @patch('frappe.get_doc')
    def test_customer_id_scheme_detection_jordanian_individual(self, mock_get_doc):
        """Test customer ID scheme detection for Jordanian individuals."""
        # Mock Jordanian individual customer
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': '1234567890',
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        test_invoice = self.sample_credit_invoice.copy()
        result = validate_customer_id_scheme(test_invoice)
        
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['recommended_scheme'], 'NAT')  # NIN mapped to NAT
        self.assertEqual(result['customer_info']['territory'], 'Jordan')
    
    @patch('frappe.get_doc')
    def test_customer_id_scheme_detection_non_jordanian_individual(self, mock_get_doc):
        """Test customer ID scheme detection for non-Jordanian individuals."""
        # Mock non-Jordanian individual customer
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Individual',
            'tax_id': 'PASS123456',
            'territory': 'United States'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        test_invoice = self.sample_credit_invoice.copy()
        result = validate_customer_id_scheme(test_invoice)
        
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['recommended_scheme'], 'NAT')  # PN mapped to NAT
        self.assertEqual(result['customer_info']['territory'], 'United States')
    
    @patch('frappe.get_doc')
    def test_company_without_tax_id_validation_error(self, mock_get_doc):
        """Test validation error for company customers without tax ID."""
        # Mock company customer without tax ID
        mock_customer = MagicMock()
        mock_customer.get.side_effect = lambda field, default=None: {
            'customer_type': 'Company',
            'tax_id': '',
            'territory': 'Jordan'
        }.get(field, default)
        mock_get_doc.return_value = mock_customer
        
        test_invoice = self.sample_credit_invoice.copy()
        result = validate_customer_id_scheme(test_invoice)
        
        self.assertFalse(result['is_valid'])
        self.assertIn('must have a valid Tax ID', result['errors'][0])
    
    def test_buyer_name_requirement_determination(self):
        """Test the buyer name requirement determination logic."""
        # Credit invoice
        self.assertTrue(_determine_buyer_name_requirement(self.sample_credit_invoice))
        
        # High-value cash invoice
        self.assertTrue(_determine_buyer_name_requirement(self.sample_cash_invoice_high))
        
        # Low-value cash invoice
        self.assertFalse(_determine_buyer_name_requirement(self.sample_cash_invoice_low))
        
        # Threshold cash invoice (exactly 10,000)
        self.assertTrue(_determine_buyer_name_requirement(self.sample_cash_invoice_threshold))
    
    def test_error_message_generation(self):
        """Test error message generation for different invoice types."""
        # Credit invoice error message
        credit_msg = _get_buyer_name_error_message(0, 5000.0, 'JOD')
        self.assertIn('Credit invoices require buyer name', credit_msg)
        
        # Cash invoice error message
        cash_msg = _get_buyer_name_error_message(1, 15000.0, 'JOD')
        self.assertIn('Cash invoices of JOD 15,000.00', cash_msg)
        self.assertIn('require buyer name', cash_msg)
    
    def test_validation_checklist_generation(self):
        """Test validation checklist generation."""
        checklist = get_validation_checklist(self.sample_credit_invoice)
        
        self.assertIsInstance(checklist, list)
        self.assertGreater(len(checklist), 0)
        
        # Check for expected checklist items
        checklist_checks = [item['check'] for item in checklist]
        self.assertIn('Buyer Name Requirement', checklist_checks)
        self.assertIn('Customer ID Scheme', checklist_checks)
        self.assertIn('Invoice Classification', checklist_checks)
    
    @patch('frappe.get_doc')
    def test_pre_submission_validation_success(self, mock_get_doc):
        """Test complete pre-submission validation for valid invoice."""
        # Mock Sales Invoice document
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = self.sample_credit_invoice
        mock_get_doc.return_value = mock_invoice
        
        result = validate_pre_submission('SI-TEST-CREDIT-001')
        
        self.assertTrue(result['is_valid'])
        self.assertEqual(result['invoice_name'], 'SI-TEST-CREDIT-001')
        self.assertIn('buyer_validation', result)
        self.assertIn('id_scheme_validation', result)
        self.assertIn('checklist', result)
    
    @patch('frappe.get_doc')
    def test_pre_submission_validation_failure(self, mock_get_doc):
        """Test pre-submission validation failure for invalid invoice."""
        # Mock Sales Invoice document with missing buyer name
        invalid_invoice = self.sample_credit_invoice.copy()
        invalid_invoice['customer_name'] = ''
        
        mock_invoice = MagicMock()
        mock_invoice.as_dict.return_value = invalid_invoice
        mock_get_doc.return_value = mock_invoice
        
        result = validate_pre_submission('SI-TEST-CREDIT-INVALID-001')
        
        self.assertFalse(result['is_valid'])
        self.assertGreater(len(result['errors']), 0)
    
    def test_multi_currency_threshold_warnings(self):
        """Test warnings for multi-currency high-value invoices."""
        # USD invoice above 10,000
        usd_invoice = self.sample_cash_invoice_low.copy()
        usd_invoice['currency'] = 'USD'
        usd_invoice['grand_total'] = 12000.0
        
        result = validate_buyer_requirements(usd_invoice)
        self.assertGreater(len(result['warnings']), 0)
        self.assertIn('may require additional documentation', result['warnings'][0])
    
    def test_edge_case_empty_customer_name(self):
        """Test edge case with empty customer name (just spaces)."""
        invoice_empty_name = self.sample_credit_invoice.copy()
        invoice_empty_name['customer_name'] = '   '  # Just spaces
        
        result = validate_buyer_requirements(invoice_empty_name)
        self.assertFalse(result['is_valid'])
        self.assertIn('Credit invoices require buyer name', result['errors'][0])
    
    def test_edge_case_none_values(self):
        """Test edge cases with None values."""
        invoice_none_values = {
            'name': 'SI-TEST-NONE-001',
            'customer': None,
            'customer_name': None,
            'is_pos': None,
            'grand_total': None,
            'currency': None,
            'company': None
        }
        
        # Should not crash and should use defaults
        result = validate_buyer_requirements(invoice_none_values)
        self.assertIsInstance(result, dict)
        self.assertIn('is_valid', result)
        
    def test_currency_conversion_error_handling(self):
        """Test currency conversion error handling."""
        with patch('jofotara_integration.jofotara_integration.utils.buyer_validation.frappe.db.get_value', side_effect=Exception('DB Error')):
            # Should not crash and should use fallback (conservative approach)
            jod_amount = _convert_currency_to_jod(10000.0, 'USD')
            self.assertEqual(jod_amount, 10000.0)  # 1:1 fallback for safety


if __name__ == '__main__':
    unittest.main()
