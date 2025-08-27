import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def add_custom_fields():
    """
    Add custom ICV counter field to Sales Invoice
    """
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "jofotara_sales_invoice_section",
                "label": "JoFotara E-Invoice Details",
                "fieldtype": "Section Break",
                "insert_after": "edit_printing_settings",
                "collapsible": 0
            },
            {
                "fieldname": "custom_einvoice_status",
                "label": "E-Invoice Status",
                "fieldtype": "Select",
                "options": "Pending\nSubmitted\nAccepted\nRejected",
                "default": "Pending",
                "read_only": 1,
                "insert_after": "jofotara_sales_invoice_section",
                "allow_on_submit": 1,
                "in_list_view": 1,
                "in_standard_filter": 1
            },
            {
                "fieldname": "custom_einvoice_uuid",
                "label": "E-Invoice UUID",
                "fieldtype": "Data",
                "read_only": 1,
                "insert_after": "custom_einvoice_status",
                "allow_on_submit": 1,
                "in_list_view": 0
            },
            {
                "fieldname": "custom_invoice_qr_code",
                "label": "E-Invoice QR Code Image",
                "fieldtype": "Long Text",
                "read_only": 1,
                "hidden": 1,
                "insert_after": "custom_einvoice_uuid",
                "allow_on_submit": 1,
                "in_list_view": 0
            },
            {
                "fieldname": "custom_icv_counter",
                "label": "JoFotara ICV",
                "fieldtype": "Int",
                "insert_after": "custom_invoice_qr_code",
                "read_only": 1,
                "no_copy": 1,
                "description": "Invoice Counter Value assigned by JoFotara integration",
                "depends_on": "eval:doc.company",
                "precision": "",
                "options": "",
                "reqd": 0,
                "default": ""
            },
            {
                "fieldname": "jofotara_payer_type",
                "label": "Jofotara Payer Type",
                "fieldtype": "Data",
                "insert_after": "custom_icv_counter",
                "read_only": 1,
                "no_copy": 1,
                "description": "This field will be populated automatically with '1', '2', or '3'.",
                "default": ""
            },
        ]
    }

    create_custom_fields(custom_fields)
