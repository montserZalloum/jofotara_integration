import frappe
from frappe import _
import json

from jofotara_integration.jofotara_integration.services.xml_generator import UBLXMLGenerator
from jofotara_integration.jofotara_integration.services.jofotara_client import JoFotaraClient
from jofotara_integration.jofotara_integration.utils.jofotara_logger import log_api_submission
from jofotara_integration.api.icv_counter import icv_counter_manager


def should_auto_submit_invoice(company_name):
	"""
	Check if automatic submission is enabled for a company (AC: 4)
	
	Args:
		company_name (str): Company name
		
	Returns:
		bool: True if auto submission is enabled, False otherwise
	"""
	try:
		company_doc = frappe.get_doc("Company", company_name)
		
		# Company must be active and auto-submit must be enabled
		is_active = bool(company_doc.get("jofotara_is_active"))
		auto_submit = bool(company_doc.get("jofotara_auto_submit"))
		
		return is_active and auto_submit
	except Exception:
		return False


def enqueue_automatic_submission(sales_invoice_name, company_name):
	"""
	Enqueue automatic invoice submission if enabled for company (AC: 4)
	
	Args:
		sales_invoice_name (str): Name/ID of the Sales Invoice
		company_name (str): Company name
		
	Returns:
		Job|None: Frappe job object if queued, None if not eligible
	"""
	# Check if automatic submission is enabled for this company
	if not should_auto_submit_invoice(company_name):
		return None
	
	return enqueue_invoice_submission(sales_invoice_name, company_name)


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
		# Validate company authentication credentials and configuration
		company_doc = frappe.get_doc("Company", company)
		_validate_company_configuration(company_doc)
		
		# Get invoice document
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		
		# Initialize services with company config
		xml_generator = UBLXMLGenerator()
		client = JoFotaraClient()
		
		# Ensure ICV is assigned (reserve if missing) and get value
		icv_counter = invoice_doc.get("custom_icv_counter") or 0
		if not icv_counter or icv_counter <= 0:
			icv_counter = icv_counter_manager.reserve_icv_for_invoice(company, sales_invoice)
			# Reload invoice to reflect updated field
			invoice_doc.reload()

		# Build invoice data AFTER ICV is ensured, so custom_icv_counter is present
		invoice_data = invoice_doc.as_dict()
		invoice_data["custom_icv_counter"] = icv_counter
		
		# Generate XML and get both content and UUID
		xml_result = xml_generator.generate_xml(invoice_data, icv_counter=icv_counter)
		xml_content = xml_result['xml_content']
		generated_uuid = xml_result['uuid']
		
		# Prepare company config dictionary for API client
		client_id = company_doc.get("jofotara_client_id")
		# Use get_password() for Password field types to get decrypted value
		secret_key = company_doc.get_password("jofotara_secret_key")
		activity_serial = company_doc.get("jofotara_activity_serial")
		
		company_config = {
			'client_id': client_id.strip() if client_id else None,
			'secret_key': secret_key.strip() if secret_key else None,
			'activity_serial': activity_serial.strip() if activity_serial else None
		}
		
		# Prepare invoice data with XML content for API client
		invoice_with_xml = {
			'xml_content': xml_content,
			'invoice_name': invoice_doc.name,
			'company': invoice_doc.company
		}
		
		# Prepare request payload for logging
		request_payload = {
			'endpoint': client.api_endpoint,
			'method': 'POST',
			'headers': {
				'Client-Id': client_id[:8] + '...' if client_id else None,
				'Secret-Key': '***HIDDEN***',
				'Content-Type': 'application/json'
			},
			'invoice_name': invoice_doc.name,
			'company': invoice_doc.company,
            'xml_length': len(xml_content),
            'icv_value': icv_counter
		}
		
		# Submit to JoFotara API
		response = client.submit_invoice(invoice_with_xml, company_config)
		
		# Log the API submission (include icv_value in payload)
		log_api_submission(sales_invoice, request_payload, response, response.get('success', False))
		
		# Check if API call was successful
		if response.get('success'):
			# Update invoice status and store response data for successful submission
			update_data = {
				'custom_einvoice_status': 'Accepted',
				'custom_einvoice_uuid': generated_uuid  # Use the generated UUID from XML, not response
			}
			
			# Store QR code if present in response
			if response.get('qr_code'):
				update_data['custom_einvoice_qr_code'] = response.get('qr_code')
			
			frappe.db.set_value('Sales Invoice', sales_invoice, update_data)
			frappe.db.commit()
			
			# Send success notification
			_send_completion_notification(sales_invoice, 'success', {
				'status': 'Accepted',
				'uuid': generated_uuid,  # Use the generated UUID from XML, not response
				'message': _("Invoice successfully submitted to JoFotara")
			})
		else:
			# API call failed, raise exception to trigger error handling
			error_msg = response.get('error', 'Unknown API error')
			status_code = response.get('status_code', 'Unknown')
			raise Exception(f"JoFotara API Error {status_code}: {error_msg}")
		
	except Exception as e:
		error_message = str(e)
		
		# Handle submission error and update status
		update_data = {
			'custom_einvoice_status': 'Rejected'
		}
		
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


def _validate_company_configuration(company_doc):
	"""
	Validate Company JoFotara configuration and credentials
	
	Args:
		company_doc (Document): Company document
		
	Raises:
		Exception: If configuration is invalid or credentials are missing
	"""
	# Check if JoFotara integration is active for this company (AC: 3)
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


def _validate_company_credentials(company_doc):
	"""
	Legacy function - use _validate_company_configuration instead
	
	Args:
		company_doc (Document): Company document
		
	Raises:
		Exception: If credentials are missing or invalid
	"""
	return _validate_company_configuration(company_doc)


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