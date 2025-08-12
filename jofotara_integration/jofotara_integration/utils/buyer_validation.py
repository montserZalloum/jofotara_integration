"""
Buyer Information Validation Module for JoFotara Integration

This module provides validation logic for buyer information requirements
based on invoice type, amount, and payment method according to JoFotara compliance rules.
"""

import frappe
from typing import Dict, Any, List
from decimal import Decimal
from jofotara_integration.jofotara_integration.services.currency_service import get_multi_currency_service

# Validation Constants
JOD_THRESHOLD = 10000.0  # JOD threshold for cash invoice buyer name requirement
MIN_NAME_LENGTH = 2      # Minimum buyer name length
DEFAULT_CURRENCY_RATE = 1.0  # Fallback currency rate (1:1) for safety

# Currency fallback rates (conservative estimates)
CURRENCY_FALLBACK_RATES = {
    'USD': 0.71,    # 1 USD = 0.71 JOD
    'EUR': 0.76,    # 1 EUR = 0.76 JOD  
    'SAR': 0.19,    # 1 SAR = 0.19 JOD
    'AED': 0.19     # 1 AED = 0.19 JOD
}


class BuyerValidationError(Exception):
    """Custom exception for buyer validation errors."""
    pass


def validate_buyer_requirements(sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate buyer information requirements based on invoice characteristics.
    
    Validation Rules:
    1. Credit invoices always require mandatory buyer name validation
    2. Cash invoices ≥10,000 JOD require mandatory buyer name validation
    3. Exactly 10,000 JOD invoices require buyer info (same as >10,000 JOD per FR17)
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        Dict containing:
        - is_valid: bool
        - errors: List of validation error messages
        - warnings: List of warning messages
        - required_fields: List of required fields for this invoice type
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'required_fields': []
    }
    
    try:
        # Get invoice details
        is_pos = sales_invoice.get('is_pos', 0)
        grand_total = sales_invoice.get('grand_total', 0)
        currency = sales_invoice.get('currency', 'JOD')
        customer_name = sales_invoice.get('customer_name', '').strip()
        
        # Determine validation requirements
        requires_buyer_name = _determine_buyer_name_requirement(sales_invoice)
        
        if requires_buyer_name:
            validation_result['required_fields'].append('customer_name')
            
            # Validate buyer name presence
            if not customer_name:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    _get_buyer_name_error_message(is_pos, grand_total, currency)
                )
            elif len(customer_name) < MIN_NAME_LENGTH:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    f"Buyer name must be at least {MIN_NAME_LENGTH} characters long"
                )
        
        # Enhanced multi-currency threshold validation
        if currency != 'JOD':
            try:
                # Use enhanced currency service for precise conversion
                currency_service = get_multi_currency_service()
                threshold_result = currency_service.validate_multi_currency_threshold(
                    Decimal(str(grand_total)), currency, _get_customer_info_basic(sales_invoice)
                )
                
                if threshold_result.get('exceeds_threshold', False):
                    jod_equivalent = threshold_result.get('jod_equivalent', grand_total)
                    # Shorten message to avoid ERPNext 140-char error log limit
                    validation_result['warnings'].append(
                        f"High-value {currency} invoice exceeds 10K JOD threshold: "
                        f"{currency} {grand_total:,.2f} ≈ JOD {jod_equivalent:.2f}"
                    )
            except Exception as e:
                # Fallback to original logic
                frappe.log_error(f"Enhanced currency validation failed: {str(e)}", "Buyer Validation")
                converted_amount = _convert_currency_to_jod(grand_total, currency)
                if converted_amount >= JOD_THRESHOLD:
                    validation_result['warnings'].append(
                        f"High-value invoice ({currency} {grand_total:,.2f} ≈ JOD {converted_amount:,.2f}) "
                        f"exceeds threshold and may require additional documentation"
                    )
        
        return validation_result
        
    except Exception as e:
        frappe.log_error(f"Error in buyer validation: {str(e)}", "Buyer Validation")
        return {
            'is_valid': False,
            'errors': [f"Validation error: {str(e)}"],
            'warnings': [],
            'required_fields': []
        }


