import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def add_custom_fields():
    """
    Add custom ICV counter field to Sales Invoice
    """
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "custom_icv_counter",
                "label": "JoFotara ICV",
                "fieldtype": "Int",
                "insert_after": "company",
                "read_only": 1,
                "no_copy": 1,
                "description": "Invoice Counter Value assigned by JoFotara integration",
                "depends_on": "eval:doc.company",
                "precision": "",
                "options": "",
                "reqd": 0,
                "default": ""
            }
        ]
    }

    create_custom_fields(custom_fields)
