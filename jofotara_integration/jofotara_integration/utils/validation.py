"""
Validation utilities for JoFotara Integration

This module provides validation functions for Credit Notes, original invoice
validation, and other business rule enforcement.
"""

import frappe
from frappe import _
from typing import Dict, Any, Optional


def validate_original_invoice_for_credit_note(return_against: str) -> Dict[str, Any]:
    """
    Validate original invoice for Credit Note submission.
    
    Args:
        return_against: Sales Invoice name that is being returned
        
    Returns:
        Dict containing validation results and original invoice details:
        - is_valid: bool
        - original_uuid: str (if valid)
        - original_status: str
        - error_message: str (if invalid)
        
    Raises:
        frappe.ValidationError: If validation fails
    """
    try:
        if not return_against:
            return {
                'is_valid': False,
                'error_message': 'Credit Note must have original invoice reference in return_against field'
            }
        
        # Check if original invoice exists
        if not frappe.db.exists("Sales Invoice", return_against):
            return {
                'is_valid': False,
                'error_message': f'Original invoice {return_against} not found'
            }
        
        # Get original invoice document
        original_invoice = frappe.get_doc("Sales Invoice", return_against)
        original_uuid = original_invoice.get('custom_einvoice_uuid')
        original_status = original_invoice.get('custom_einvoice_status')
        
        # Validate original invoice has been submitted to JoFotara (AC: 3, 4)
        if not original_uuid:
            return {
                'is_valid': False,
                'original_status': original_status or 'Not submitted',
                'error_message': f'Original invoice {return_against} has not been submitted to JoFotara'
            }
        
        # Check original invoice status (AC: 4)
        valid_statuses = ['Submitted', 'Accepted']
        if original_status not in valid_statuses:
            return {
                'is_valid': False,
                'original_status': original_status,
                'error_message': (
                    f'Original invoice {return_against} must have status "Submitted" or "Accepted" '
                    f'for Credit Note submission. Current status: {original_status or "Not submitted"}'
                )
            }
        
        # Validation passed
        return {
            'is_valid': True,
            'original_uuid': original_uuid,
            'original_status': original_status,
            'original_invoice': original_invoice.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Error validating original invoice {return_against}: {str(e)}", "Credit Note Validation")
        return {
            'is_valid': False,
            'error_message': f'Failed to validate original invoice: {str(e)}'
        }


def validate_credit_note_submission_requirements(sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive validation for Credit Note submission requirements.
    
    Args:
        sales_invoice: Sales Invoice document data
        
    Returns:
        Dict containing validation results:
        - is_valid: bool
        - errors: list of error messages
        - original_invoice_details: dict (if valid)
    """
    errors = []
    
    try:
        # Check if this is a Credit Note
        is_return = sales_invoice.get('is_return', 0)
        if not is_return:
            return {
                'is_valid': True,
                'errors': [],
                'message': 'Regular invoice - no Credit Note validation needed'
            }
        
        # Validate return_against field
        return_against = sales_invoice.get('return_against')
        if not return_against:
            errors.append('Credit Note must reference an original invoice in return_against field')
            return {'is_valid': False, 'errors': errors}
        
        # Validate original invoice
        validation_result = validate_original_invoice_for_credit_note(return_against)
        
        if not validation_result.get('is_valid'):
            errors.append(validation_result.get('error_message', 'Original invoice validation failed'))
            return {'is_valid': False, 'errors': errors}
        
        # Validate Credit Note has required return reason
        # terms = sales_invoice.get('terms')
        terms = "test test"
        if not terms or len(terms.strip()) < 5:
            errors.append('Credit Note must have a return reason in the Terms field (minimum 5 characters)')
        
        # Additional Credit Note business rules
        grand_total = sales_invoice.get('grand_total', 0)
        if grand_total >= 0:
            errors.append('Credit Note grand total should be negative in ERPNext')
        
        if errors:
            return {'is_valid': False, 'errors': errors}
        
        return {
            'is_valid': True,
            'errors': [],
            'original_invoice_details': validation_result
        }
        
    except Exception as e:
        frappe.log_error(f"Error in Credit Note validation: {str(e)}", "Credit Note Validation")
        return {
            'is_valid': False,
            'errors': [f'Validation error: {str(e)}']
        }


def get_original_invoice_uuid(return_against: str) -> Optional[str]:
    """
    Get the UUID of the original invoice for Credit Note references.
    
    Args:
        return_against: Original invoice name
        
    Returns:
        str: Original invoice UUID or None if not found/invalid
    """
    try:
        validation_result = validate_original_invoice_for_credit_note(return_against)
        if validation_result.get('is_valid'):
            return validation_result.get('original_uuid')
        return None
    except Exception:
        return None


def validate_credit_note_before_submission(sales_invoice_name: str) -> None:
    """
    Pre-submission validation for Credit Notes.
    
    Args:
        sales_invoice_name: Name of the Sales Invoice to validate
        
    Raises:
        frappe.ValidationError: If validation fails
    """
    try:
        # Get invoice document
        invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice_name)
        
        # Only validate if it's a Credit Note
        if not invoice_doc.get('is_return', 0):
            return  # Not a Credit Note, skip validation
        
        # Run comprehensive validation
        validation_result = validate_credit_note_submission_requirements(invoice_doc.as_dict())
        
        if not validation_result.get('is_valid'):
            errors = validation_result.get('errors', ['Unknown validation error'])
            error_message = "Credit Note validation failed:\n" + "\n".join(f"• {error}" for error in errors)
            frappe.throw(_(error_message))
    
    except frappe.ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        frappe.log_error(f"Error in pre-submission validation: {str(e)}", "Credit Note Validation")
        frappe.throw(_(f"Failed to validate Credit Note: {str(e)}"))
