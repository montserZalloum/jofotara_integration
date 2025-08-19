"""
UBL 2.1 XML Generator Service for JoFotara Integration

This module provides XML generation functionality for Sales Invoices
according to UBL 2.1 specifications and JoFotara API requirements.
"""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
import frappe
from lxml import etree
from jofotara_integration.jofotara_integration.utils.validation import validate_original_invoice_for_credit_note
from jofotara_integration.jofotara_integration.services.currency_service import get_multi_currency_service


class UBLXMLGenerator:
    """
    UBL 2.1 XML Generator for JoFotara e-invoicing compliance.
    
    Generates XML documents that comply with UBL 2.1 schema and 
    JoFotara technical specifications.
    """
    
    # UBL 2.1 Namespaces for XML generation
    NAMESPACES = {
        None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    }
    
    def __init__(self):
        """Initialize UBL XML Generator with namespace mappings."""
        self.nsmap = self.NAMESPACES
    
    def _convert_amount_for_credit_note(self, amount: float, is_return: bool) -> float:
        """
        Convert negative Credit Note amounts to positive values for UBL XML.
        
        Args:
            amount: Original amount from ERPNext (negative for Credit Notes)
            is_return: Whether this is a Credit Note/return invoice
            
        Returns:
            float: Positive amount for UBL XML or original amount for regular invoices
        """
        if is_return and amount < 0:
            return abs(amount)
        return amount
    
    def generate_xml(self, sales_invoice: Dict[str, Any], icv_counter: int) -> Dict[str, str]:
        """
        Generate UBL 2.1 compliant XML for a Sales Invoice.
        
        Args:
            sales_invoice: Sales Invoice document data
            icv_counter: Invoice Counter Value for sequential numbering
            
        Returns:
            Dict[str, str]: Dictionary containing:
                - xml_content: Generated XML string with proper UBL 2.1 structure
                - uuid: The generated UUID for the invoice
            
        Raises:
            ValueError: If required invoice data is missing
            Exception: If XML generation fails
        """
        try:
            # Generate UUID that will be used in the XML and saved to the invoice
            generated_uuid = str(uuid.uuid4())
            
            # Create root element with namespaces
            root = etree.Element("Invoice", nsmap=self.nsmap)
            
            # Build XML in the EXACT required order as per JoFotara specification
            
            # 1. Main Invoice Information
            self._add_profile_id(root)
            self._add_invoice_id(root, sales_invoice)
            self._add_uuid(root, generated_uuid)
            self._add_issue_date(root, sales_invoice)
            self._add_issue_time(root, sales_invoice)
            self._add_invoice_type_code(root, sales_invoice)
            self._add_note(root, sales_invoice)
            self._add_currency_codes(root, sales_invoice)
            
            # 2. BillingReference for Credit Notes (must come before AdditionalDocumentReference)
            if sales_invoice.get('is_return', 0):
                self._add_billing_reference(root, sales_invoice)
            
            # 3. Additional Document Reference (ICV)
            self._add_icv_document_reference(root, icv_counter)
            
            # 3.1. Additional Document Reference for Original Invoice Total (Credit Notes)
            if sales_invoice.get('is_return', 0):
                self._add_original_invoice_total_reference(root, sales_invoice)
            
            # 4. Accounting Supplier Party (Seller details)
            self._add_accounting_supplier_party(root, sales_invoice)
            
            # 5. Accounting Customer Party (Buyer details)
            self._add_accounting_customer_party(root, sales_invoice)
            
            # 6. Seller Supplier Party (Activity Serial Number)
            self._add_seller_supplier_party(root, sales_invoice)
            
            # 7. PaymentMeans for Credit Notes (if applicable)
            if sales_invoice.get('is_return', 0):
                self._add_payment_means(root, sales_invoice)
            
            # 8. Document Level Allowance/Discount
            self._add_document_level_allowance(root, sales_invoice)
            
            # 9. Tax Total
            self._add_tax_total(root, sales_invoice)
            
            # 10. Legal Monetary Total
            self._add_legal_monetary_total(root, sales_invoice)
            
            # 11. Invoice Lines
            self._add_invoice_lines(root, sales_invoice)
            
            # Validate invoice type compatibility before finalizing XML
            compatibility_result = self.validate_invoice_type_compatibility(sales_invoice)
            if not compatibility_result['is_compatible']:
                error_messages = '; '.join(compatibility_result['errors'])
                frappe.log_error(
                    f"Invoice type compatibility issues for {sales_invoice.get('name')}: {error_messages}",
                    "UBL XML Generator"
                )
                # Log warnings but don't fail XML generation
                if compatibility_result['warnings']:
                    warning_messages = '; '.join(compatibility_result['warnings'])
                    frappe.log_error(
                        f"Invoice type compatibility warnings for {sales_invoice.get('name')}: {warning_messages}",
                        "UBL XML Generator Warnings"
                    )
            
            # Generate XML string with declaration
            xml_str = etree.tostring(
                root, 
                pretty_print=True, 
                xml_declaration=True, 
                encoding='UTF-8'
            ).decode('utf-8')
            
            return {
                'xml_content': xml_str,
                'uuid': generated_uuid,
                'invoice_type_info': self.determine_invoice_type_code(sales_invoice),
                'compatibility_validation': compatibility_result
            }
            
        except ValueError as e:
            # Handle user-friendly validation errors (like unsupported currency)
            error_msg = str(e)
            frappe.log_error(f"Validation error in XML generation: {error_msg}", "XML Generation Validation")
            raise ValueError(error_msg)  # Re-raise as ValueError to be handled by caller
        except Exception as e:
            frappe.log_error(f"XML Generation failed: {str(e)}", "UBL XML Generator")
            raise
    
    def _add_profile_id(self, root: etree.Element) -> None:
        """Add ProfileID element as per JoFotara specification."""
        profile_id = etree.SubElement(root, "{%s}ProfileID" % self.nsmap['cbc'])
        profile_id.text = "reporting:1.0"
    
    def _add_invoice_id(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add Invoice ID element (must be unique per seller)."""
        invoice_id = etree.SubElement(root, "{%s}ID" % self.nsmap['cbc'])
        
        # Use the ICV counter as the main invoice ID for JoFotara compliance
        # This ensures sequential numbering per company as required
        icv_value = sales_invoice.get('custom_icv_counter')
        if icv_value:
            invoice_id.text = str(icv_value)
        else:
            # Fallback to Frappe invoice name if ICV not available
            invoice_id.text = sales_invoice.get('name', '')
    
    def _add_uuid(self, root: etree.Element, generated_uuid: str) -> None:
        """Add UUID element for universal unique identification."""
        uuid_elem = etree.SubElement(root, "{%s}UUID" % self.nsmap['cbc'])
        uuid_elem.text = generated_uuid
    
    def _add_issue_date(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add IssueDate in YYYY-MM-DD format."""
        issue_date = etree.SubElement(root, "{%s}IssueDate" % self.nsmap['cbc'])
        posting_date = sales_invoice.get('posting_date')
        if isinstance(posting_date, str):
            issue_date.text = posting_date
        else:
            issue_date.text = posting_date.strftime('%Y-%m-%d') if posting_date else datetime.now().strftime('%Y-%m-%d')
    
    def _add_invoice_type_code(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add InvoiceTypeCode with proper Credit Note handling per JoFotara specification."""
        type_code_elem = etree.SubElement(root, "{%s}InvoiceTypeCode" % self.nsmap['cbc'])
        
        # Determine if this is a return/credit invoice
        is_return = sales_invoice.get('is_return', 0)
        
        if is_return:
            # Credit Note: InvoiceTypeCode = 381, but name attribute must match original invoice type
            type_code_elem.text = "381"
            payment_method_name = self._get_original_invoice_type_code(sales_invoice)
        else:
            # New invoice - use enhanced 3-digit type code generation
            type_code_elem.text = "388"
            # Get comprehensive invoice type information
            type_info = self.determine_invoice_type_code(sales_invoice)
            payment_method_name = type_info['type_code']
        
        # Add the mandatory 'name' attribute with payment method code
        type_code_elem.set('name', payment_method_name)
    
    def _get_original_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Get the 3-digit type code from the original invoice for Credit Note compatibility.
        
        According to JoFotara specification, Credit Notes must use the same type code
        in the name attribute as the original invoice to maintain type compatibility.
        
        Args:
            sales_invoice: Credit Note sales invoice data
            
        Returns:
            str: 3-digit type code from original invoice (e.g., "022", "011", etc.)
        """
        try:
            return_against = sales_invoice.get('return_against')
            if not return_against:
                frappe.throw("Credit Note must reference an original invoice in return_against field")
            
            # Validate original invoice using existing utility
            validation_result = validate_original_invoice_for_credit_note(return_against)
            if not validation_result.get('is_valid'):
                error_message = validation_result.get('error_message', 'Original invoice validation failed')
                frappe.throw(error_message)
            
            # Get original invoice data
            original_invoice_data = validation_result.get('original_invoice', {})
            
            # Try to get the type code from the original invoice's custom field if available
            original_type_code = original_invoice_data.get('custom_invoice_type_code')
            if original_type_code:
                return original_type_code
            
            # If not available, determine the type code based on original invoice characteristics
            # This ensures backward compatibility with invoices that don't have the type code stored
            original_type_info = self.determine_invoice_type_code(original_invoice_data)
            return original_type_info.get('type_code', '022')  # Fallback to Local Credit General Sales
            
        except Exception as e:
            frappe.log_error(
                f"Error getting original invoice type code for Credit Note: {str(e)}", 
                "UBL XML Generator"
            )
            # Return a safe default that works for most cases
            return "022"  # Local Credit General Sales - most common scenario
    
    def _get_simple_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Get simple invoice type code with Development Area detection.
        
        Returns:
        - "212": Development Area Credit
        - "211": Development Area Cash  
        - "021": Local Credit
        - "011": Local Cash
        """
        try:
            # Check if customer is in Development Area
            customer_name = sales_invoice.get('customer')
            if customer_name:
                customer_doc = frappe.get_doc("Customer", customer_name)
                if customer_doc.get('custom_is_in_development_area'):
                    # Development Area customer - use 2xx codes
                    is_pos = sales_invoice.get('is_pos', 0)
                    return "211" if is_pos else "212"
            
            # Default Local customer - use 0xx codes  
            is_pos = sales_invoice.get('is_pos', 0)
            return "011" if is_pos else "021"
            
        except Exception as e:
            frappe.log_error(f"Error determining simple invoice type: {str(e)}", "UBL XML Generator")
            # Default to Local codes on error
            is_pos = sales_invoice.get('is_pos', 0)
            return "011" if is_pos else "021"
    
    def _generate_3_digit_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Generate 3-digit invoice type code based on invoice characteristics.
        
        Code structure: XYZ
        - X: Invoice Category (0=Local, 1=Export, 2=Development Area)
        - Y: Payment Method (1=Cash, 2=Credit)
        - Z: Payer Type (1=Income, 2=General Sales, 3=Special Sales)
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            str: 3-digit invoice type code (e.g., "011", "121", "223")
        """
        # Determine invoice category (first digit)
        category_digit = self._determine_invoice_category(sales_invoice)
        
        # Determine payment method (second digit)
        is_pos = sales_invoice.get('is_pos', 0)
        payment_digit = "1" if is_pos else "2"  # 1=Cash, 2=Credit
        
        # Determine payer type (third digit) using enhanced logic
        payer_digit = self._determine_payer_type(sales_invoice)
        
        return f"{category_digit}{payment_digit}{payer_digit}"
    
    def _determine_payer_type(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Determine payer type for the third digit of 3-digit invoice type code.
        
        Payer Types:
        - 1: Income invoices (specific business use cases)
        - 2: General Sales invoices (default for most transactions)
        - 3: Special Sales invoices (items with special tax rates or categories)
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            str: Payer type digit ("1", "2", or "3")
        """
        try:
            # Use currency service to determine special sales eligibility
            currency_service = get_multi_currency_service()
            special_sales_result = currency_service.determine_special_sales_eligibility(sales_invoice)
            
            if special_sales_result.get('is_special_sales', False):
                return "3"  # Special Sales
            
            # Check for Income type invoices (business-specific logic)
            if self._is_income_invoice(sales_invoice):
                return "1"  # Income
            
            # Default to General Sales
            return "2"  # General Sales
            
        except Exception as e:
            frappe.log_error(f"Error determining payer type: {str(e)}", "UBL XML Generator")
            return "2"  # Default to General Sales on error
    
    def _is_income_invoice(self, sales_invoice: Dict[str, Any]) -> bool:
        """
        Determine if invoice qualifies as Income type (1st payer digit).
        
        Income invoices are typically:
        - Service-based transactions
        - Professional fees
        - Rental income
        - Custom business rules defined by company
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            bool: True if invoice qualifies as Income type
        """
        try:
            # Check if invoice has income-related items or categories
            items = sales_invoice.get('items', [])
            
            for item in items:
                item_code = item.get('item_code', '')
                item_group = item.get('item_group', '')
                
                # Example business rules for Income classification
                # These can be customized based on specific business requirements
                if any(keyword in str(item_code).lower() for keyword in ['service', 'rental', 'fee', 'consultation']):
                    return True
                
                if any(keyword in str(item_group).lower() for keyword in ['services', 'professional', 'income']):
                    return True
            
            # Check invoice-level indicators
            terms = sales_invoice.get('terms', '')
            if terms and any(keyword in terms.lower() for keyword in ['service agreement', 'rental', 'professional fee']):
                return True
            
            return False
            
        except Exception as e:
            frappe.log_error(f"Error checking income invoice classification: {str(e)}", "UBL XML Generator")
            return False
    
    def determine_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive invoice type code determination for all 18 combinations.
        
        Returns detailed information about the invoice type classification
        including the 3-digit code and breakdown of each digit.
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing:
            - type_code: str - 3-digit invoice type code
            - category: str - Invoice category (Local/Export/Development Area)
            - payment_method: str - Payment method (Cash/Credit)
            - payer_type: str - Payer type (Income/General Sales/Special Sales)
            - category_digit: str - First digit
            - payment_digit: str - Second digit  
            - payer_digit: str - Third digit
            - description: str - Human-readable description
        """
        try:
            # Generate the 3-digit code
            type_code = self._generate_3_digit_invoice_type_code(sales_invoice)
            
            # Break down the code
            category_digit = type_code[0]
            payment_digit = type_code[1]
            payer_digit = type_code[2]
            
            # Map digits to descriptions
            category_map = {'0': 'Local', '1': 'Export', '2': 'Development Area'}
            payment_map = {'1': 'Cash', '2': 'Credit'}
            payer_map = {'1': 'Income', '2': 'General Sales', '3': 'Special Sales'}
            
            category_desc = category_map.get(category_digit, 'Unknown')
            payment_desc = payment_map.get(payment_digit, 'Unknown')
            payer_desc = payer_map.get(payer_digit, 'Unknown')
            
            description = f"{category_desc} {payment_desc} {payer_desc}"
            
            return {
                'type_code': type_code,
                'category': category_desc,
                'payment_method': payment_desc,
                'payer_type': payer_desc,
                'category_digit': category_digit,
                'payment_digit': payment_digit,
                'payer_digit': payer_digit,
                'description': description,
                'is_valid': True,
                'validation_errors': []
            }
            
        except Exception as e:
            frappe.log_error(f"Error determining invoice type code: {str(e)}", "UBL XML Generator")
            return {
                'type_code': '022',  # Default fallback
                'category': 'Local',
                'payment_method': 'Credit',
                'payer_type': 'General Sales',
                'category_digit': '0',
                'payment_digit': '2',
                'payer_digit': '2',
                'description': 'Local Credit General Sales (Default)',
                'is_valid': False,
                'validation_errors': [f"Error in type code determination: {str(e)}"]
            }
    
    def validate_special_sales_requirements(self, sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Special Sales invoice requirements for JoFotara compliance.
        
        Special Sales invoices (3rd digit = 3) must meet specific criteria:
        - Have items with special tax rates or exemptions
        - Proper tax template assignments
        - Valid tax calculations
        - Compliance with unique tax scenarios
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing validation results:
            - is_valid: bool
            - errors: List[str] - Validation errors
            - warnings: List[str] - Validation warnings
            - special_sales_info: Dict - Information about special sales classification
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'special_sales_info': {}
        }
        
        try:
            # Get invoice type information
            type_info = self.determine_invoice_type_code(sales_invoice)
            
            # Only validate if this is a Special Sales invoice
            if type_info.get('payer_digit') != '3':
                validation_result['special_sales_info'] = {
                    'is_special_sales': False,
                    'reason': 'Not classified as Special Sales invoice'
                }
                return validation_result
            
            # Get special sales eligibility details
            currency_service = get_multi_currency_service()
            special_sales_result = currency_service.determine_special_sales_eligibility(sales_invoice)
            
            validation_result['special_sales_info'] = special_sales_result
            
            # Validate that Special Sales classification is justified
            if not special_sales_result.get('is_special_sales', False):
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    "Invoice classified as Special Sales but does not meet Special Sales criteria"
                )
                return validation_result
            
            # Validate special items requirements
            special_items = special_sales_result.get('special_items', [])
            if len(special_items) == 0:
                validation_result['errors'].append(
                    "Special Sales invoice must contain at least one item with special tax treatment"
                )
                validation_result['is_valid'] = False
            
            # Validate tax calculations for special items
            items = sales_invoice.get('items', [])
            total_special_amount = 0
            
            for item in items:
                item_code = item.get('item_code')
                
                # Check if this item is in special_items list
                is_special_item = any(
                    special_item.get('item_code') == item_code 
                    for special_item in special_items
                )
                
                if is_special_item:
                    # Validate special item tax handling
                    tax_rate = item.get('rate', 0)
                    amount = item.get('amount', 0)
                    total_special_amount += amount
                    
                    # Check for proper tax template
                    item_tax_template = item.get('item_tax_template')
                    if not item_tax_template:
                        validation_result['warnings'].append(
                            f"Special item {item_code} should have a tax template assigned"
                        )
                    
                    # Validate zero-rated items have proper justification
                    if tax_rate == 0 and not item_tax_template:
                        validation_result['errors'].append(
                            f"Zero-rated special item {item_code} must have tax template for compliance"
                        )
                        validation_result['is_valid'] = False
            
            # Validate that special items constitute significant portion of invoice
            total_invoice_amount = sales_invoice.get('net_total', 0)
            if total_invoice_amount > 0:
                special_percentage = (total_special_amount / total_invoice_amount) * 100
                if special_percentage < 10:  # Less than 10% special items
                    validation_result['warnings'].append(
                        f"Special Sales classification may not be appropriate - only {special_percentage:.1f}% of invoice contains special items"
                    )
            
            # Validate currency compatibility with Special Sales
            currency = sales_invoice.get('currency', 'JOD')
            currency_service = get_multi_currency_service()
            currency_validation = currency_service.validate_currency_support(currency)
            
            if not currency_validation['is_valid']:
                validation_result['errors'].append(
                    f"Special Sales invoice currency validation failed: {currency_validation['error_message']}"
                )
                validation_result['is_valid'] = False
            
            # Validate customer information for Special Sales
            customer_name = sales_invoice.get('customer')
            if customer_name:
                try:
                    customer_doc = frappe.get_doc("Customer", customer_name)
                    customer_type = customer_doc.get('customer_type')
                    
                    # Special Sales typically require proper customer identification
                    if customer_type == 'Company':
                        tax_id = customer_doc.get('tax_id')
                        if not tax_id or tax_id.strip() in ['', 'NA']:
                            validation_result['warnings'].append(
                                "Special Sales to companies should have valid tax ID for compliance"
                            )
                    
                except Exception as e:
                    validation_result['warnings'].append(
                        f"Could not validate customer information: {str(e)}"
                    )
            
            return validation_result
            
        except Exception as e:
            frappe.log_error(f"Special Sales validation error: {str(e)}", "UBL XML Generator")
            return {
                'is_valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'special_sales_info': {'error': str(e)}
            }
    
    def validate_invoice_type_compatibility(self, sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate compatibility between invoice type, customer, and business rules.
        
        Ensures that the determined invoice type code is appropriate for:
        - Customer territory and type
        - Invoice currency
        - Item classifications
        - Business compliance requirements
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing compatibility validation results
        """
        validation_result = {
            'is_compatible': True,
            'errors': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            # Get comprehensive invoice type information
            type_info = self.determine_invoice_type_code(sales_invoice)
            
            if not type_info.get('is_valid', True):
                validation_result['errors'].extend(type_info.get('validation_errors', []))
                validation_result['is_compatible'] = False
                return validation_result
            
            category = type_info.get('category')
            payer_type = type_info.get('payer_type')
            currency = sales_invoice.get('currency', 'JOD')
            
            # Validate Export invoices
            if category == 'Export':
                customer_name = sales_invoice.get('customer')
                if customer_name:
                    try:
                        customer_doc = frappe.get_doc("Customer", customer_name)
                        territory = customer_doc.get('territory', 'Jordan')
                        
                        if territory == 'Jordan':
                            validation_result['warnings'].append(
                                "Export invoice type assigned to Jordan customer - verify classification"
                            )
                        
                        # Validate currency for export
                        if currency == 'JOD' and territory != 'Jordan':
                            validation_result['recommendations'].append(
                                f"Consider using {territory} local currency or USD for export to {territory}"
                            )
                    except Exception:
                        validation_result['warnings'].append(
                            "Could not validate customer territory for Export invoice"
                        )
            
            # Validate Special Sales compatibility
            if payer_type == 'Special Sales':
                special_validation = self.validate_special_sales_requirements(sales_invoice)
                if not special_validation['is_valid']:
                    validation_result['errors'].extend(special_validation['errors'])
                    validation_result['is_compatible'] = False
                
                validation_result['warnings'].extend(special_validation['warnings'])
            
            # Validate Development Area invoices
            if category == 'Development Area':
                customer_name = sales_invoice.get('customer')
                if customer_name:
                    try:
                        customer_doc = frappe.get_doc("Customer", customer_name)
                        is_dev_area = customer_doc.get('custom_is_in_development_area')
                        
                        if not is_dev_area:
                            validation_result['errors'].append(
                                "Development Area invoice type requires customer to be flagged as in development area"
                            )
                            validation_result['is_compatible'] = False
                    except Exception:
                        validation_result['warnings'].append(
                            "Could not validate development area flag for customer"
                        )
            
            return validation_result
            
        except Exception as e:
            frappe.log_error(f"Invoice type compatibility validation error: {str(e)}", "UBL XML Generator")
            return {
                'is_compatible': False,
                'errors': [f"Compatibility validation error: {str(e)}"],
                'warnings': [],
                'recommendations': []
            }
    
    def _determine_invoice_category(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Determine invoice category for the first digit of 3-digit code.
        
        Categories:
        - 0: Local invoices (default)
        - 1: Export invoices (customer territory != Jordan)
        - 2: Development Area invoices (customer has custom_is_in_development_area=1)
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            str: Category digit ("0", "1", or "2")
        """
        try:
            customer_name = sales_invoice.get('customer')
            if not customer_name:
                return "0"  # Default to Local
            
            # Get customer document to check territory and development area flag
            customer_doc = frappe.get_doc("Customer", customer_name)
            
            # Check for Development Area first (highest priority)
            if customer_doc.get('custom_is_in_development_area'):
                return "2"  # Development Area
            
            # Check for Export based on territory
            customer_territory = customer_doc.get('territory')
            if customer_territory and customer_territory != 'Jordan':
                return "1"  # Export
            
            # Default to Local
            return "0"
            
        except Exception as e:
            frappe.log_error(f"Error determining invoice category: {str(e)}", "UBL XML Generator")
            return "0"  # Default to Local on error
    

    
    def _add_currency_codes(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add DocumentCurrencyCode and TaxCurrencyCode with multi-currency support."""
        invoice_currency = sales_invoice.get('currency', 'JOD')
        
        # Use multi-currency service to get proper currency codes
        currency_service = get_multi_currency_service()
        
        try:
            # Get proper document and tax currencies
            document_currency, tax_currency = currency_service.get_document_and_tax_currencies(invoice_currency)
            
            # Add DocumentCurrencyCode (invoice currency)
            doc_currency = etree.SubElement(root, "{%s}DocumentCurrencyCode" % self.nsmap['cbc'])
            doc_currency.text = document_currency
            
            # Add TaxCurrencyCode (JoFotara requires it to match DocumentCurrencyCode)
            tax_currency_elem = etree.SubElement(root, "{%s}TaxCurrencyCode" % self.nsmap['cbc'])
            tax_currency_elem.text = tax_currency
            
        except ValueError as e:
            # Handle unsupported currency errors gracefully - don't crash XML generation
            error_msg = str(e)
            if "not supported by JoFotara" in error_msg:
                # This is a currency validation error - should have been caught earlier
                # Create a user-friendly error instead of technical XML error
                raise ValueError(f"Invoice currency '{invoice_currency}' is not supported by JoFotara. Please change the invoice currency to one of the supported currencies: JOD, USD, EUR, SAR, AED, OMR, GBP, QAR, KWD, BHD, AUD, CAD, JPY, CHF, TRY, SYP, EGP")
            else:
                # Other currency processing errors
                raise ValueError(f"Currency processing error: {error_msg}")
        except Exception as e:
            # For any other unexpected errors, use fallback
            frappe.log_error(f"Unexpected currency code processing error: {str(e)}", "UBL XML Generator")
            # Fallback to basic currency handling - both currencies must match
            currency_code = invoice_currency or 'JOD'
            
            doc_currency = etree.SubElement(root, "{%s}DocumentCurrencyCode" % self.nsmap['cbc'])
            doc_currency.text = currency_code
            
            tax_currency_elem = etree.SubElement(root, "{%s}TaxCurrencyCode" % self.nsmap['cbc'])
            tax_currency_elem.text = currency_code  # Must match DocumentCurrencyCode
    
    def _add_icv_document_reference(self, root: etree.Element, icv_counter: int) -> None:
        """Add AdditionalDocumentReference container for ICV."""
        doc_ref = etree.SubElement(root, "{%s}AdditionalDocumentReference" % self.nsmap['cac'])
        
        ref_id = etree.SubElement(doc_ref, "{%s}ID" % self.nsmap['cbc'])
        ref_id.text = "ICV"
        
        ref_uuid = etree.SubElement(doc_ref, "{%s}UUID" % self.nsmap['cbc'])
        ref_uuid.text = str(icv_counter)
    
    def _add_billing_reference(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add BillingReference element for Credit Notes with original invoice details."""
        return_against = sales_invoice.get('return_against')
        
        # Validate original invoice using utility function
        validation_result = validate_original_invoice_for_credit_note(return_against)
        
        if not validation_result.get('is_valid'):
            error_message = validation_result.get('error_message', 'Original invoice validation failed')
            frappe.throw(error_message)
        
        try:
            # Extract validated details
            original_uuid = validation_result.get('original_uuid')
            original_invoice_data = validation_result.get('original_invoice', {})
            
            # Create BillingReference element
            billing_ref = etree.SubElement(root, "{%s}BillingReference" % self.nsmap['cac'])
            
            # Add InvoiceDocumentReference with original invoice details
            invoice_doc_ref = etree.SubElement(billing_ref, "{%s}InvoiceDocumentReference" % self.nsmap['cac'])
            
            # Add original invoice ID
            doc_ref_id = etree.SubElement(invoice_doc_ref, "{%s}ID" % self.nsmap['cbc'])
            original_icv = original_invoice_data.get('custom_icv_counter')
            if original_icv:
                doc_ref_id.text = str(original_icv)
            else:
                # Fallback to original invoice name if ICV is missing (should not happen)
                doc_ref_id.text = return_against
            
            # Get original total for use in multiple places
            original_total = original_invoice_data.get('grand_total', 0.0)
            
            # Add original invoice UUID
            doc_ref_uuid = etree.SubElement(invoice_doc_ref, "{%s}UUID" % self.nsmap['cbc'])
            doc_ref_uuid.text = original_uuid
            
            # Add IssueDate from original invoice if available
            original_date = original_invoice_data.get('posting_date')
            if original_date:
                if isinstance(original_date, str):
                    issue_date = etree.SubElement(invoice_doc_ref, "{%s}IssueDate" % self.nsmap['cbc'])
                    issue_date.text = original_date
                else:
                    issue_date = etree.SubElement(invoice_doc_ref, "{%s}IssueDate" % self.nsmap['cbc'])
                    issue_date.text = original_date.strftime('%Y-%m-%d') if original_date else ""
            
            # Add DocumentDescription with original invoice total for JoFotara
            if original_total:
                doc_description = etree.SubElement(invoice_doc_ref, "{%s}DocumentDescription" % self.nsmap['cbc'])
                # Provide only the numeric total to avoid non-numeric characters that break BigDecimal parsing
                doc_description.text = f"{abs(original_total):.2f}"
            
            # Add BillingReferenceLine with original invoice total (as per UBL structure)
            if original_total:
                currency = sales_invoice.get('currency', 'JOD')
                billing_ref_line = etree.SubElement(billing_ref, "{%s}BillingReferenceLine" % self.nsmap['cac'])
                
                # Add line ID
                line_id = etree.SubElement(billing_ref_line, "{%s}ID" % self.nsmap['cbc'])
                line_id.text = "1"
                
                # Add original invoice amount in BillingReferenceLine
                billed_amount = etree.SubElement(billing_ref_line, "{%s}Amount" % self.nsmap['cbc'])
                billed_amount.set('currencyID', currency)
                billed_amount.text = f"{abs(original_total):.2f}"
            
        except Exception as e:
            frappe.log_error(f"Error adding BillingReference for Credit Note: {str(e)}", "UBL XML Generator")
            frappe.throw(f"Failed to process original invoice reference: {str(e)}")
    
    def _add_original_invoice_total_reference(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AdditionalDocumentReference for original invoice total (JoFotara requirement)."""
        try:
            return_against = sales_invoice.get('return_against')
            if not return_against:
                return
            
            # Get original invoice data
            validation_result = validate_original_invoice_for_credit_note(return_against)
            if not validation_result.get('is_valid'):
                return
            
            original_invoice_data = validation_result.get('original_invoice', {})
            original_total = original_invoice_data.get('grand_total', 0.0)
            
            if original_total:
                # Create AdditionalDocumentReference for original invoice total
                doc_ref = etree.SubElement(root, "{%s}AdditionalDocumentReference" % self.nsmap['cac'])
                
                # Set ID as originalInvoiceTotal
                ref_id = etree.SubElement(doc_ref, "{%s}ID" % self.nsmap['cbc'])
                ref_id.text = "originalInvoiceTotal"
                
                # Set the total amount as UUID field (JoFotara specific)
                ref_uuid = etree.SubElement(doc_ref, "{%s}UUID" % self.nsmap['cbc'])
                ref_uuid.text = f"{abs(original_total):.2f}"
                
        except Exception as e:
            frappe.log_error(f"Error adding original invoice total reference: {str(e)}", "UBL XML Generator")
            # Don't throw error - continue with standard XML
            pass
    
    def _add_payment_means(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add PaymentMeans element for Credit Notes with return reason instruction."""
        try:
            # Create PaymentMeans element
            payment_means = etree.SubElement(root, "{%s}PaymentMeans" % self.nsmap['cac'])
            
            # Add PaymentMeansCode for Credit Note/Return
            payment_means_code = etree.SubElement(payment_means, "{%s}PaymentMeansCode" % self.nsmap['cbc'])
            payment_means_code.text = "1"  # Standard code for Credit Note returns
            
            # Add InstructionNote with return reason
            # return_reason = sales_invoice.get('terms', '').strip()
            return_reason = "test test "
            if not return_reason or len(return_reason) < 5:
                frappe.throw("Credit Note must have a return reason in the Terms field (minimum 5 characters)")
            
            instruction_note = etree.SubElement(payment_means, "{%s}InstructionNote" % self.nsmap['cbc'])
            instruction_note.text = return_reason[:500]  # Limit to 500 characters for UBL compliance
            
        except Exception as e:
            frappe.log_error(f"Error adding PaymentMeans for Credit Note: {str(e)}", "UBL XML Generator")
            frappe.throw(f"Failed to add PaymentMeans: {str(e)}")
    
    def _add_issue_time(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add IssueTime element."""
        issue_time = etree.SubElement(root, "{%s}IssueTime" % self.nsmap['cbc'])
        
        if sales_invoice and sales_invoice.get('posting_time'):
            # Use actual posting time if available
            posting_time = sales_invoice.get('posting_time')
            if isinstance(posting_time, str):
                issue_time.text = posting_time
            else:
                # Handle timedelta object (ERPNext stores time as timedelta)
                from datetime import timedelta
                if isinstance(posting_time, timedelta):
                    # Convert timedelta to HH:MM:SS format
                    total_seconds = int(posting_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    issue_time.text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    # For datetime objects
                    issue_time.text = posting_time.strftime('%H:%M:%S')
        else:
            # Fallback to midnight
            issue_time.text = "00:00:00"
    
    def _add_note(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add Note element."""
        note = etree.SubElement(root, "{%s}Note" % self.nsmap['cbc'])
        note.text = sales_invoice.get('terms') or "Sales Invoice"
    
    def _add_accounting_supplier_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AccountingSupplierParty element with seller details."""
        supplier_party = etree.SubElement(root, "{%s}AccountingSupplierParty" % self.nsmap['cac'])
        party = etree.SubElement(supplier_party, "{%s}Party" % self.nsmap['cac'])
        
        # Postal Address
        postal_address = etree.SubElement(party, "{%s}PostalAddress" % self.nsmap['cac'])
        country = etree.SubElement(postal_address, "{%s}Country" % self.nsmap['cac'])
        etree.SubElement(country, "{%s}IdentificationCode" % self.nsmap['cbc']).text = "JO"
        
        # Party Tax Scheme (Company Tax ID)
        party_tax_scheme = etree.SubElement(party, "{%s}PartyTaxScheme" % self.nsmap['cac'])
        
        # Get company tax ID from Company doctype
        company_name = sales_invoice.get('company')
        company_tax_id = "NA"
        try:
            if company_name:
                company_doc = frappe.get_doc("Company", company_name)
                company_tax_id = company_doc.get('tax_id') or "NA"
        except Exception as e:
            frappe.log_error(f"Error getting company tax ID: {str(e)}", "UBL XML Generator")
            
        etree.SubElement(party_tax_scheme, "{%s}CompanyID" % self.nsmap['cbc']).text = str(company_tax_id)
        tax_scheme = etree.SubElement(party_tax_scheme, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
        
        # Party Legal Entity
        party_legal_entity = etree.SubElement(party, "{%s}PartyLegalEntity" % self.nsmap['cac'])
        company_name = sales_invoice.get('company') or "Company Name"
        etree.SubElement(party_legal_entity, "{%s}RegistrationName" % self.nsmap['cbc']).text = str(company_name)
    
    def _add_accounting_customer_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AccountingCustomerParty element with enhanced buyer details and ID scheme detection."""
        customer_party = etree.SubElement(root, "{%s}AccountingCustomerParty" % self.nsmap['cac'])
        party = etree.SubElement(customer_party, "{%s}Party" % self.nsmap['cac'])
        
        # Get enhanced customer information
        customer_info = self._get_enhanced_customer_info(sales_invoice)
        
        # Party Identification with enhanced scheme detection
        party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
        etree.SubElement(
            party_identification, 
            "{%s}ID" % self.nsmap['cbc'], 
            schemeID=customer_info['id_scheme']
        ).text = str(customer_info['tax_id'])
        
        # Postal Address
        postal_address = etree.SubElement(party, "{%s}PostalAddress" % self.nsmap['cac'])
        country = etree.SubElement(postal_address, "{%s}Country" % self.nsmap['cac'])
        etree.SubElement(country, "{%s}IdentificationCode" % self.nsmap['cbc']).text = "JO"
        
        # Party Tax Scheme
        party_tax_scheme = etree.SubElement(party, "{%s}PartyTaxScheme" % self.nsmap['cac'])
        tax_scheme = etree.SubElement(party_tax_scheme, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
        
        # Party Legal Entity
        party_legal_entity = etree.SubElement(party, "{%s}PartyLegalEntity" % self.nsmap['cac'])
        customer_name = sales_invoice.get('customer_name') or sales_invoice.get('customer') or "Customer Name"
        etree.SubElement(party_legal_entity, "{%s}RegistrationName" % self.nsmap['cbc']).text = str(customer_name)
    
    def _get_enhanced_customer_info(self, sales_invoice: Dict[str, Any]) -> Dict[str, str]:
        """
        Get enhanced customer information with proper ID scheme detection.
        
        ID Schemes:
        - TN (Tax Number): For companies with valid tax ID
        - NIN (National ID): For Jordanian individuals  
        - PN (Personal No.): For non-Jordanian individuals
        
        Note: Using 'TIN' and 'NAT' as XML scheme values for compatibility,
        but logic follows TN/NIN/PN business rules.
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing customer info with proper scheme
        """
        default_info = {
            'tax_id': 'NA',
            'id_scheme': 'NAT',
            'customer_type': 'Individual',
            'territory': 'Jordan'
        }
        
        try:
            customer_name = sales_invoice.get('customer')
            if not customer_name:
                return default_info
            
            # Get customer document
            customer_doc = frappe.get_doc("Customer", customer_name)
            customer_type = customer_doc.get('customer_type', 'Individual')
            tax_id = customer_doc.get('tax_id', '').strip()
            territory = customer_doc.get('territory', 'Jordan')
            
            # Determine appropriate ID scheme
            if customer_type == 'Company':
                # Companies should use TN (Tax Number) scheme
                if tax_id and tax_id != 'NA':
                    return {
                        'tax_id': tax_id,
                        'id_scheme': 'TIN',  # TN mapped to TIN for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                else:
                    # Company without tax ID - validation should catch this
                    frappe.log_error(
                        f"Company customer {customer_name} missing tax ID",
                        "Customer ID Scheme Detection"
                    )
                    return {
                        'tax_id': 'NA',
                        'id_scheme': 'TIN',  # Still use TIN scheme for companies
                        'customer_type': customer_type,
                        'territory': territory
                    }
            else:
                # Individual customers
                if territory == 'Jordan':
                    # Jordanian individuals use NIN (National ID) scheme
                    return {
                        'tax_id': tax_id or 'NA',
                        'id_scheme': 'NAT',  # NIN mapped to NAT for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                else:
                    # Non-Jordanian individuals use PN (Personal No.) scheme
                    return {
                        'tax_id': tax_id or 'NA',
                        'id_scheme': 'NAT',  # PN mapped to NAT for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                    
        except Exception as e:
            frappe.log_error(f"Error getting enhanced customer info: {str(e)}", "UBL XML Generator")
            return default_info
    
    def _add_seller_supplier_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add SellerSupplierParty element with Activity Serial Number."""
        # Get Company document to fetch activity serial number
        company_name = sales_invoice.get('company')
        if company_name:
            try:
                company_doc = frappe.get_doc("Company", company_name)
                activity_serial = company_doc.get("jofotara_activity_serial")
                
                if not activity_serial:
                    raise ValueError(f"Activity Serial Number not configured for company {company_name}")
                
                seller_party = etree.SubElement(root, "{%s}SellerSupplierParty" % self.nsmap['cac'])
                party = etree.SubElement(seller_party, "{%s}Party" % self.nsmap['cac'])
                party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
                etree.SubElement(party_identification, "{%s}ID" % self.nsmap['cbc']).text = str(activity_serial)
            except Exception as e:
                frappe.log_error(f"Error getting activity serial number: {str(e)}", "UBL XML Generator")
                # Add placeholder if company data not available
                seller_party = etree.SubElement(root, "{%s}SellerSupplierParty" % self.nsmap['cac'])
                party = etree.SubElement(seller_party, "{%s}Party" % self.nsmap['cac'])
                party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
                etree.SubElement(party_identification, "{%s}ID" % self.nsmap['cbc']).text = "1"
    
    def _add_document_level_allowance(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add document-level AllowanceCharge element."""
        allowance_charge = etree.SubElement(root, "{%s}AllowanceCharge" % self.nsmap['cac'])
        etree.SubElement(allowance_charge, "{%s}ChargeIndicator" % self.nsmap['cbc']).text = "false"
        etree.SubElement(allowance_charge, "{%s}AllowanceChargeReason" % self.nsmap['cbc']).text = "discount"
        
        discount_amount = sales_invoice.get('discount_amount') or 0.00
        currency = sales_invoice.get('currency', 'JOD')
        # Round discount amount to 9 decimal places then format for display
        discount_decimal = Decimal(str(discount_amount)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        etree.SubElement(allowance_charge, "{%s}Amount" % self.nsmap['cbc'], currencyID=currency).text = f"{discount_decimal:.9f}".rstrip('0').rstrip('.')
    
    def _add_tax_total(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add TaxTotal element."""
        tax_total = etree.SubElement(root, "{%s}TaxTotal" % self.nsmap['cac'])
        
        is_return = sales_invoice.get('is_return', 0)
        total_taxes = sales_invoice.get('total_taxes_and_charges') or 0.00
        net_total = sales_invoice.get('net_total') or 0.00
        
        # Convert amounts for Credit Notes (negative to positive)
        total_taxes = self._convert_amount_for_credit_note(total_taxes, is_return)
        net_total = self._convert_amount_for_credit_note(net_total, is_return)
        
        currency = sales_invoice.get('currency', 'JOD')
        # Apply 9 decimal precision for tax amounts
        tax_decimal = Decimal(str(total_taxes)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        etree.SubElement(tax_total, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{tax_decimal:.9f}".rstrip('0').rstrip('.')
        
        # Add tax subtotal
        tax_subtotal = etree.SubElement(tax_total, "{%s}TaxSubtotal" % self.nsmap['cac'])
        # Apply 9 decimal precision for tax subtotal amounts
        net_decimal = Decimal(str(net_total)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        tax_decimal = Decimal(str(total_taxes)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        etree.SubElement(tax_subtotal, "{%s}TaxableAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{net_decimal:.9f}".rstrip('0').rstrip('.')
        etree.SubElement(tax_subtotal, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{tax_decimal:.9f}".rstrip('0').rstrip('.')
        
        # Tax Category
        tax_category = etree.SubElement(tax_subtotal, "{%s}TaxCategory" % self.nsmap['cac'])
        category_id = "S" if total_taxes > 0 else "Z"  # S for standard rate, Z for zero rate
        etree.SubElement(tax_category, "{%s}ID" % self.nsmap['cbc']).text = category_id
        
        # Calculate tax percentage
        tax_percent = 0.00
        if net_total > 0 and total_taxes > 0:
            tax_percent = (total_taxes / net_total) * 100
        etree.SubElement(tax_category, "{%s}Percent" % self.nsmap['cbc']).text = f"{tax_percent:.2f}"
        
        # Tax Scheme
        tax_scheme = etree.SubElement(tax_category, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
    
    def _add_legal_monetary_total(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add LegalMonetaryTotal element."""
        monetary_total = etree.SubElement(root, "{%s}LegalMonetaryTotal" % self.nsmap['cac'])
        
        is_return = sales_invoice.get('is_return', 0)
        currency = sales_invoice.get('currency', 'JOD')
        net_total = sales_invoice.get('net_total') or 0.00
        grand_total = sales_invoice.get('grand_total') or 0.00
        discount_amount = sales_invoice.get('discount_amount') or 0.00
        
        # Convert amounts for Credit Notes (negative to positive)
        net_total = self._convert_amount_for_credit_note(net_total, is_return)
        grand_total = self._convert_amount_for_credit_note(grand_total, is_return)
        discount_amount = self._convert_amount_for_credit_note(discount_amount, is_return)
        
        # Apply 9 decimal precision for all monetary amounts
        net_decimal = Decimal(str(net_total)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        grand_decimal = Decimal(str(grand_total)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        discount_decimal = Decimal(str(discount_amount)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
        
        etree.SubElement(monetary_total, "{%s}TaxExclusiveAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{net_decimal:.9f}".rstrip('0').rstrip('.')
        etree.SubElement(monetary_total, "{%s}TaxInclusiveAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{grand_decimal:.9f}".rstrip('0').rstrip('.')
        etree.SubElement(monetary_total, "{%s}AllowanceTotalAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{discount_decimal:.9f}".rstrip('0').rstrip('.')
        etree.SubElement(monetary_total, "{%s}PayableAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{grand_decimal:.9f}".rstrip('0').rstrip('.')
    
    def _add_invoice_lines(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add InvoiceLine elements for each item."""
        items = sales_invoice.get('items', [])
        currency = sales_invoice.get('currency', 'JOD')
        is_return = sales_invoice.get('is_return', 0)
        
        for idx, item in enumerate(items, 1):
            invoice_line = etree.SubElement(root, "{%s}InvoiceLine" % self.nsmap['cac'])
            
            etree.SubElement(invoice_line, "{%s}ID" % self.nsmap['cbc']).text = str(idx)
            
            qty = item.get('qty', 1)
            uom = item.get('uom', 'PCE')
            # Convert quantity for Credit Notes (negative to positive)
            qty = self._convert_amount_for_credit_note(qty, is_return)
            etree.SubElement(invoice_line, "{%s}InvoicedQuantity" % self.nsmap['cbc'], unitCode=uom).text = str(qty)
            
            amount = item.get('amount', 0.00)
            # Convert amount for Credit Notes (negative to positive)
            amount = self._convert_amount_for_credit_note(amount, is_return)
            # Apply 9 decimal precision for line extension amount
            amount_decimal = Decimal(str(amount)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
            etree.SubElement(invoice_line, "{%s}LineExtensionAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{amount_decimal:.9f}".rstrip('0').rstrip('.')
            
            # Tax Total for line item (simplified)
            line_tax_total = etree.SubElement(invoice_line, "{%s}TaxTotal" % self.nsmap['cac'])
            etree.SubElement(line_tax_total, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = "0.00"
            
            # Item details
            item_element = etree.SubElement(invoice_line, "{%s}Item" % self.nsmap['cac'])
            item_name = item.get('item_name') or item.get('item_code', 'Item')
            etree.SubElement(item_element, "{%s}Name" % self.nsmap['cbc']).text = str(item_name)
            
            # Price details
            price = etree.SubElement(invoice_line, "{%s}Price" % self.nsmap['cac'])
            rate = item.get('rate', 0.00)
            # Convert rate for Credit Notes (negative to positive)
            rate = self._convert_amount_for_credit_note(rate, is_return)
            # Apply 9 decimal precision for price amount
            rate_decimal = Decimal(str(rate)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
            etree.SubElement(price, "{%s}PriceAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{rate_decimal:.9f}".rstrip('0').rstrip('.')
    
    def validate_xml_schema(self, xml_content: str) -> Dict[str, Any]:
        """
        Validate generated XML against UBL 2.1 schema.
        
        Args:
            xml_content: XML string to validate
            
        Returns:
            Dict containing validation results:
            - is_valid: bool
            - errors: list of error messages
            - warnings: list of warning messages
        """
        try:
            # Parse XML content
            doc = etree.fromstring(xml_content.encode('utf-8'))
            
            # Basic validation - check required elements exist
            required_elements = [
                './/{%s}ProfileID' % self.nsmap['cbc'],
                './/{%s}ID' % self.nsmap['cbc'], 
                './/{%s}UUID' % self.nsmap['cbc'],
                './/{%s}IssueDate' % self.nsmap['cbc'],
                './/{%s}InvoiceTypeCode' % self.nsmap['cbc'],
                './/{%s}DocumentCurrencyCode' % self.nsmap['cbc'],
                './/{%s}TaxCurrencyCode' % self.nsmap['cbc']
            ]
            
            errors = []
            for xpath in required_elements:
                if doc.find(xpath) is None:
                    element_name = xpath.split('}')[-1]
                    errors.append(f"Required element {element_name} is missing")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': []
            }
            
        except Exception as e:
            return {
                'is_valid': False,
                'errors': [f"XML parsing error: {str(e)}"],
                'warnings': []
            }
    
    def calculate_line_extension_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal = Decimal('0')) -> Decimal:
        """
        Calculate line extension amount with 9 decimal precision.
        
        Formula: ROUND((quantity * unitPrice) - Discount, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item
            discount: Discount amount
            
        Returns:
            Decimal: Line extension amount rounded to 9 decimal places
        """
        result = (quantity * unit_price) - discount
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
    
    def calculate_tax_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal, tax_percent: Decimal) -> Decimal:
        """
        Calculate tax amount with 9 decimal precision.
        
        Formula: ROUND(((quantity * unitPrice) - discount) * taxPercent, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item  
            discount: Discount amount
            tax_percent: Tax percentage (as decimal, e.g., 0.16 for 16%)
            
        Returns:
            Decimal: Tax amount rounded to 9 decimal places
        """
        taxable_amount = (quantity * unit_price) - discount
        result = taxable_amount * tax_percent
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
    
    def calculate_rounding_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal, tax_amount: Decimal) -> Decimal:
        """
        Calculate rounding amount with 9 decimal precision.
        
        Formula: ROUND((quantity * unitPrice - discount) + TaxAmount, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item
            discount: Discount amount
            tax_amount: Calculated tax amount
            
        Returns:
            Decimal: Rounding amount rounded to 9 decimal places
        """
        base_amount = (quantity * unit_price) - discount
        result = base_amount + tax_amount
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP) 