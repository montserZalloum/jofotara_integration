import frappe
from frappe import _
import json

# Temporarily commenting out services for testing
# from jofotara_integration.services.xml_generator import UBLXMLGenerator
# from jofotara_integration.services.jofotara_client import JoFotaraClient


def enqueue_invoice_submission(sales_invoice_name, company_name):
	"""
	Enqueue invoice submission job for background processing
	
	Args:
		sales_invoice_name (str): Name/ID of the Sales Invoice
		company_name (str): Company name for authentication
		
	Returns:
		Job: Frappe job object
	"""
	job_name = f'jofotara_submission_{sales_invoice_name}'
	
	# Enqueue job with 60-second timeout (30s API + 30s buffer)
	job = frappe.enqueue(
		method='jofotara_integration.api.background_jobs.process_invoice_submission',
		queue='long',  # Use long queue for 30+ second operations
		timeout=60,    # 30s API + 30s buffer
		job_name=job_name,
		sales_invoice=sales_invoice_name,
		company=company_name,
		is_async=True
	)
	
	# Update invoice status to indicate submission started
	frappe.db.set_value('Sales Invoice', sales_invoice_name, 
		'custom_einvoice_status', 'Submitted')
	frappe.db.commit()
	
	frappe.publish_realtime(
		event='jofotara_submission_queued',
		message={
			'invoice': sales_invoice_name,
			'status': 'queued',
			'job_id': job.id
		},
		user=frappe.session.user
	)
	
	return job


def process_invoice_submission(sales_invoice, company):
	"""
	Background job processor for invoice submissions
	
	Args:
		sales_invoice (str): Sales Invoice name/ID
		company (str): Company name
	"""
	try:
		frappe.log_info(f"Starting JoFotara submission for {sales_invoice}")
		
		# Validate company authentication credentials
		company_doc = frappe.get_doc("Company", company)
		_validate_company_credentials(company_doc)
		
		# Get invoice document
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		
		# TEMPORARY: Mock the services for testing
		frappe.log_info("MOCK: Would generate XML and submit to JoFotara")
		
		# Mock response for testing
		response = {
			'uuid': f'mock-uuid-{sales_invoice}',
			'qr_code': f'mock-qr-code-{sales_invoice}'
		}
		
		# Update invoice status and store response data
		update_data = {
			'custom_einvoice_status': 'Accepted',
		}
		
		# Store UUID if present in response
		if response.get('uuid'):
			update_data['custom_einvoice_uuid'] = response.get('uuid')
		
		# Store QR code if present in response
		if response.get('qr_code'):
			update_data['custom_einvoice_qr_code_text'] = response.get('qr_code')
		
		frappe.db.set_value('Sales Invoice', sales_invoice, update_data)
		frappe.db.commit()
		
		# Send success notification
		_send_completion_notification(sales_invoice, 'success', {
			'status': 'Accepted',
			'uuid': response.get('uuid'),
			'message': _("Invoice successfully submitted to JoFotara")
		})
		
		frappe.log_info(f"JoFotara submission completed successfully for {sales_invoice}")
		
	except Exception as e:
		error_message = str(e)
		frappe.log_error(f"JoFotara submission failed for {sales_invoice}: {error_message}")
		
		# Handle submission error and update status
		update_data = {
			'custom_einvoice_status': 'Rejected'
		}
		
		# Store error details if there's a custom field for it
		# (This would be added in future iteration if needed)
		
		frappe.db.set_value('Sales Invoice', sales_invoice, update_data)
		frappe.db.commit()
		
		# Send error notification
		_send_completion_notification(sales_invoice, 'error', {
			'status': 'Rejected',
			'error': error_message,
			'message': _("Invoice submission to JoFotara failed: {0}").format(error_message)
		})
		
		# Re-raise the exception to mark job as failed
		raise


def _validate_company_credentials(company_doc):
	"""
	Validate Company JoFotara authentication credentials
	
	Args:
		company_doc (Document): Company document
		
	Raises:
		Exception: If credentials are missing or invalid
	"""
	if not company_doc.get("jofotara_is_active"):
		raise Exception(f"JoFotara integration is disabled for company {company_doc.company_name}")
	
	required_fields = ["jofotara_client_id", "jofotara_secret_key", "jofotara_activity_serial"]
	missing_fields = []
	
	for field in required_fields:
		if not company_doc.get(field):
			field_label = frappe.get_meta("Company").get_label(field) or field
			missing_fields.append(field_label)
	
	if missing_fields:
		raise Exception(f"Missing JoFotara credentials: {', '.join(missing_fields)}")
	
	# Validate Activity Serial Number format
	activity_serial = company_doc.get("jofotara_activity_serial")
	if activity_serial:
		import re
		if not re.match(r'^\d{1,15}$', activity_serial):
			raise Exception("Activity Serial Number must be 1-15 digits only")


def _send_completion_notification(sales_invoice, notification_type, details):
	"""
	Send real-time notification about job completion
	
	Args:
		sales_invoice (str): Sales Invoice name
		notification_type (str): 'success' or 'error'
		details (dict): Notification details
	"""
	event = f'jofotara_submission_{notification_type}'
	
	message = {
		'invoice': sales_invoice,
		'type': notification_type,
		**details
	}
	
	# Send to all users with access to the invoice
	frappe.publish_realtime(
		event=event,
		message=message,
		doctype='Sales Invoice',
		docname=sales_invoice
	)


@frappe.whitelist()
def retry_failed_submission(sales_invoice_name):
	"""
	Retry a failed submission
	
	Args:
		sales_invoice_name (str): Sales Invoice name
		
	Returns:
		dict: Response with status
	"""
	try:
		if not frappe.has_permission("Sales Invoice", "submit"):
			frappe.throw(_("Insufficient permissions"))
		
		invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
		
		# Check if it's actually in a failed state
		if invoice.get("custom_einvoice_status") not in ["Rejected", "Pending"]:
			frappe.throw(_("Invoice is not in a state that can be retried"))
		
		# Re-queue the submission
		from jofotara_integration.api.submission import submit_invoice_to_jofotara
		return submit_invoice_to_jofotara(sales_invoice_name)
		
	except Exception as e:
		frappe.log_error(f"Retry submission failed for {sales_invoice_name}: {str(e)}")
		frappe.throw(_("Retry failed: {0}").format(str(e))) 