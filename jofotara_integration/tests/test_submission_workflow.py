import unittest
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import json

from jofotara_integration.api.submission import submit_invoice_to_jofotara, get_submission_status
from jofotara_integration.api.background_jobs import process_invoice_submission, enqueue_invoice_submission


class TestSubmissionWorkflow(FrappeTestCase):
	def setUp(self):
		"""Set up test data"""
		# Create test company with JoFotara credentials
		if not frappe.db.exists("Company", "_Test Company JoFotara"):
			self.test_company = frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Company JoFotara", 
				"abbr": "TCJ",
				"default_currency": "USD",
				"jofotara_is_active": 1,
				"jofotara_client_id": "test_client_id",
				"jofotara_secret_key": "test_secret_key",
				"jofotara_activity_serial": "123456789",
				"current_icv_counter": 0
			}).insert()
		else:
			self.test_company = frappe.get_doc("Company", "_Test Company JoFotara")
			# Update credentials
			self.test_company.update({
				"jofotara_is_active": 1,
				"jofotara_client_id": "test_client_id",
				"jofotara_secret_key": "test_secret_key",
				"jofotara_activity_serial": "123456789"
			})
			self.test_company.save()
		
		# Create test customer
		if not frappe.db.exists("Customer", "_Test Customer JoFotara"):
			self.test_customer = frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "_Test Customer JoFotara"
			}).insert()
		else:
			self.test_customer = frappe.get_doc("Customer", "_Test Customer JoFotara")
		
		# Create test item
		if not frappe.db.exists("Item", "_Test Item JoFotara"):
			self.test_item = frappe.get_doc({
				"doctype": "Item",
				"item_code": "_Test Item JoFotara",
				"item_name": "_Test Item JoFotara",
				"stock_uom": "Nos",
				"is_stock_item": 0
			}).insert()
		else:
			self.test_item = frappe.get_doc("Item", "_Test Item JoFotara")

	def tearDown(self):
		"""Clean up test data"""
		# Clean up in reverse order to avoid dependency issues
		frappe.db.rollback()

	def create_test_invoice(self, submit=True):
		"""Create a test Sales Invoice"""
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": self.test_company.name,
			"customer": self.test_customer.name,
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": self.test_item.item_code,
				"qty": 1,
				"rate": 100
			}],
			"custom_einvoice_status": "Pending"
		})
		invoice.insert()
		
		if submit:
			invoice.submit()
		
		return invoice

	def test_submit_invoice_api_endpoint_success(self):
		"""Test successful invoice submission via API endpoint"""
		invoice = self.create_test_invoice()
		
		with patch('jofotara_integration.api.background_jobs.enqueue_invoice_submission') as mock_enqueue:
			mock_job = MagicMock()
			mock_job.id = "test_job_123"
			mock_enqueue.return_value = mock_job
			
			result = submit_invoice_to_jofotara(invoice.name)
			
			self.assertEqual(result['status'], 'queued')
			self.assertEqual(result['invoice'], invoice.name)
			self.assertEqual(result['job_id'], "test_job_123")
			mock_enqueue.assert_called_once_with(invoice.name, invoice.company)

	def test_submit_invoice_permission_validation(self):
		"""Test permission validation for invoice submission"""
		invoice = self.create_test_invoice()
		
		with patch('frappe.has_permission', return_value=False):
			with self.assertRaises(frappe.ValidationError) as context:
				submit_invoice_to_jofotara(invoice.name)
			
			self.assertIn("Insufficient permissions", str(context.exception))

	def test_submit_invoice_already_accepted(self):
		"""Test submission of already accepted invoice"""
		invoice = self.create_test_invoice()
		frappe.db.set_value('Sales Invoice', invoice.name, 'custom_einvoice_status', 'Accepted')
		
		with self.assertRaises(frappe.ValidationError) as context:
			submit_invoice_to_jofotara(invoice.name)
		
		self.assertIn("already been accepted", str(context.exception))

	def test_submit_invoice_missing_company_credentials(self):
		"""Test submission with missing company credentials"""
		# Create company without credentials
		company_no_creds = frappe.get_doc({
			"doctype": "Company",
			"company_name": "_Test Company No Creds",
			"abbr": "TCNC",
			"default_currency": "USD",
			"jofotara_is_active": 0
		}).insert()
		
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"company": company_no_creds.name,
			"customer": self.test_customer.name,
			"due_date": frappe.utils.today(),
			"items": [{
				"item_code": self.test_item.item_code,
				"qty": 1,
				"rate": 100
			}]
		})
		invoice.insert()
		invoice.submit()
		
		with self.assertRaises(frappe.ValidationError) as context:
			submit_invoice_to_jofotara(invoice.name)
		
		self.assertIn("integration is disabled", str(context.exception))

	@patch('jofotara_integration.services.xml_generator.UBLXMLGenerator')
	@patch('jofotara_integration.services.jofotara_client.JoFotaraClient')
	def test_background_job_processing_success(self, mock_client_class, mock_generator_class):
		"""Test successful background job processing"""
		invoice = self.create_test_invoice()
		
		# Mock the services
		mock_generator = MagicMock()
		mock_generator.generate_invoice_xml.return_value = "<xml>test</xml>"
		mock_generator_class.return_value = mock_generator
		
		mock_client = MagicMock()
		mock_client.submit_invoice.return_value = {
			'uuid': 'test-uuid-123',
			'qr_code': 'test-qr-code'
		}
		mock_client_class.return_value = mock_client
		
		# Process the submission
		process_invoice_submission(invoice.name, invoice.company)
		
		# Verify services were called
		mock_generator.generate_invoice_xml.assert_called_once()
		mock_client.submit_invoice.assert_called_once()
		
		# Verify invoice was updated
		invoice.reload()
		self.assertEqual(invoice.custom_einvoice_status, "Accepted")
		self.assertEqual(invoice.custom_einvoice_uuid, "test-uuid-123")
		self.assertEqual(invoice.custom_einvoice_qr_code_text, "test-qr-code")

	@patch('jofotara_integration.services.xml_generator.UBLXMLGenerator')
	@patch('jofotara_integration.services.jofotara_client.JoFotaraClient')
	def test_background_job_processing_failure(self, mock_client_class, mock_generator_class):
		"""Test background job processing with API failure"""
		invoice = self.create_test_invoice()
		
		# Mock the services to raise an exception
		mock_generator = MagicMock()
		mock_generator.generate_invoice_xml.return_value = "<xml>test</xml>"
		mock_generator_class.return_value = mock_generator
		
		mock_client = MagicMock()
		mock_client.submit_invoice.side_effect = Exception("API Error")
		mock_client_class.return_value = mock_client
		
		# Process the submission (should raise exception)
		with self.assertRaises(Exception) as context:
			process_invoice_submission(invoice.name, invoice.company)
		
		self.assertIn("API Error", str(context.exception))
		
		# Verify invoice status was updated to Rejected
		invoice.reload()
		self.assertEqual(invoice.custom_einvoice_status, "Rejected")

	def test_get_submission_status_api(self):
		"""Test get submission status API endpoint"""
		invoice = self.create_test_invoice()
		
		# Update invoice with some status data
		frappe.db.set_value('Sales Invoice', invoice.name, {
			'custom_einvoice_status': 'Accepted',
			'custom_einvoice_uuid': 'test-uuid-456'
		})
		
		result = get_submission_status(invoice.name)
		
		self.assertEqual(result['invoice'], invoice.name)
		self.assertEqual(result['einvoice_status'], 'Accepted')
		self.assertEqual(result['einvoice_uuid'], 'test-uuid-456')
		self.assertFalse(result['has_active_job'])

	def test_duplicate_submission_prevention(self):
		"""Test prevention of duplicate simultaneous submissions"""
		invoice = self.create_test_invoice()
		
		# Mock an existing job
		with patch('frappe.get_all', return_value=[{'name': 'existing_job'}]):
			with self.assertRaises(frappe.ValidationError) as context:
				submit_invoice_to_jofotara(invoice.name)
			
			self.assertIn("already in progress", str(context.exception))

	def test_activity_serial_validation_in_background_job(self):
		"""Test Activity Serial Number validation in background job"""
		invoice = self.create_test_invoice()
		
		# Update company with invalid activity serial
		frappe.db.set_value('Company', invoice.company, 'jofotara_activity_serial', 'invalid123')
		
		with self.assertRaises(Exception) as context:
			process_invoice_submission(invoice.name, invoice.company)
		
		self.assertIn("1-15 digits only", str(context.exception))

	def test_company_integration_disabled(self):
		"""Test submission when company integration is disabled"""
		invoice = self.create_test_invoice()
		
		# Disable integration
		frappe.db.set_value('Company', invoice.company, 'jofotara_is_active', 0)
		
		with self.assertRaises(Exception) as context:
			process_invoice_submission(invoice.name, invoice.company)
		
		self.assertIn("integration is disabled", str(context.exception))

	@patch('frappe.enqueue')
	def test_enqueue_invoice_submission(self, mock_enqueue):
		"""Test invoice submission enqueueing"""
		invoice = self.create_test_invoice()
		
		mock_job = MagicMock()
		mock_job.id = "test_job_789"
		mock_enqueue.return_value = mock_job
		
		job = enqueue_invoice_submission(invoice.name, invoice.company)
		
		# Verify enqueue was called with correct parameters
		mock_enqueue.assert_called_once()
		call_args = mock_enqueue.call_args
		self.assertEqual(call_args[1]['method'], 'jofotara_integration.api.background_jobs.process_invoice_submission')
		self.assertEqual(call_args[1]['queue'], 'long')
		self.assertEqual(call_args[1]['timeout'], 60)
		self.assertEqual(call_args[1]['sales_invoice'], invoice.name)
		self.assertEqual(call_args[1]['company'], invoice.company)
		
		# Verify invoice status was updated
		invoice.reload()
		self.assertEqual(invoice.custom_einvoice_status, "Submitted")


if __name__ == '__main__':
	unittest.main() 