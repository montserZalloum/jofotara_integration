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
		
		
	except Exception as e:
		# Log the error to database instead of file to avoid permission issues
		try:
			frappe.db.sql("""
				INSERT INTO `tabError Log` (`name`, `title`, `error`, `creation`, `owner`)
				VALUES (%(name)s, %(title)s, %(error)s, NOW(), 'Administrator')
			""", {
				'name': frappe.generate_hash(length=10),
				'title': "JoFotara Auto-Submission Error",
				'error': f"Auto-submission failed for Sales Invoice {doc.name}: {str(e)}"
			})
			frappe.db.commit()
		except Exception:
			# If logging fails, continue anyway
			pass
		
		# Show a non-blocking message to the user
		frappe.msgprint(
			_("Sales Invoice submitted successfully, but auto-submission to JoFotara failed. You can submit manually from the invoice."),
			title=_("Auto-Submission Failed"),
			indicator="orange"
		)


