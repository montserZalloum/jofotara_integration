"""
Buyer Information Validation Module for JoFotara Integration

This module provides validation logic for buyer information requirements
based on invoice type, amount, and payment method according to JoFotara compliance rules.
"""

import frappe
from typing import Dict, Any, List
from decimal import Decimal

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
        
        # Add warnings for edge cases
        if currency != 'JOD' and grand_total >= JOD_THRESHOLD:
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
        # Convert amount to JOD for threshold comparison
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
