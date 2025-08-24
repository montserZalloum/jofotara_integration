import frappe
from frappe import _
from typing import Dict, Any, List, Optional


class ValidationService:
    """
    Service class for handling JoFotara validation rules and compliance checks.
    """
    
    def __init__(self):
        pass
    
    def validate_company_item_compliance(self, sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that unregistered companies cannot include items with special tax templates.
        
        Args:
            sales_invoice: Sales Invoice document or dictionary
            
        Returns:
            Dict containing validation result with success status and error message if applicable
        """
        try:
            # Get company information
            company_name = sales_invoice.get('company')
            if not company_name:
                return {
                    'success': True,
                    'message': 'No company specified, skipping validation'
                }
            
            company_doc = frappe.get_doc("Company", company_name)
            
            # Check if JoFotara is active for this company
            jofotara_is_active = getattr(company_doc, 'jofotara_is_active', 0)
            if not jofotara_is_active:
                return {
                    'success': True,
                    'message': 'JoFotara integration not active for this company'
                }
            
            # Check company registration status
            is_registered = getattr(company_doc, 'is_jordan_sales_tax_registered', 0)
            
            # If company is registered, no validation needed
            if is_registered:
                return {
                    'success': True,
                    'message': 'Company is registered, special tax items allowed'
                }
            
            # Company is unregistered - check for special tax items
            special_tax_items = self._get_special_tax_items(sales_invoice)
            
            if special_tax_items:
                error_message = self._create_validation_error_message(special_tax_items)
                return {
                    'success': False,
                    'error_message': error_message,
                    'special_items': special_tax_items
                }
            
            return {
                'success': True,
                'message': 'Validation passed - no special tax items found'
            }
            
        except Exception as e:
            frappe.log_error(
                f"Company item compliance validation failed: {str(e)}",
                "JoFotara Validation Error"
            )
            return {
                'success': False,
                'error_message': f'Validation failed due to system error: {str(e)}'
            }
    
    def _get_special_tax_items(self, sales_invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get list of items with special tax templates from the sales invoice.
        
        Args:
            sales_invoice: Sales Invoice document or dictionary
            
        Returns:
            List of items with special tax templates
        """
        special_items = []
        
        for item in sales_invoice.get('items', []):
            item_tax_template = item.get('item_tax_template')
            if item_tax_template:
                try:
                    tax_template_doc = frappe.get_doc("Item Tax Template", item_tax_template)
                    if getattr(tax_template_doc, 'is_jofotara_special_tax', 0):
                        special_items.append({
                            'item_code': item.get('item_code', 'Unknown'),
                            'item_name': item.get('item_name', 'Unknown'),
                            'item_tax_template': item_tax_template,
                            'qty': item.get('qty', 0),
                            'rate': item.get('rate', 0)
                        })
                except Exception as e:
                    frappe.log_error(
                        f"Error checking tax template {item_tax_template}: {str(e)}",
                        "JoFotara Validation Error"
                    )
        
        return special_items
    
    def _create_validation_error_message(self, special_items: List[Dict[str, Any]]) -> str:
        """
        Create a clear, actionable error message for compliance violation.
        
        Args:
            special_items: List of items with special tax templates
            
        Returns:
            Formatted error message with actionable guidance
        """
        item_count = len(special_items)
        item_names = [item['item_name'] for item in special_items[:3]]  # Show first 3 items
        
        if item_count == 1:
            items_text = f"item '{item_names[0]}'"
        elif item_count <= 3:
            items_text = f"items: {', '.join(item_names)}"
        else:
            items_text = f"items including: {', '.join(item_names)} and {item_count - 3} more"
        
        error_message = _(
            "Compliance Violation: Your company is not registered for Jordanian sales tax, "
            "but this invoice contains {items_text} with special tax templates. "
            "Unregistered companies cannot include items with special tax treatment."
        ).format(items_text=items_text)
        
        resolution_message = _(
            "To resolve this issue, you can either:\n"
            "1. Remove the special tax items from this invoice, or\n"
            "2. Register your company for Jordanian sales tax in the Company master"
        )
        
        return f"{error_message}\n\n{resolution_message}"
    
    def validate_unregistered_company_special_items(self, sales_invoice) -> None:
        """
        Main validation method to be called from hooks.
        Throws frappe.ValidationError if validation fails.
        
        Args:
            sales_invoice: Sales Invoice document
            
        Raises:
            frappe.ValidationError: If validation fails
        """
        validation_result = self.validate_company_item_compliance(sales_invoice.as_dict())
        
        if not validation_result['success']:
            frappe.throw(
                validation_result['error_message'],
                title=_("JoFotara Compliance Violation")
            )


# Global instance for easy access
validation_service = ValidationService()


@frappe.whitelist()
def is_special_tax_template(tax_template: str) -> Dict[str, Any]:
    """
    Check if a tax template is marked as special for JoFotara.
    
    Args:
        tax_template: Name of the Item Tax Template
        
    Returns:
        Dict with is_special boolean flag
    """
    try:
        if not tax_template:
            return {'is_special': False}
        
        tax_template_doc = frappe.get_doc("Item Tax Template", tax_template)
        is_special = getattr(tax_template_doc, 'is_jofotara_special_tax', 0)
        
        return {'is_special': bool(is_special)}
        
    except Exception as e:
        frappe.log_error(
            f"Error checking special tax template {tax_template}: {str(e)}",
            "JoFotara Validation Error"
        )
        return {'is_special': False}