def _determine_buyer_name_requirement(sales_invoice: Dict[str, Any]) -> bool:
    """
    Determine if buyer name is required based on invoice characteristics.
    
    Requirements:
    - Credit invoices (is_pos=0): Always required
    - Cash invoices (is_pos=1): Required if amount ≥ 10,000 JOD (including exactly 10,000)
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        bool: True if buyer name is required
    """
    is_pos = sales_invoice.get('is_pos', 0)
    grand_total = sales_invoice.get('grand_total', 0)
    currency = sales_invoice.get('currency', 'JOD')
    
    # Credit invoices always require buyer name
    if not is_pos:
        return True
    
    # Cash invoices require buyer name if ≥ 10,000 JOD (FR17: exactly 10,000 JOD = above threshold)
    if is_pos:
        try:
            # Use enhanced currency service for precise threshold validation
            currency_service = get_multi_currency_service()
            threshold_result = currency_service.validate_multi_currency_threshold(
                Decimal(str(grand_total)), currency, _get_customer_info_basic(sales_invoice)
            )
            return threshold_result.get('requires_buyer_validation', False)
        except Exception as e:
            frappe.log_error(f"Enhanced threshold validation failed, using fallback: {str(e)}", "Buyer Validation")
            # Fallback to original conversion logic
            jod_amount = _convert_currency_to_jod(grand_total, currency)
            return jod_amount >= JOD_THRESHOLD
    
    return False


def _convert_currency_to_jod(amount: float, currency: str) -> float:
    """
    Convert amount to JOD using current exchange rates.
    
    Supported currencies: USD, EUR, SAR, AED
    
    Args:
        amount: Amount to convert
        currency: Source currency code
        
    Returns:
        float: Amount in JOD
    """
    if currency == 'JOD':
        return amount
    
    # Get exchange rate from ERPNext Currency Exchange
    try:
        exchange_rate = frappe.db.get_value(
            "Currency Exchange",
            {"from_currency": currency, "to_currency": "JOD"},
            "exchange_rate"
        )
        
        if exchange_rate:
            return amount * exchange_rate
        else:
            # Fallback to approximate rates if no exact rate found
            fallback_rates = {
                'USD': 0.71,  # 1 USD ≈ 0.71 JOD
                'EUR': 0.76,  # 1 EUR ≈ 0.76 JOD  
                'SAR': 0.19,  # 1 SAR ≈ 0.19 JOD
                'AED': 0.19   # 1 AED ≈ 0.19 JOD
            }
            
            rate = fallback_rates.get(currency, 1.0)
            frappe.log_error(
                f"Using fallback exchange rate for {currency}: {rate}",
                "Buyer Validation Currency Conversion"
            )
            return amount * rate
            
    except Exception as e:
        frappe.log_error(
            f"Error getting exchange rate for {currency}: {str(e)}",
            "Buyer Validation Currency Conversion"
        )
        # Conservative approach - assume 1:1 rate to avoid missing validations
        return amount


