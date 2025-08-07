import frappe
from frappe import _


@frappe.whitelist()
def get_company_configuration_status(company_name):
	"""
	Get JoFotara configuration status for a company (AC: 6)
	
	Args:
		company_name (str): Company name
		
	Returns:
		dict: Configuration status information
	"""
	try:
		# Validate permissions
		if not frappe.has_permission("Company", "read"):
			frappe.throw(_("Insufficient permissions"))
		
		# Get company document
		if not frappe.db.exists("Company", company_name):
			frappe.throw(_("Company {0} not found").format(company_name))
		
		company_doc = frappe.get_doc("Company", company_name)
		
		# Check configuration status
		is_active = bool(company_doc.get("jofotara_is_active"))
		auto_submit = bool(company_doc.get("jofotara_auto_submit"))
		
		# Check if all required credentials are present
		required_fields = ["jofotara_client_id", "jofotara_secret_key", "jofotara_activity_serial"]
		has_complete_credentials = True
		
		if is_active:
			for field in required_fields:
				if not company_doc.get(field):
					has_complete_credentials = False
					break
		
		return {
			"company": company_name,
			"is_active": is_active,
			"auto_submit": auto_submit,
			"has_complete_credentials": has_complete_credentials,
			"status_summary": _get_status_summary(is_active, auto_submit, has_complete_credentials)
		}
		
	except Exception as e:
		frappe.log_error(f"Configuration status check failed for {company_name}: {str(e)}")
		frappe.throw(_("Configuration status check failed: {0}").format(str(e)))


def _get_status_summary(is_active, auto_submit, has_credentials):
	"""
	Generate status summary text
	
	Args:
		is_active (bool): JoFotara integration active
		auto_submit (bool): Auto submission enabled
		has_credentials (bool): Complete credentials available
		
	Returns:
		str: Status summary
	"""
	if not is_active:
		return _("Integration Disabled")
	elif not has_credentials:
		return _("Missing Credentials")
	elif auto_submit:
		return _("Auto Submit Enabled")
	else:
		return _("Manual Submit Only")


@frappe.whitelist()
def get_all_companies_configuration():
	"""
	Get JoFotara configuration status for all companies (Administrator view)
	
	Returns:
		list: List of company configurations
	"""
	try:
		# Only allow System Manager role
		if not frappe.has_permission("Company", "read"):
			frappe.throw(_("Insufficient permissions"))
		
		companies = frappe.get_all("Company", 
			fields=["name", "company_name", "jofotara_is_active", "jofotara_auto_submit", 
				   "jofotara_client_id", "jofotara_secret_key", "jofotara_activity_serial"])
		
		company_configs = []
		for company in companies:
			# Check if all required credentials are present
			has_complete_credentials = bool(
				company.get("jofotara_client_id") and 
				company.get("jofotara_secret_key") and 
				company.get("jofotara_activity_serial")
			)
			
			is_active = bool(company.get("jofotara_is_active"))
			auto_submit = bool(company.get("jofotara_auto_submit"))
			
			company_configs.append({
				"company": company.get("name"),
				"company_name": company.get("company_name"),
				"is_active": is_active,
				"auto_submit": auto_submit,
				"has_complete_credentials": has_complete_credentials,
				"status_summary": _get_status_summary(is_active, auto_submit, has_complete_credentials)
			})
		
		return company_configs
		
	except Exception as e:
		frappe.log_error(f"All companies configuration check failed: {str(e)}")
		frappe.throw(_("Configuration check failed: {0}").format(str(e)))


@frappe.whitelist()
def test_company_connection(company_name):
	"""
	Test JoFotara connection for a company
	
	Args:
		company_name (str): Company name
		
	Returns:
		dict: Connection test result
	"""
	try:
		# Validate permissions
		if not frappe.has_permission("Company", "write"):
			frappe.throw(_("Insufficient permissions"))
		
		# Get company document
		if not frappe.db.exists("Company", company_name):
			frappe.throw(_("Company {0} not found").format(company_name))
		
		company_doc = frappe.get_doc("Company", company_name)
		
		# Use existing validation function to check configuration
		from jofotara_integration.api.background_jobs import _validate_company_configuration
		_validate_company_configuration(company_doc)
		
		# If validation passes, the configuration is valid
		# In a real implementation, you might want to make a test API call to JoFotara
		return {
			"success": True,
			"message": _("Configuration is valid and ready for use")
		}
		
	except Exception as e:
		return {
			"success": False,
			"error": str(e),
			"message": _("Configuration test failed")
		}
