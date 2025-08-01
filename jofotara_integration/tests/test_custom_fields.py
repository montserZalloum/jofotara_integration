import frappe
import unittest


class TestCustomFields(unittest.TestCase):
	"""Test cases for Sales Invoice custom fields for e-invoicing"""
	
	def test_custom_fields_exist_in_meta(self):
		"""Test that all required custom fields exist in Sales Invoice meta"""
		meta = frappe.get_meta("Sales Invoice")
		
		# Test field existence in meta
		required_fields = ['e_invoice_status', 'e_invoice_uuid', 'e_invoice_qr_code', 'icv_counter']
		
		for fieldname in required_fields:
			field = meta.get_field(fieldname)
			self.assertIsNotNone(field, f"Field {fieldname} not found in Sales Invoice meta")
	
	def test_e_invoice_status_default_value(self):
		"""Test E-Invoice Status defaults to 'Pending'"""
		meta = frappe.get_meta("Sales Invoice")
		status_field = meta.get_field("e_invoice_status")
		self.assertEqual(status_field.default, 'Pending')
	
	def test_e_invoice_status_options(self):
		"""Test E-Invoice Status has correct options"""
		# Get field meta to check options
		meta = frappe.get_meta("Sales Invoice")
		status_field = meta.get_field("e_invoice_status")
		
		self.assertIsNotNone(status_field)
		self.assertEqual(status_field.fieldtype, "Select")
		
		expected_options = ["Pending", "Submitted", "Accepted", "Rejected"]
		actual_options = [opt.strip() for opt in status_field.options.split('\n') if opt.strip()]
		self.assertEqual(actual_options, expected_options)
	
	def test_fields_are_readonly(self):
		"""Test that all e-invoicing fields are read-only"""
		meta = frappe.get_meta("Sales Invoice")
		
		readonly_fields = ["e_invoice_status", "e_invoice_uuid", "e_invoice_qr_code", "icv_counter"]
		
		for fieldname in readonly_fields:
			field = meta.get_field(fieldname)
			self.assertIsNotNone(field, f"Field {fieldname} not found")
			self.assertEqual(field.read_only, 1, f"Field {fieldname} is not read-only")
	
	def test_field_types(self):
		"""Test that fields have correct data types"""
		meta = frappe.get_meta("Sales Invoice")
		
		field_types = {
			"e_invoice_status": "Select",
			"e_invoice_uuid": "Data", 
			"e_invoice_qr_code": "Long Text",
			"icv_counter": "Int"
		}
		
		for fieldname, expected_type in field_types.items():
			field = meta.get_field(fieldname)
			self.assertIsNotNone(field, f"Field {fieldname} not found")
			self.assertEqual(field.fieldtype, expected_type, f"Field {fieldname} has wrong type")
	
	def test_service_field_access_capability(self):
		"""Test that custom fields are accessible for service integration"""
		meta = frappe.get_meta("Sales Invoice")
		
		# Verify all fields exist and are properly configured for service access
		required_fields = ['e_invoice_status', 'e_invoice_uuid', 'e_invoice_qr_code', 'icv_counter']
		
		for fieldname in required_fields:
			field = meta.get_field(fieldname)
			self.assertIsNotNone(field, f"Field {fieldname} must exist for service access")
			# Fields should allow updates on submit for service integration
			self.assertEqual(field.allow_on_submit, 1, f"Field {fieldname} must allow updates on submit")
	
	def test_hooks_configuration(self):
		"""Test that custom fields are properly configured in hooks"""
		from jofotara_integration.hooks import custom_fields
		
		# Test hooks configuration exists
		self.assertIn("Sales Invoice", custom_fields)
		sales_invoice_fields = custom_fields["Sales Invoice"]
		
		# Test all required fields are in hooks
		field_names = [field["fieldname"] for field in sales_invoice_fields]
		required_fields = ['e_invoice_status', 'e_invoice_uuid', 'e_invoice_qr_code', 'icv_counter']
		
		for fieldname in required_fields:
			self.assertIn(fieldname, field_names, f"Field {fieldname} missing from hooks configuration")
	
	def test_field_positioning(self):
		"""Test that fields are positioned correctly in form"""
		meta = frappe.get_meta("Sales Invoice")
		
		# Check that e_invoice_status comes after status field
		status_field = meta.get_field("e_invoice_status")
		self.assertEqual(status_field.insert_after, "status")
		
		# Check field ordering
		uuid_field = meta.get_field("e_invoice_uuid")
		self.assertEqual(uuid_field.insert_after, "e_invoice_status")
		
		qr_field = meta.get_field("e_invoice_qr_code")
		self.assertEqual(qr_field.insert_after, "e_invoice_uuid")
		
		icv_field = meta.get_field("icv_counter")
		self.assertEqual(icv_field.insert_after, "e_invoice_qr_code")


def suite():
	"""Return test suite"""
	test_suite = unittest.TestSuite()
	test_suite.addTest(unittest.makeSuite(TestCustomFields))
	return test_suite


if __name__ == "__main__":
	unittest.main() 