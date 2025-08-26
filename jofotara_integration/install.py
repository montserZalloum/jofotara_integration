import frappe
import os

def after_install():
	"""Install print format and custom fields after app installation"""
	install_print_format()
	install_custom_fields()


def install_custom_fields():
	"""Install custom fields for Company and Sales Invoice"""
	try:
		# Install Company custom fields
		from jofotara_integration.custom.company import add_custom_fields as add_company_fields
		add_company_fields()
		print("✅ Company custom fields installed successfully")
		
		# Install Sales Invoice custom fields
		from jofotara_integration.custom.sales_invoice import add_custom_fields as add_sales_invoice_fields
		add_sales_invoice_fields()
		print("✅ Sales Invoice custom fields installed successfully")
		
		frappe.db.commit()
		
	except Exception as e:
		print(f"❌ Error installing custom fields: {e}")
		frappe.db.rollback()

def install_print_format():
	"""Install the Invoice with QR Code print format"""
	try:
		# Check if print format already exists
		if not frappe.db.exists("Print Format", "Invoice with QR Code"):
			# Read the HTML template content
			html_content = get_print_format_html()
			
			# Create the print format
			print_format = frappe.get_doc({
				"doctype": "Print Format",
				"name": "Invoice with QR Code",
				"doc_type": "Sales Invoice",
				"print_format_type": "Jinja",
				"html": html_content,
				"css": "",
				"raw_printing": 0,
				"standard": "No",
				"custom_format": 1,
				"disabled": 0,
				"font_size": 13,
				"margin_bottom": 15.0,
				"margin_left": 15.0,
				"margin_right": 15.0,
				"margin_top": 15.0,
				"show_section_headings": 0,
				"default_print_language": "en"
			})
			print_format.insert()
			frappe.db.commit()
			print("✅ Print Format 'Invoice with QR Code' installed successfully")
		else:
			# Update existing print format
			print_format = frappe.get_doc("Print Format", "Invoice with QR Code")
			html_content = get_print_format_html()
			print_format.html = html_content
			print_format.save()
			frappe.db.commit()
			print("✅ Print Format 'Invoice with QR Code' updated successfully")
			
	except Exception as e:
		print(f"❌ Error installing print format: {e}")
		frappe.db.rollback()

