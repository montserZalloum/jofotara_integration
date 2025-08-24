import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_custom_fields():
    custom_fields = {
        "Item Tax Template": [
            {
                "fieldname": "is_jofotara_special_tax",
                "label": "Is Jofotara Special Tax",
                "fieldtype": "Check",
                "insert_after": "company",
                "default": 0,
                "description": (
                    "Check this box if this tax rate applies to goods with a "
                    "'special tax rate' as defined by Jofotara (e.g., tobacco). "
                    "Invoices containing items with this tax template will be "
                    "categorized as 'Special Sales'."
                )
            }
        ]
    }

    create_custom_fields(custom_fields)
