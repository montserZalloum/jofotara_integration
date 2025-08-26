import frappe
from frappe import _
from frappe.utils import get_url
import json

from jofotara_integration.jofotara_integration.services.xml_generator import UBLXMLGenerator
from jofotara_integration.jofotara_integration.services.jofotara_client import JoFotaraClient


@frappe.whitelist()
def submit_invoice_to_jofotara(sales_invoice_name):
	"""
	Manual submission API endpoint for JoFotara e-invoice submission
	
	Args:
		sales_invoice_name (str): Name/ID of the Sales Invoice to submit
		
	Returns:
		dict: Response with status and details
	"""
	try:
		# Validate user permissions
		if not frappe.has_permission("Sales Invoice", "submit"):
			frappe.throw(_("Insufficient permissions to submit invoices"))
		
		# Get and validate Sales Invoice
		if not frappe.db.exists("Sales Invoice", sales_invoice_name):
			frappe.throw(_("Sales Invoice {0} not found").format(sales_invoice_name))
		
		invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
		
		# Check if invoice is submitted
		if invoice.docstatus != 1:
			frappe.throw(_("Only submitted invoices can be sent to JoFotara"))
		
		# Check if already accepted
		if invoice.get("custom_einvoice_status") == "Accepted":
			frappe.throw(_("Invoice has already been accepted by JoFotara"))
		
		# Check compliance status before manual submission
		from jofotara_integration.jofotara_integration.services.validation_service import check_invoice_compliance_status
		
		compliance_result = check_invoice_compliance_status(sales_invoice_name)
		if not compliance_result.get('is_compliant', False):
			frappe.throw(
				compliance_result.get('error_message', 'Compliance validation failed'),
				title=_("JoFotara Compliance Violation")
			)
		
		# Validate Company configuration and credentials (AC: 3, 4, 5)
		company_doc = frappe.get_doc("Company", invoice.company)
		_validate_company_configuration(company_doc)
		
		# Check for duplicate submissions (prevent multiple simultaneous submissions)
		job_name = f'jofotara_submission_{sales_invoice_name}'
		existing_jobs = frappe.get_all("RQ Job", 
			filters={"job_name": job_name, "status": ["in", ["queued", "started"]]})
		
		if existing_jobs:
			frappe.throw(_("Submission already in progress for this invoice"))
		
		# Enqueue background job for submission
		from jofotara_integration.api.background_jobs import enqueue_invoice_submission
		job = enqueue_invoice_submission(sales_invoice_name, invoice.company)
		
		return {
			"status": "queued",
			"message": _("Invoice submission has been queued for processing"),
			"job_id": job.id,
			"invoice": sales_invoice_name
		}
		
	except Exception as e:
		frappe.log_error(f"Manual submission failed for {sales_invoice_name}: {str(e)}")
		frappe.throw(_("Submission failed: {0}").format(str(e)))


def _validate_company_configuration(company_doc):
	"""
	Validate Company JoFotara configuration and credentials
	
	Args:
		company_doc (Document): Company document
		
	Raises:
		ValidationError: If configuration is invalid or credentials are missing
	"""
	# Check if JoFotara integration is active for this company (AC: 3)
	if not company_doc.get("jofotara_is_active"):
		frappe.throw(_("JoFotara integration is disabled for company {0}").format(company_doc.company_name))
	
	required_fields = ["jofotara_client_id", "jofotara_secret_key", "jofotara_activity_serial"]
	missing_fields = []
	
	for field in required_fields:
		if not company_doc.get(field):
			missing_fields.append(frappe.get_meta("Company").get_label(field))
	
	if missing_fields:
		frappe.throw(_("Missing JoFotara credentials: {0}").format(", ".join(missing_fields)))
	
	# Validate Activity Serial Number format
	activity_serial = company_doc.get("jofotara_activity_serial")
	if activity_serial:
		import re
		if not re.match(r'^\d{1,15}$', activity_serial):
			frappe.throw(_("Activity Serial Number must be 1-15 digits only"))


def _validate_company_credentials(company_doc):
	"""
	Legacy function - use _validate_company_configuration instead
	
	Args:
		company_doc (Document): Company document
		
	Raises:
		ValidationError: If credentials are missing or invalid
	"""
	return _validate_company_configuration(company_doc)


@frappe.whitelist()
def get_submission_status(sales_invoice_name):
	"""
	Get current submission status for an invoice
	
	Args:
		sales_invoice_name (str): Name/ID of the Sales Invoice
		
	Returns:
		dict: Current status information
	"""
	try:
		if not frappe.has_permission("Sales Invoice", "read"):
			frappe.throw(_("Insufficient permissions"))
		
		invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
		
		# Check for active job
		job_name = f'jofotara_submission_{sales_invoice_name}'
		active_jobs = frappe.get_all("RQ Job", 
			filters={"job_name": job_name, "status": ["in", ["queued", "started"]]},
			fields=["name", "status", "creation"])
		
		return {
			"invoice": sales_invoice_name,
			"einvoice_status": invoice.get("custom_einvoice_status", "Pending"),
			"einvoice_uuid": invoice.get("custom_einvoice_uuid"),
			"qr_code": invoice.get("custom_invoice_qr_code"),
			"has_active_job": len(active_jobs) > 0,
			"active_jobs": active_jobs
		}
		
	except Exception as e:
		frappe.log_error(f"Status check failed for {sales_invoice_name}: {str(e)}")
		frappe.throw(_("Status check failed: {0}").format(str(e)))


 