def get_print_format_html():
	"""Get the HTML content for the print format"""
	html_template_path = os.path.join(
		frappe.get_app_path("jofotara_integration"),
		"jofotara_integration", "print_formats", "invoice_with_qr", "invoice_with_qr.html"
	)
	
	if os.path.exists(html_template_path):
		with open(html_template_path, 'r', encoding='utf-8') as f:
			return f.read()
	else:
		# Fallback HTML content if file doesn't exist
		return """
<div class="print-format">
	<div class="invoice-header">
		<div class="row">
			<div class="col-md-6">
				<img src="{{ doc.company_logo }}" class="company-logo" style="max-height: 80px;">
				<h3>{{ doc.company }}</h3>
				<p>{{ doc.company_address }}</p>
			</div>
			<div class="col-md-6 text-right">
				<h2>INVOICE</h2>
				<p><strong>Invoice #:</strong> {{ doc.name }}</p>
				<p><strong>Date:</strong> {{ doc.posting_date }}</p>
				<p><strong>Due Date:</strong> {{ doc.due_date }}</p>
			</div>
		</div>
	</div>

	<div class="customer-details">
		<div class="row">
			<div class="col-md-6">
				<h4>Bill To:</h4>
				<p><strong>{{ doc.customer_name }}</strong></p>
				<p>{{ doc.customer_address }}</p>
			</div>
			<div class="col-md-6">
				{% if doc.custom_invoice_qr_code %}
				<div class="qr-code-section">
					<h4>E-Invoice QR Code</h4>
					<div class="qr-code-container" style="text-align: center; padding: 10px; border: 1px solid #ddd;">
						<img id="qr-code-image" src="data:image/png;base64,{{ doc.custom_invoice_qr_code }}" 
							 alt="E-Invoice QR Code" style="max-width: 150px; max-height: 150px;">
						<p style="font-size: 11px; margin-top: 5px;">Scan for E-Invoice Verification</p>
					</div>
				</div>
				{% endif %}
			</div>
		</div>
	</div>

	<div class="invoice-items">
		<table class="table table-bordered">
			<thead>
				<tr>
					<th>Item</th>
					<th>Description</th>
					<th>Qty</th>
					<th>Rate</th>
					<th>Amount</th>
				</tr>
			</thead>
			<tbody>
				{% for item in doc.items %}
				<tr>
					<td>{{ item.item_code }}</td>
					<td>{{ item.description }}</td>
					<td>{{ item.qty }}</td>
					<td>{{ frappe.utils.fmt_money(item.rate, currency=doc.currency) }}</td>
					<td>{{ frappe.utils.fmt_money(item.amount, currency=doc.currency) }}</td>
				</tr>
				{% endfor %}
			</tbody>
		</table>
	</div>

	<div class="invoice-totals">
		<div class="row">
			<div class="col-md-6">
				{% if doc.custom_invoice_qr_code %}
				<div class="e-invoice-info">
					<p><strong>E-Invoice Status:</strong> {{ doc.custom_einvoice_status or "Not Submitted" }}</p>
					{% if doc.custom_einvoice_status == "Accepted" %}
					<p style="color: green; font-weight: bold;">✓ Tax Authority Approved</p>
					{% endif %}
				</div>
				{% endif %}
			</div>
			<div class="col-md-6">
				<table class="table table-bordered totals-table" style="margin-left: auto; width: 300px;">
					<tr>
						<td><strong>Subtotal:</strong></td>
						<td class="text-right">{{ frappe.utils.fmt_money(doc.net_total, currency=doc.currency) }}</td>
					</tr>
					{% if doc.total_taxes_and_charges %}
					<tr>
						<td><strong>Tax:</strong></td>
						<td class="text-right">{{ frappe.utils.fmt_money(doc.total_taxes_and_charges, currency=doc.currency) }}</td>
					</tr>
					{% endif %}
					<tr style="font-weight: bold; border-top: 2px solid #000;">
						<td><strong>Total:</strong></td>
						<td class="text-right">{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</td>
					</tr>
				</table>
			</div>
		</div>
	</div>

	<div class="invoice-footer">
		<div class="row">
			<div class="col-md-12">
				<hr>
				<p style="text-align: center; font-size: 12px;">
					{% if doc.custom_invoice_qr_code %}
					This invoice has been electronically submitted to tax authorities and contains an official QR code for verification.
					{% else %}
					This invoice has not been electronically submitted to tax authorities.
					{% endif %}
				</p>
			</div>
		</div>
	</div>
</div>

<style>
	.print-format {
		font-family: Arial, sans-serif;
		font-size: 13px;
		line-height: 1.4;
	}
	
	.invoice-header {
		margin-bottom: 30px;
		padding-bottom: 20px;
		border-bottom: 2px solid #ddd;
	}
	
	.customer-details {
		margin-bottom: 20px;
	}
	
	.qr-code-section {
		background-color: #f9f9f9;
		padding: 15px;
		border-radius: 5px;
	}
	
	.qr-code-container {
		background-color: white;
		border-radius: 3px;
	}
	
	.invoice-items {
		margin-bottom: 20px;
	}
	
	.invoice-items table {
		width: 100%;
		border-collapse: collapse;
	}
	
	.invoice-items th,
	.invoice-items td {
		padding: 8px;
		text-align: left;
		border: 1px solid #ddd;
	}
	
	.invoice-items th {
		background-color: #f2f2f2;
		font-weight: bold;
	}
	
	.invoice-totals {
		margin-bottom: 30px;
	}
	
	.totals-table {
		width: auto;
		margin-left: auto;
	}
	
	.totals-table td {
		padding: 5px 10px;
	}
	
	.e-invoice-info {
		background-color: #e8f5e8;
		padding: 10px;
		border-radius: 5px;
		border-left: 4px solid #4CAF50;
	}
	
	.invoice-footer {
		margin-top: 40px;
		font-size: 11px;
		color: #666;
	}
	
	@media print {
		.qr-code-section {
			background-color: transparent !important;
			border: 1px solid #000 !important;
		}
		
		.qr-code-container {
			border: 1px solid #000 !important;
		}
		
		.e-invoice-info {
			background-color: transparent !important;
			border: 1px solid #000 !important;
		}
	}
</style>
		"""

def after_migrate():
	"""Run after migrations to ensure print format and custom fields are installed"""
	install_print_format()
	install_custom_fields()

@frappe.whitelist()
def install_qr_print_format():
	"""Manual command to install/update the QR print format"""
	install_print_format()
	return {"message": "Print format installation completed"} 