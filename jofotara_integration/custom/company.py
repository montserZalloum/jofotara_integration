import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def add_custom_fields():
    custom_fields = {
        "Company": [
            {
                "fieldname": "jofotara_section",
                "label": "JoFotara E-Invoicing",
                "fieldtype": "Section Break",
                "insert_after": "registration_info",
                "collapsible": 1
            },
            {
                "fieldname": "jofotara_is_active",
                "label": "Enable JoFotara Integration",
                "fieldtype": "Check",
                "insert_after": "jofotara_section",
                "default": 0,
                "description": "Enable JoFotara e-invoicing for this company"
            },
            {
                "fieldname": "jofotara_client_id",
                "label": "JoFotara Client ID",
                "fieldtype": "Data",
                "insert_after": "jofotara_is_active",
                "depends_on": "jofotara_is_active",
                "length": 100,
                "description": "Client ID provided by JoFotara for API authentication"
            },
            {
                "fieldname": "jofotara_secret_key",
                "label": "JoFotara Secret Key",
                "fieldtype": "Password",
                "no_strength_check": 1,
                "insert_after": "jofotara_client_id",
                "depends_on": "jofotara_is_active",
                "length": 500,
                "description": "Secret Key provided by JoFotara for API authentication (encrypted)"
            },
            {
                "fieldname": "jofotara_activity_serial",
                "label": "Activity Serial Number",
                "fieldtype": "Data",
                "insert_after": "jofotara_secret_key",
                "depends_on": "jofotara_is_active",
                "length": 15,
                "description": "1-15 digit Activity Serial Number from JoFotara registration"
            },
            {
                "fieldname": "jofotara_column_break",
                "fieldtype": "Column Break",
                "insert_after": "jofotara_activity_serial"
            },
            {
                "fieldname": "jofotara_auto_submit",
                "label": "Auto Submit to JoFotara",
                "fieldtype": "Check",
                "insert_after": "jofotara_column_break",
                "depends_on": "jofotara_is_active",
                "default": 0,
                "description": "Enable auto submission to JoFotara"
            },
            {
                "fieldname": "is_jordan_sales_tax_registered",
                "label": "Registered for Jordanian Sales Tax",
                "fieldtype": "Check",
                "insert_after": "jofotara_auto_submit",
                "depends_on": "jofotara_is_active",
                "default": 0,
                "description": "if the company is registered for General Sales Tax with Jordan's Income and Sales Tax Department (ISTD). This setting determines the base category for Jofotara e-invoices."
            },
            {
                "fieldname": "current_icv_counter",
                "label": "Current ICV Counter",
                "fieldtype": "Data",
                "insert_after": "is_jordan_sales_tax_registered",
                "depends_on": "jofotara_is_active",
                "read_only": 1,
                "default": 0,
                "description": "Current Invoice Counter Value for sequential numbering"
            },
            {
                "fieldname": "jofotara_end_section",
                "fieldtype": "Section Break",
                "insert_after": "current_icv_counter"
            }
        ]
    }

    create_custom_fields(custom_fields)