def _get_customer_info_basic(sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get basic customer information for currency validation context.
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        Dict containing basic customer information
    """
    try:
        customer_name = sales_invoice.get('customer')
        if not customer_name:
            return {}
        
        customer_doc = frappe.get_doc("Customer", customer_name)
        return {
            'customer_type': customer_doc.get('customer_type'),
            'territory': customer_doc.get('territory'),
            'tax_id': customer_doc.get('tax_id')
        }
    except Exception:
        return {}


def validate_enhanced_buyer_requirements(sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced buyer validation with full multi-currency support and 9-decimal precision.
    
    This is the new enhanced version that should be used for new implementations.
    The original validate_buyer_requirements is kept for backward compatibility.
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        Dict containing enhanced validation results with currency details
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'required_fields': [],
        'currency_info': {},
        'threshold_validation': {},
        'precision_maintained': True
    }
    
    try:
        # Get invoice details
        is_pos = sales_invoice.get('is_pos', 0)
        grand_total = sales_invoice.get('grand_total', 0)
        currency = sales_invoice.get('currency', 'JOD')
        customer_name = sales_invoice.get('customer_name', '').strip()
        
        # Enhanced currency validation using multi-currency service
        currency_service = get_multi_currency_service()
        
        # Validate currency support
        currency_validation = currency_service.validate_currency_support(currency)
        if not currency_validation['is_valid']:
            validation_result['is_valid'] = False
            validation_result['errors'].append(currency_validation['error_message'])
            return validation_result
        
        # Get customer info for context
        customer_info = _get_customer_info_basic(sales_invoice)
        
        # Enhanced threshold validation with 9-decimal precision
        threshold_result = currency_service.validate_multi_currency_threshold(
            Decimal(str(grand_total)), currency, customer_info
        )
        validation_result['threshold_validation'] = threshold_result
        
        # Store currency conversion details
        validation_result['currency_info'] = {
            'original_currency': currency,
            'original_amount': grand_total,
            'jod_equivalent': float(threshold_result.get('jod_equivalent', grand_total)),
            'conversion_applied': currency != 'JOD',
            'exceeds_threshold': threshold_result.get('exceeds_threshold', False),
            'threshold_amount': float(threshold_result.get('threshold_amount', JOD_THRESHOLD))
        }
        
        # Determine buyer name requirement using enhanced logic
        requires_buyer_name = _determine_enhanced_buyer_name_requirement(
            sales_invoice, threshold_result
        )
        
        if requires_buyer_name:
            validation_result['required_fields'].append('customer_name')
            
            # Validate buyer name presence
            if not customer_name:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    _get_enhanced_buyer_name_error_message(
                        is_pos, grand_total, currency, threshold_result
                    )
                )
            elif len(customer_name) < MIN_NAME_LENGTH:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    f"Buyer name must be at least {MIN_NAME_LENGTH} characters long"
                )
        
        # Enhanced currency compatibility warnings
        if currency != 'JOD':
            territory = customer_info.get('territory', '')
            if territory:
                # Determine invoice type for compatibility check
                invoice_type = _determine_invoice_type_from_customer(customer_info)
                
                compatibility_result = currency_service.validate_currency_compatibility(
                    currency, territory, invoice_type
                )
                
                # Shorten compatibility warnings to avoid message length limits
                if compatibility_result['warnings']:
                    validation_result['warnings'].extend([
                        f"{currency}-{territory} compatibility issue" 
                        for warning in compatibility_result['warnings'][:2]  # Limit to 2 warnings
                    ])
                
                if compatibility_result['recommendations']:
                    validation_result['warnings'].extend([
                        f"Consider: {rec[:30]}..." if len(rec) > 30 else f"Consider: {rec}"
                        for rec in compatibility_result['recommendations'][:1]  # Limit to 1 recommendation
                    ])
        
        # Validate precision maintenance  
        if threshold_result.get('exceeds_threshold') and currency != 'JOD':
            jod_equivalent = threshold_result.get('jod_equivalent')
            if isinstance(jod_equivalent, Decimal):
                # Check if precision is properly maintained (9 decimal places)
                exponent = jod_equivalent.as_tuple().exponent
                if exponent < -9:
                    validation_result['warnings'].append(
                        "Currency precision >9 decimals"
                    )
                    validation_result['precision_maintained'] = False
        
        return validation_result
        
    except Exception as e:
        frappe.log_error(f"Error in enhanced buyer validation: {str(e)}", "Enhanced Buyer Validation")
        return {
            'is_valid': False,
            'errors': [f"Enhanced validation error: {str(e)}"],
            'warnings': [],
            'required_fields': [],
            'currency_info': {},
            'threshold_validation': {},
            'precision_maintained': False
        }


def _determine_enhanced_buyer_name_requirement(sales_invoice: Dict[str, Any], 
                                               threshold_result: Dict[str, Any]) -> bool:
    """
    Enhanced buyer name requirement determination using multi-currency threshold validation.
    
    Args:
        sales_invoice: Sales Invoice document data
        threshold_result: Result from multi-currency threshold validation
        
    Returns:
        bool: True if buyer name is required
    """
    is_pos = sales_invoice.get('is_pos', 0)
    
    # Credit invoices always require buyer name
    if not is_pos:
        return True
    
    # Cash invoices require buyer name if they exceed the JOD threshold
    return threshold_result.get('requires_buyer_validation', False)


def _get_enhanced_buyer_name_error_message(is_pos: int, grand_total: float, 
                                           currency: str, threshold_result: Dict[str, Any]) -> str:
    """
    Generate enhanced error message with multi-currency details.
    
    Args:
        is_pos: Payment method flag
        grand_total: Invoice total amount
        currency: Invoice currency
        threshold_result: Currency threshold validation result
        
    Returns:
        str: Enhanced error message with precision details
    """
    if is_pos:
        # Cash invoice above threshold
        jod_equivalent = threshold_result.get('jod_equivalent', grand_total)
        threshold_amount = threshold_result.get('threshold_amount', JOD_THRESHOLD)
        
        if currency != 'JOD':
            return (
                f"Cash invoice exceeds {threshold_amount:,.0f} JOD threshold. "
                f"Amount: {currency} {grand_total:,.9f} ≈ JOD {jod_equivalent:.9f} "
                f"(calculated with 9-decimal precision). "
                f"Buyer name is required for JoFotara compliance."
            )
        else:
            return (
                f"Cash invoice of JOD {grand_total:,.9f} exceeds {threshold_amount:,.0f} JOD threshold. "
                f"Buyer name is required for JoFotara compliance."
            )
    else:
        # Credit invoice
        return "Credit invoices require buyer name for JoFotara compliance. Please provide customer name."


def _determine_invoice_type_from_customer(customer_info: Dict[str, Any]) -> str:
    """
    Determine invoice type based on customer information.
    
    Args:
        customer_info: Customer information dictionary
        
    Returns:
        str: Invoice type (Local/Export/Development Area)
    """
    if customer_info.get('is_in_development_area'):
        return 'Development Area'
    elif customer_info.get('territory') != 'Jordan':
        return 'Export'
    else:
        return 'Local'


def _get_buyer_name_error_message(is_pos: int, grand_total: float, currency: str) -> str:
    """
    Generate appropriate error message based on invoice type.
    
    Args:
        is_pos: Payment method (0=Credit, 1=Cash)
        grand_total: Invoice total amount
        currency: Invoice currency
        
    Returns:
        str: Formatted error message
    """
    if not is_pos:
        # Credit invoice
        return ("Credit invoices require buyer name information regardless of amount. "
               f"Please enter customer name in the 'Customer Name' field.")
    else:
        # Cash invoice
        if currency == 'JOD':
            return (f"Cash invoices of {currency} {grand_total:,.2f} "
                   f"(≥ JOD {JOD_THRESHOLD:,.0f} threshold) require buyer name information. "
                   f"Please enter customer name in the 'Customer Name' field.")
        else:
            # Convert to JOD for display
            jod_amount = _convert_currency_to_jod(grand_total, currency)
            return (f"Cash invoices of {currency} {grand_total:,.2f} "
                   f"(≈ JOD {jod_amount:,.2f}, ≥ JOD {JOD_THRESHOLD:,.0f} threshold) require buyer name information. "
                   f"Please enter customer name in the 'Customer Name' field.")


def validate_customer_id_scheme(sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate customer ID scheme selection (TN/NIN/PN) based on customer type.
    
    Scheme Rules:
    - TN (Tax Number): For companies with valid tax ID
    - NIN (National ID): For Jordanian individuals
    - PN (Personal No.): For non-Jordanian individuals
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        Dict containing validation results and recommended scheme
    """
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'recommended_scheme': 'NAT',  # Default fallback
        'customer_info': {}
    }
    
    try:
        customer_name = sales_invoice.get('customer')
        if not customer_name:
            validation_result['warnings'].append("No customer specified")
            return validation_result
        
        # Get customer document
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_type = customer_doc.get('customer_type', 'Individual')
        tax_id = customer_doc.get('tax_id', '').strip()
        territory = customer_doc.get('territory', '')
        
        validation_result['customer_info'] = {
            'customer_type': customer_type,
            'tax_id': tax_id,
            'territory': territory
        }
        
        # Determine appropriate scheme
        if customer_type == 'Company':
            if tax_id:
                validation_result['recommended_scheme'] = 'TIN'
            else:
                validation_result['is_valid'] = False
                validation_result['errors'].append(
                    "Company customers must have a valid Tax ID for TIN scheme"
                )
        else:
            # Individual customer
            if territory == 'Jordan':
                validation_result['recommended_scheme'] = 'NAT'  # National ID for Jordanians
                if not tax_id:
                    validation_result['warnings'].append(
                        "Jordanian customers should have National ID number"
                    )
            else:
                validation_result['recommended_scheme'] = 'NAT'  # Personal No. for non-Jordanians
                # Note: Using NAT as the scheme name, but this represents Personal No. for non-Jordanians
                if not tax_id:
                    validation_result['warnings'].append(
                        "Non-Jordanian customers should have Personal ID number"
                    )
        
        return validation_result
        
    except Exception as e:
        frappe.log_error(f"Error in customer ID scheme validation: {str(e)}", "Buyer Validation")
        return {
            'is_valid': False,
            'errors': [f"ID scheme validation error: {str(e)}"],
            'warnings': [],
            'recommended_scheme': 'NAT',
            'customer_info': {}
        }


