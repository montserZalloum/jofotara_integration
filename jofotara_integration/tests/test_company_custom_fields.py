import unittest
import frappe
from frappe.tests.utils import FrappeTestCase


class TestCompanyCustomFields(FrappeTestCase):
	def setUp(self):
		"""Set up test data"""
		# Create or get test company
		if not frappe.db.exists("Company", "_Test Company JoFotara"):
			self.test_company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Company JoFotara",
				"abbr": "TCJ",
				"default_currency": "USD"
			}).insert()
		else:
			self.test_company = frappe.get_doc("Company", "_Test Company JoFotara")

	def tearDown(self):
		"""Clean up test data"""
		if frappe.db.exists("Company", "_Test Company JoFotara"):
			frappe.delete_doc("Company", "_Test Company JoFotara")

	def test_company_custom_fields_exist(self):
		"""Test that Company custom fields are properly created"""
		company = self.test_company
		
		# Verify custom fields exist and have correct properties
		self.assertTrue(hasattr(company, 'jofotara_is_active'))
		self.assertTrue(hasattr(company, 'jofotara_client_id'))
		self.assertTrue(hasattr(company, 'jofotara_secret_key'))
		self.assertTrue(hasattr(company, 'jofotara_activity_serial'))
		self.assertTrue(hasattr(company, 'current_icv_counter'))

	def test_activity_serial_number_validation_valid(self):
		"""Test Activity Serial Number validation with valid values"""
		company = self.test_company
		
		# Test valid Activity Serial Numbers (1-15 digits)
		valid_serials = ["1", "123", "123456789", "123456789012345"]
		
		for serial in valid_serials:
			company.jofotara_activity_serial = serial
			try:
				company.save()  # Should not raise error
			except Exception as e:
				self.fail(f"Valid serial {serial} should not raise error: {str(e)}")

	def test_activity_serial_number_validation_invalid(self):
		"""Test Activity Serial Number validation with invalid values"""
		company = self.test_company
		
		# Test invalid Activity Serial Numbers
		invalid_serials = [
			"",  # Empty
			"abc123",  # Contains letters
			"123abc",  # Contains letters
			"123-456",  # Contains hyphen
			"1234567890123456",  # Too long (16 digits)
			"12.34",  # Contains decimal
		]
		
		for serial in invalid_serials:
			company.jofotara_activity_serial = serial
			with self.assertRaises(frappe.ValidationError):
				company.save()

	def test_jofotara_integration_enable_disable(self):
		"""Test JoFotara integration enable/disable functionality"""
		company = self.test_company
		
		# Test default state
		self.assertEqual(company.jofotara_is_active, 0)
		
		# Test enabling integration
		company.jofotara_is_active = 1
		company.jofotara_client_id = "test_client_id"
		company.jofotara_secret_key = "test_secret_key"
		company.jofotara_activity_serial = "123456789"
		company.save()
		
		# Verify fields were saved
		company.reload()
		self.assertEqual(company.jofotara_is_active, 1)
		self.assertEqual(company.jofotara_client_id, "test_client_id")
		self.assertEqual(company.jofotara_activity_serial, "123456789")

	def test_current_icv_counter_default(self):
		"""Test Current ICV Counter field default value"""
		company = self.test_company
		
		# Test default value
		self.assertEqual(company.current_icv_counter, 0)


if __name__ == '__main__':
	unittest.main() 