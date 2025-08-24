import frappe
import unittest


class TestJofotaraPayerTypeSimple(unittest.TestCase):
	"""Simplified test cases for Jofotara Payer Type logic implementation"""
	
	def test_field_exists_in_meta(self):
		"""Test that jofotara_payer_type field exists in Sales Invoice meta"""
		meta = frappe.get_meta("Sales Invoice")
		field = meta.get_field("jofotara_payer_type")
		
		self.assertIsNotNone(field, "jofotara_payer_type field should exist in Sales Invoice meta")
		self.assertEqual(field.fieldtype, "Data", "jofotara_payer_type should be Data type")
		self.assertEqual(field.read_only, 1, "jofotara_payer_type should be read-only")
	
	def test_company_field_exists(self):
		"""Test that is_jordan_sales_tax_registered field exists in Company meta"""
		meta = frappe.get_meta("Company")
		field = meta.get_field("is_jordan_sales_tax_registered")
		
		self.assertIsNotNone(field, "is_jordan_sales_tax_registered field should exist in Company meta")
		self.assertEqual(field.fieldtype, "Check", "is_jordan_sales_tax_registered should be Check type")
	
	def test_tax_template_field_exists(self):
		"""Test that is_jofotara_special_tax field exists in Item Tax Template meta"""
		meta = frappe.get_meta("Item Tax Template")
		field = meta.get_field("is_jofotara_special_tax")
		
		self.assertIsNotNone(field, "is_jofotara_special_tax field should exist in Item Tax Template meta")
		self.assertEqual(field.fieldtype, "Check", "is_jofotara_special_tax should be Check type")
	
	def test_validate_function_exists(self):
		"""Test that the validate function is properly hooked"""
		from jofotara_integration.overrides.sales_invoice import validate
		
		self.assertTrue(callable(validate), "validate function should exist and be callable")
	
	def test_logic_branch_1_non_registered(self):
		"""Test Branch 1 logic: Non-registered company should get Payer Type '1'"""
		# Create a mock Sales Invoice document
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": "Test Company",
			"total_taxes_and_charges": 0
		})
		
		# Mock the company document
		company_doc = frappe._dict({
			"country": "Jordan",
			"is_jordan_sales_tax_registered": 0
		})
		
		# Mock frappe.get_doc to return our test company
		original_get_doc = frappe.get_doc
		frappe.get_doc = lambda doctype, name: company_doc if doctype == "Company" else original_get_doc(doctype, name)
		
		try:
			# Import and call the validate function
			from jofotara_integration.overrides.sales_invoice import validate
			validate(si, "validate")
			
			# Verify Payer Type is set to '1'
			self.assertEqual(si.jofotara_payer_type, '1', 
				"Non-registered company should have Payer Type '1'")
		finally:
			# Restore original function
			frappe.get_doc = original_get_doc
	
	def test_logic_branch_2_registered_general(self):
		"""Test Branch 2 logic: Registered company with general items should get Payer Type '2'"""
		# Create a mock Sales Invoice document
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": "Test Company",
			"items": [{
				"item_tax_template": "General Tax Template"
			}]
		})
		
		# Mock the company document
		company_doc = frappe._dict({
			"country": "Jordan",
			"is_jordan_sales_tax_registered": 1
		})
		
		# Mock the tax template document
		tax_template_doc = frappe._dict({
			"is_jofotara_special_tax": 0
		})
		
		# Mock frappe.get_doc to return our test documents
		original_get_doc = frappe.get_doc
		def mock_get_doc(doctype, name):
			if doctype == "Company":
				return company_doc
			elif doctype == "Item Tax Template":
				return tax_template_doc
			else:
				return original_get_doc(doctype, name)
		
		frappe.get_doc = mock_get_doc
		
		try:
			# Import and call the validate function
			from jofotara_integration.overrides.sales_invoice import validate
			validate(si, "validate")
			
			# Verify Payer Type is set to '2'
			self.assertEqual(si.jofotara_payer_type, '2', 
				"Registered company with general items should have Payer Type '2'")
		finally:
			# Restore original function
			frappe.get_doc = original_get_doc
	
	def test_logic_branch_2_registered_special(self):
		"""Test Branch 2 logic: Registered company with special items should get Payer Type '3'"""
		# Create a mock Sales Invoice document
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": "Test Company",
			"items": [{
				"item_tax_template": "Special Tax Template"
			}]
		})
		
		# Mock the company document
		company_doc = frappe._dict({
			"country": "Jordan",
			"is_jordan_sales_tax_registered": 1
		})
		
		# Mock the tax template document
		tax_template_doc = frappe._dict({
			"is_jofotara_special_tax": 1
		})
		
		# Mock frappe.get_doc to return our test documents
		original_get_doc = frappe.get_doc
		def mock_get_doc(doctype, name):
			if doctype == "Company":
				return company_doc
			elif doctype == "Item Tax Template":
				return tax_template_doc
			else:
				return original_get_doc(doctype, name)
		
		frappe.get_doc = mock_get_doc
		
		try:
			# Import and call the validate function
			from jofotara_integration.overrides.sales_invoice import validate
			validate(si, "validate")
			
			# Verify Payer Type is set to '3'
			self.assertEqual(si.jofotara_payer_type, '3', 
				"Registered company with special items should have Payer Type '3'")
		finally:
			# Restore original function
			frappe.get_doc = original_get_doc
	
	def test_non_jordanian_company_ignored(self):
		"""Test that non-Jordanian companies are ignored by the logic"""
		# Create a mock Sales Invoice document
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": "Test Company"
		})
		
		# Mock the company document
		company_doc = frappe._dict({
			"country": "United States",
			"is_jordan_sales_tax_registered": 0
		})
		
		# Mock frappe.get_doc to return our test company
		original_get_doc = frappe.get_doc
		frappe.get_doc = lambda doctype, name: company_doc if doctype == "Company" else original_get_doc(doctype, name)
		
		try:
			# Import and call the validate function
			from jofotara_integration.overrides.sales_invoice import validate
			validate(si, "validate")
			
			# Verify Payer Type is not set (should remain None/empty)
			self.assertIsNone(getattr(si, 'jofotara_payer_type', None),
				"Non-Jordanian companies should not have Payer Type set")
		finally:
			# Restore original function
			frappe.get_doc = original_get_doc
