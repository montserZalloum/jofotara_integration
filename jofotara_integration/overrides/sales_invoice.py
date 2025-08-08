import frappe
from frappe import _


def on_submit(doc, method):
	"""
    Hook to automatically submit eligible invoices to JoFotara.
    ICV is now assigned strictly at send-time inside the background job.
	
	Args:
		doc (Document): Sales Invoice document
		method (str): Document event method name
	"""
	try:
		# Only proceed if this is a newly submitted invoice
		if doc.docstatus != 1:
			return
		
        # Check if the company has automatic submission enabled (AC: 4)
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


