"""
JoFotara Logger Utility

Simple logging of JoFotara API requests and responses to custom JoFotara Log doctype.
Creates only ONE log entry per invoice submission for debugging API issues.
"""

import frappe
from typing import Dict, Any




def log_api_submission(sales_invoice: str, request_payload: Dict[str, Any], 
                      response_data: Dict[str, Any], success: bool) -> str:
    """
    Log actual JoFotara API submission - the only log we create per request
    
    Args:
        sales_invoice (str): Sales Invoice name/ID
        request_payload (dict): Complete request payload sent to API
        response_data (dict): Complete response from API
        success (bool): Whether the API call was successful
        
    Returns:
        str: Created JoFotara Log document name
    """
    try:
        # Sanitize request payload to avoid logging sensitive data
        sanitized_request = request_payload.copy()
        if "headers" in sanitized_request:
            headers = sanitized_request["headers"].copy()
            if "Secret-Key" in headers:
                headers["Secret-Key"] = "***HIDDEN***"
            sanitized_request["headers"] = headers
        
        status = "Success" if success else "Error"
        
        # Create JoFotara Log document directly (simplified from multiple helper functions)
        frappe.get_doc({
            "doctype": "JoFotara Log",
            "sales_invoice": sales_invoice,
            "status": status,
            "request_payload": frappe.as_json(sanitized_request),
            "response_payload": frappe.as_json(response_data)
        }).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return sales_invoice  # Return something to indicate success
        
    except Exception as e:
        # Fallback to error log if JoFotara Log creation fails
        frappe.log_error(f"Failed to create JoFotara Log for {sales_invoice}: {str(e)}")
        frappe.log_error(f"Request data: {frappe.as_json(sanitized_request)}")
        frappe.log_error(f"Response data: {frappe.as_json(response_data)}")
        return None


 