import frappe
import unittest
from frappe.test_runner import make_test_records_for_doctype


class TestJofotaraPayerType(unittest.TestCase):
	"""Test cases for Jofotara Payer Type logic implementation"""
	
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Create necessary test records
		try:
			make_test_records_for_doctype("Sales Invoice", "User")
		except:
			pass  # Test records may already exist
		
		# Create test companies
		cls.create_test_companies()
		cls.create_test_tax_templates()
	
	@classmethod
	def create_test_companies(cls):
		"""Create test companies for different scenarios"""
		# Non-registered Jordanian company
		if not frappe.db.exists("Company", "Test Jordan Non-Registered"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Jordan Non-Registered",
				"abbr": "TJNR",
				"country": "Jordan",
				"is_jordan_sales_tax_registered": 0,
				"default_currency": "JOD",
				"chart_of_accounts": "Standard"
			}).insert()
		
		# Registered Jordanian company
		if not frappe.db.exists("Company", "Test Jordan Registered"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Jordan Registered",
				"abbr": "TJR",
				"country": "Jordan",
				"is_jordan_sales_tax_registered": 1,
				"default_currency": "JOD",
				"chart_of_accounts": "Standard"
			}).insert()
		
		# Non-Jordanian company (should be ignored)
		if not frappe.db.exists("Company", "Test Non-Jordan"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "Test Non-Jordan",
				"abbr": "TNJ",
				"country": "United States",
				"is_jordan_sales_tax_registered": 0,
				"default_currency": "USD",
				"chart_of_accounts": "Standard"
			}).insert()
	
	@classmethod
	def create_test_tax_templates(cls):
		"""Create test tax templates for different scenarios"""
		# General tax template
		if not frappe.db.exists("Item Tax Template", "Test General Tax"):
			frappe.get_doc({
				"doctype": "Item Tax Template",
				"company": "Test Jordan Registered",
				"title": "Test General Tax",
				"is_jofotara_special_tax": 0,
				"taxes": [{
					"tax_type": "Sales",
					"tax_rate": 16.0
				}]
			}).insert()
		
		# Special tax template
		if not frappe.db.exists("Item Tax Template", "Test Special Tax"):
			frappe.get_doc({
				"doctype": "Item Tax Template",
				"company": "Test Jordan Registered",
				"title": "Test Special Tax",
				"is_jofotara_special_tax": 1,
				"taxes": [{
					"tax_type": "Sales",
					"tax_rate": 25.0
				}]
			}).insert()
	
	def test_scenario_1_non_registered_zero_tax(self):
		"""Test Scenario 1: Non-registered company with zero tax → Payer Type '1'"""
		# Create Sales Invoice for non-registered company with no taxes
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "Administrator",
			"company": "Test Jordan Non-Registered",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "Administrator",
				"qty": 1,
				"rate": 0.10,
			}]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is set to '1'
		self.assertEqual(si.jofotara_payer_type, '1', 
			"Non-registered company with zero tax should have Payer Type '1'")
	
	def test_scenario_2_non_registered_with_tax(self):
		"""Test Scenario 2: Non-registered company with tax → Validation error"""
		# Create Sales Invoice for non-registered company with taxes
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Jordan Non-Registered",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 0.1,
			}],
			"taxes": [{
				"charge_type": "On Net Total",
				"account_head": "_Test Sales Taxes and Charges - _TC",
				"description": "Test Tax",
				"rate": 16.0
			}]
		})
		
		# Should raise validation error
		with self.assertRaises(frappe.exceptions.ValidationError) as context:
			si.validate()
		
		# Verify error message
		self.assertIn("not registered for sales tax", str(context.exception),
			"Should show appropriate error message for non-registered company with taxes")
	
	def test_scenario_3_registered_general_items(self):
		"""Test Scenario 3: Registered company with general items → Payer Type '2'"""
		# Create Sales Invoice for registered company with general tax template
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Jordan Registered",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 0.1,
				"item_tax_template": "Test General Tax"
			}]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is set to '2'
		self.assertEqual(si.jofotara_payer_type, '2',
			"Registered company with general items should have Payer Type '2'")
	
	def test_scenario_4_registered_special_items(self):
		"""Test Scenario 4: Registered company with special items → Payer Type '3'"""
		# Create Sales Invoice for registered company with special tax template
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Jordan Registered",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 0.1,
				"item_tax_template": "Test Special Tax"
			}]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is set to '3'
		self.assertEqual(si.jofotara_payer_type, '3',
			"Registered company with special items should have Payer Type '3'")
	
	def test_scenario_5_registered_zero_rated_items(self):
		"""Test Scenario 5: Registered company with zero-rated items → Payer Type '2'"""
		# Create Sales Invoice for registered company with no tax template (zero-rated)
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Jordan Registered",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 0.1,
				# No item_tax_template = zero-rated
			}]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is set to '2' (General Sales)
		self.assertEqual(si.jofotara_payer_type, '2',
			"Registered company with zero-rated items should have Payer Type '2'")
	
	def test_non_jordanian_company_ignored(self):
		"""Test that non-Jordanian companies are ignored by the logic"""
		# Create Sales Invoice for non-Jordanian company
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Non-Jordan",
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 0.1,
			}]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is not set (should remain None/empty)
		self.assertIsNone(getattr(si, 'jofotara_payer_type', None),
			"Non-Jordanian companies should not have Payer Type set")
	
	def test_mixed_items_special_takes_precedence(self):
		"""Test that mixed items with special tax template results in Payer Type '3'"""
		# Create Sales Invoice with mixed items (general and special)
		si = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": "_Test Customer",
			"company": "Test Jordan Registered",
			"due_date": frappe.utils.today(),
			"items": [
				{
					"item_code": "_Test Item",
					"qty": 1,
					"rate": 0.1,
					"item_tax_template": "Test General Tax"
				},
				{
					"item_code": "_Test Item",
					"qty": 1,
					"rate": 0.1,
					"item_tax_template": "Test Special Tax"
				}
			]
		})
		
		# Trigger validation
		si.validate()
		
		# Verify Payer Type is set to '3' (Special Sales takes precedence)
		self.assertEqual(si.jofotara_payer_type, '3',
			"Mixed items with special tax should result in Payer Type '3'")
	
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
	
	@classmethod
	def tearDownClass(cls):
		"""Clean up test data"""
		# Delete test companies
		for company in ["Test Jordan Non-Registered", "Test Jordan Registered", "Test Non-Jordan"]:
			if frappe.db.exists("Company", company):
				frappe.delete_doc("Company", company, force=True)
		
		# Delete test tax templates
		for template in ["Test General Tax", "Test Special Tax"]:
			if frappe.db.exists("Item Tax Template", template):
				frappe.delete_doc("Item Tax Template", template, force=True)
		
		frappe.db.commit()
		super().tearDownClass()
