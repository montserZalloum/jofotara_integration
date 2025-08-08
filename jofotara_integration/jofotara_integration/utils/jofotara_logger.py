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
        log_doc = {
            "doctype": "JoFotara Log",
            "sales_invoice": sales_invoice,
            "status": status,
            "icv_value": sanitized_request.get("icv_value"),
            "request_payload": frappe.as_json(sanitized_request),
            "response_payload": frappe.as_json(response_data)
        }
        frappe.get_doc(log_doc).insert(ignore_permissions=True)
        
        frappe.db.commit()
        
        return sales_invoice  # Return something to indicate success
        
    except Exception as e:
        # Fallback to database logging if JoFotara Log creation fails
        # Avoid frappe.log_error() which may have file permission issues in background jobs
        try:
            # Use frappe.db.sql for direct database logging as fallback
            frappe.db.sql("""
                INSERT INTO `tabError Log` (`name`, `title`, `error`, `creation`, `owner`)
                VALUES (%(name)s, %(title)s, %(error)s, NOW(), 'Administrator')
            """, {
                'name': frappe.generate_hash(length=10),
                'title': f"JoFotara Log Creation Failed",
                'error': f"Failed to create JoFotara Log for {sales_invoice}: {str(e)}\nRequest: {frappe.as_json(sanitized_request)}\nResponse: {frappe.as_json(response_data)}"
            })
            frappe.db.commit()
        except Exception:
            # If even database logging fails, just pass silently
            # The main submission will still work, we just lose the log entry
            pass
        return None


 