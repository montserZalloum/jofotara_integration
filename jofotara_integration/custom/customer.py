import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_custom_fields():
    custom_fields = {
        "Customer": [
            {
                "fieldname": "custom_is_in_development_area",
                "label": "Is in Development Area",
                "fieldtype": "Check",
                "insert_after": "customer_group",
                "default": 0,
                "description": "If the customer is in the Development Area, the invoice will be treated as a Development Area invoice (For JoFotara e-invoicing)"
            }
        ]
    }

    create_custom_fields(custom_fields)
