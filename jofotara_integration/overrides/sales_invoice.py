import frappe
from frappe import _


def validate(doc, method):
	"""
	Hook to automatically calculate Jofotara Payer Type based on company registration status and item tax templates.
	Also validates that unregistered companies cannot include items with special tax templates.
	
	Logic Flow:
	1. Pre-check: Verify company country is "Jordan"
	2. Fetch company registration status from Company master
	3. Branch 1 (Non-registered): Set Payer Type '1', validate no taxes and no special tax items
	4. Branch 2 (Registered): Check items for special tax, set Payer Type '2' or '3'
	
	Args:
		doc (Document): Sales Invoice document
		method (str): Document event method name
	"""
	# Pre-check: Only apply logic for Jordanian companies
	if not doc.company:
		return
		
	company_doc = frappe.get_doc("Company", doc.company)
	if company_doc.country != "Jordan":
		return
	
	# Fetch company registration status
	is_registered = getattr(company_doc, 'is_jordan_sales_tax_registered', 0)
	
	# Branch 1: Company is NOT registered for sales tax
	if not is_registered:
		doc.jofotara_payer_type = '1'
		
		# Validation: Non-registered companies cannot have tax charges
		if doc.total_taxes_and_charges > 0:
			frappe.throw(
				_("This company is not registered for sales tax. Invoices cannot include tax charges. Please remove all taxes to proceed."),
				title=_("Tax Registration Required")
			)
		
		# Enhanced validation for unregistered companies with special tax items
		# This validation MUST prevent saving if compliance violations exist
		# Only apply if JoFotara is enabled for this company
		jofotara_is_active = getattr(company_doc, 'jofotara_is_active', 0)
		if jofotara_is_active:
			from jofotara_integration.jofotara_integration.services.validation_service import validation_service
			validation_service.validate_unregistered_company_special_items(doc)
	
	# Branch 2: Company IS registered for sales tax
	else:
		# Check if any items have special tax templates
		has_special_items = False
		
		for item in doc.items:
			if item.item_tax_template:
				# Get the item tax template
				tax_template = frappe.get_doc("Item Tax Template", item.item_tax_template)
				if getattr(tax_template, 'is_jofotara_special_tax', 0):
					has_special_items = True
					break  # Break early for efficiency
		
		# Set Payer Type based on special items
		if has_special_items:
			doc.jofotara_payer_type = '3'  # Special Sales
		else:
			doc.jofotara_payer_type = '2'  # General Sales


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


def before_save(doc, method):
	"""
	Hook to reset e-invoicing custom fields for Credit Notes.
	
	When a Credit Note is created from an original invoice, ERPNext copies 
	all fields including custom e-invoicing fields. These need to be reset
	to default values for the new Credit Note.
	
	Args:
		doc (Document): Sales Invoice document
		method (str): Document event method name
	"""
	# Check if this is a Credit Note (is_return = 1)
	if getattr(doc, 'is_return', 0) == 1:
		# Reset e-invoicing custom fields to their default values
		if hasattr(doc, 'custom_einvoice_status'):
			doc.custom_einvoice_status = "Pending"
		
		if hasattr(doc, 'custom_invoice_qr_code'):
			doc.custom_invoice_qr_code = ""
		
		## if hasattr(doc, 'custom_einvoice_uuid'):
		## 	doc.custom_einvoice_uuid = ""
		## 
		## if hasattr(doc, 'custom_icv_counter'):
		## 	doc.custom_icv_counter = None


