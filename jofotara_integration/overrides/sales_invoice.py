import frappe
from frappe import _


def on_submit(doc, method):
	"""
	Hook to assign ICV counter and automatically submit eligible invoices to JoFotara
	
	Args:
		doc (Document): Sales Invoice document
		method (str): Document event method name
	"""
	try:
		# Only proceed if this is a newly submitted invoice
		if doc.docstatus != 1:
			return
		
		# Step 1: Assign ICV counter at submission time (AC: 6)
		_assign_icv_counter(doc)
		
		# Step 2: Check if the company has automatic submission enabled (AC: 4)
		from jofotara_integration.api.background_jobs import enqueue_automatic_submission
		
		# Attempt to enqueue automatic submission
		job = enqueue_automatic_submission(doc.name, doc.company)
		
		if job:
			frappe.msgprint(
				_("Invoice automatically queued for JoFotara submission"),
				title=_("Auto-Submission Enabled"),
				indicator="blue"
			)
		
	except Exception as e:
		# Log the error but don't prevent invoice submission
		frappe.log_error(
			f"Auto-submission failed for Sales Invoice {doc.name}: {str(e)}",
			"JoFotara Auto-Submission Error"
		)
		
		# Show a non-blocking message to the user
		frappe.msgprint(
			_("Sales Invoice submitted successfully, but auto-submission to JoFotara failed. You can submit manually from the invoice."),
			title=_("Auto-Submission Failed"),
			indicator="orange"
		)


def _assign_icv_counter(doc):
	"""
	Assign ICV counter to Sales Invoice at submission time
	
	Args:
		doc (Document): Sales Invoice document
	"""
	try:
		# Check if company has JoFotara integration enabled
		company_doc = frappe.get_doc("Company", doc.company)
		
		if not company_doc.get("jofotara_is_active"):
			# Skip ICV assignment if JoFotara is not active for this company
			return
		
		# Skip if ICV is already assigned (prevent duplicate assignment)
		if doc.get("custom_icv_counter") and doc.get("custom_icv_counter") > 0:
			return
		
		# Get next ICV from counter management service
		from jofotara_integration.api.icv_counter import icv_counter_manager
		
		next_icv = icv_counter_manager.get_next_icv(doc.company)
		
		# Assign ICV to the invoice
		frappe.db.set_value(
			"Sales Invoice", 
			doc.name, 
			"custom_icv_counter", 
			next_icv,
			update_modified=False  # Don't update modified timestamp
		)
		
		# Update the document object for immediate access
		doc.custom_icv_counter = next_icv
		
		frappe.logger().info(f"ICV Assignment: Invoice {doc.name} assigned ICV {next_icv}")
		
	except Exception as e:
		# Log error and re-raise to prevent invoice submission with invalid ICV state
		frappe.log_error(
			f"ICV Counter Assignment Error for Sales Invoice {doc.name}: {str(e)}",
			"ICV Counter Assignment Error"
		)
		
		# Re-raise to prevent submission if ICV assignment fails
		frappe.throw(_("Failed to assign Invoice Counter Value: {0}").format(str(e)))