def get_validation_checklist(sales_invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate a validation checklist for the given invoice.
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        List of validation items with status and requirements
    """
    checklist = []
    
    # Buyer name validation
    buyer_validation = validate_buyer_requirements(sales_invoice)
    checklist.append({
        'check': 'Buyer Name Requirement',
        'status': 'passed' if buyer_validation['is_valid'] else 'failed',
        'required': len(buyer_validation['required_fields']) > 0,
        'message': buyer_validation['errors'][0] if buyer_validation['errors'] else 'Buyer name validation passed',
        'details': buyer_validation
    })
    
    # Customer ID scheme validation
    id_scheme_validation = validate_customer_id_scheme(sales_invoice)
    checklist.append({
        'check': 'Customer ID Scheme',
        'status': 'passed' if id_scheme_validation['is_valid'] else 'warning',
        'required': True,
        'message': f"Recommended scheme: {id_scheme_validation['recommended_scheme']}",
        'details': id_scheme_validation
    })
    
    # Invoice type classification
    is_pos = sales_invoice.get('is_pos', 0)
    grand_total = sales_invoice.get('grand_total', 0)
    currency = sales_invoice.get('currency', 'JOD')
    
    checklist.append({
        'check': 'Invoice Classification',
        'status': 'passed',
        'required': True,
        'message': f"{'Cash' if is_pos else 'Credit'} invoice - {currency} {grand_total:,.2f}",
        'details': {
            'payment_method': 'Cash' if is_pos else 'Credit',
            'amount': grand_total,
            'currency': currency
        }
    })
    
    return checklist


def validate_pre_submission(sales_invoice_name: str) -> Dict[str, Any]:
    """
    Comprehensive pre-submission validation for a Sales Invoice.
    
    This function should be called before XML generation to ensure
    all buyer information requirements are met.
    
    Args:
        sales_invoice_name: Name of the Sales Invoice document
        
    Returns:
        Dict containing comprehensive validation results
    """
    try:
        # Get sales invoice document
        sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
        sales_invoice_dict = sales_invoice_doc.as_dict()
        
        # Run all validations
        buyer_validation = validate_buyer_requirements(sales_invoice_dict)
        id_scheme_validation = validate_customer_id_scheme(sales_invoice_dict)
        checklist = get_validation_checklist(sales_invoice_dict)
        
        # Determine overall validation status
        all_valid = buyer_validation['is_valid'] and id_scheme_validation['is_valid']
        
        # Collect all errors and warnings
        all_errors = buyer_validation['errors'] + id_scheme_validation['errors']
        all_warnings = buyer_validation['warnings'] + id_scheme_validation['warnings']
        
        return {
            'is_valid': all_valid,
            'errors': all_errors,
            'warnings': all_warnings,
            'checklist': checklist,
            'buyer_validation': buyer_validation,
            'id_scheme_validation': id_scheme_validation,
            'invoice_name': sales_invoice_name
        }
        
    except Exception as e:
        frappe.log_error(f"Error in pre-submission validation: {str(e)}", "Buyer Validation")
        return {
            'is_valid': False,
            'errors': [f"Pre-submission validation failed: {str(e)}"],
            'warnings': [],
            'checklist': [],
            'invoice_name': sales_invoice_name
        }
