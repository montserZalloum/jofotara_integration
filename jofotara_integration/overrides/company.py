import re
import frappe
from frappe import _
from erpnext.setup.doctype.company.company import Company


class CompanyOverride(Company):
	def validate(self):
		super().validate()
		self.validate_activity_serial_number()
	
	def validate_activity_serial_number(self):
		"""Validate Activity Serial Number format: 1-15 digits only"""
		if self.get("jofotara_activity_serial"):
			if not re.match(r'^\d{1,15}$', self.jofotara_activity_serial):
				frappe.throw(_("Activity Serial Number must be 1-15 digits only")) 