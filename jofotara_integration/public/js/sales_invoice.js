frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		// Clean up any stuck progress indicators from previous sessions
		hide_submission_progress(frm);
		
		// Add JoFotara configuration status indicator (AC: 6)
		add_company_configuration_status(frm);
		
		// Add buyer validation status indicator (Task 6)
		add_buyer_validation_status(frm);
		
		// Add JoFotara submission button for submitted invoices
		if (frm.doc.docstatus === 1) {
			add_jofotara_submission_button(frm);
		}
		
		// Setup real-time listeners for submission updates (only once per form instance)
		if (!frm.jofotara_listeners_setup) {
			setup_realtime_listeners(frm);
			frm.jofotara_listeners_setup = true;
		}
		
		// Add QR code preview functionality
		add_qr_code_preview(frm);
		
		// Add enhanced print preview button
		add_enhanced_print_preview_button(frm);
		
		// Control e-invoicing section visibility based on company settings
		control_einvoicing_section_visibility(frm);
	},
	
	company: function(frm) {
		// Update e-invoicing section visibility when company changes
		control_einvoicing_section_visibility(frm);
		// Refresh buyer validation when company changes
		add_buyer_validation_status(frm);
	},
	
	customer: function(frm) {
		// Refresh buyer validation when customer changes
		add_buyer_validation_status(frm);
	},
	
	customer_name: function(frm) {
		// Refresh buyer validation when customer name changes
		add_buyer_validation_status(frm);
	},
	
	grand_total: function(frm) {
		// Refresh buyer validation when total changes (for threshold checks)
		add_buyer_validation_status(frm);
	},
	
	is_pos: function(frm) {
		// Refresh buyer validation when payment method changes
		add_buyer_validation_status(frm);
	},
	
	custom_einvoice_qr_code: function(frm) {
		// Real-time QR code display when field is updated
		add_qr_code_preview(frm);
	}
});

function add_jofotara_submission_button(frm) {
	const einvoice_status = frm.doc.custom_einvoice_status;
	
	// Only show button if not already accepted
	if (einvoice_status !== 'Accepted') {
		frm.add_custom_button(__('Submit to JoFotara'), function() {
			submit_to_jofotara(frm);
		}, __('Actions'));
		
		// Style the button
		frm.custom_buttons[__('Submit to JoFotara')].addClass('btn-primary');
	}
	
	// Add status check button
	frm.add_custom_button(__('Check Status'), function() {
		check_submission_status(frm);
	}, __('Actions'));
	

	
	// Add retry button for rejected invoices
	if (einvoice_status === 'Rejected') {
		frm.add_custom_button(__('Retry Submission'), function() {
			retry_submission(frm);
		}, __('Actions'));
		
		frm.custom_buttons[__('Retry Submission')].addClass('btn-warning');
	}
}

function submit_to_jofotara(frm) {
	// Pre-submission validation including buyer validation
	if (!validate_submission_requirements(frm)) {
		return;
	}
	
	// Additional buyer validation check
	if (!validate_buyer_requirements(frm)) {
		return;
	}
	
	// Show progress dialog
	
	frappe.call({
		method: 'jofotara_integration.api.submission.submit_invoice_to_jofotara',
		args: {
			sales_invoice_name: frm.doc.name
		},
		callback: function(response) {
			if (response.message) {
				const result = response.message;
				
				if (result.status === 'queued') {
					// Real-time notification will handle user feedback
					// Refresh form to update status
					frm.reload_doc();
				}
			}
		},
		error: function(error) {
			
			let error_message = __('Submission failed');
			if (error.message) {
				error_message = error.message;
			}
			
			frappe.msgprint({
				title: __('Submission Failed'),
				message: error_message,
				indicator: 'red'
			});
		}
	});
}

function validate_submission_requirements(frm) {
	// Check if invoice is submitted
	if (frm.doc.docstatus !== 1) {
		frappe.msgprint({
			title: __('Invalid Status'),
			message: __('Only submitted invoices can be sent to JoFotara'),
			indicator: 'red'
		});
		return false;
	}
	
	// Check if already accepted
	const einvoice_status = frm.doc.custom_einvoice_status;
	if (einvoice_status === 'Accepted') {
		frappe.msgprint({
			title: __('Already Submitted'),
			message: __('This invoice has already been accepted by JoFotara'),
			indicator: 'orange'
		});
		return false;
	}
	
	return true;
}

function check_submission_status(frm) {
	frappe.call({
		method: 'jofotara_integration.api.submission.get_submission_status',
		args: {
			sales_invoice_name: frm.doc.name
		},
		callback: function(response) {
			if (response.message) {
				const status = response.message;
				
				let message = `<p><strong>Status:</strong> ${status.einvoice_status}</p>`;
				
				if (status.einvoice_uuid) {
					message += `<p><strong>UUID:</strong> ${status.einvoice_uuid}</p>`;
				}
				
				if (status.has_active_job) {
					message += `<p><strong>Active Jobs:</strong> ${status.active_jobs.length}</p>`;
				}
				
				frappe.msgprint({
					title: __('Submission Status'),
					message: message,
					indicator: status.einvoice_status === 'Accepted' ? 'green' : 
							  status.einvoice_status === 'Rejected' ? 'red' : 'blue'
				});
			}
		}
	});
}

function retry_submission(frm) {
	frappe.confirm(
		__('Are you sure you want to retry the submission to JoFotara?'),
		function() {
			frappe.call({
				method: 'jofotara_integration.api.background_jobs.retry_failed_submission',
				args: {
					sales_invoice_name: frm.doc.name
				},
				callback: function(response) {
					if (response.message && response.message.status === 'queued') {
						frappe.msgprint({
							title: __('Retry Queued'),
							message: __('Submission retry has been queued for processing.'),
							indicator: 'blue'
						});
						
						frm.reload_doc();
					}
				}
			});
		}
	);
}



function hide_submission_progress(frm) {
	// Helper function to clean up any stuck progress indicators
	if (frm.jofotara_progress) {
		frm.jofotara_progress.remove();
		frm.jofotara_progress = null;
	}
}

// Dashboard progress indicator removed - using only modal progress dialog

function setup_realtime_listeners(frm) {
	// Listen for submission completion events
	frappe.realtime.on('jofotara_submission_success', function(data) {
		if (data.invoice === frm.doc.name) {
			// Show success notification
			frappe.show_alert({
				message: __('Invoice successfully submitted to JoFotara'),
				indicator: 'green'
			});
			
			// Refresh form to show updated status
			frm.reload_doc();
		}
	});
	
	frappe.realtime.on('jofotara_submission_error', function(data) {
		if (data.invoice === frm.doc.name) {
			// Show error notification
			frappe.show_alert({
				message: __('Invoice submission failed: {0}', [data.error || 'Unknown error']),
				indicator: 'red'
			});
			
			// Refresh form to show updated status
			frm.reload_doc();
		}
	});
	
	frappe.realtime.on('jofotara_submission_queued', function(data) {
		if (data.invoice === frm.doc.name) {
			// Show queued notification
			frappe.show_alert({
				message: __('Invoice submission queued for processing'),
				indicator: 'blue'
			});
		}
	});
}

// Custom field display formatting
frappe.ui.form.on('Sales Invoice', {
	custom_einvoice_status: function(frm) {
		// Update status indicator color based on e-invoice status
		const status = frm.doc.custom_einvoice_status;
		update_status_indicator(frm, status);
	}
});

function update_status_indicator(frm, status) {
	// Add visual indicators for different statuses
	const status_colors = {
		'Pending': 'grey',
		'Submitted': 'blue', 
		'Accepted': 'green',
		'Rejected': 'red'
	};
	
	if (status && status_colors[status]) {
		// Update the field's appearance if possible
		const field = frm.get_field('custom_einvoice_status');
		if (field && field.$wrapper) {
			field.$wrapper.find('.control-value').css('color', status_colors[status]);
		}
	}
}

// QR Code Preview Functionality
function add_qr_code_preview(frm) {
	const qr_code_data = frm.doc.custom_einvoice_qr_code;
	const status = frm.doc.custom_einvoice_status;
	
	// Remove existing QR code preview
	remove_qr_code_preview(frm);
	
	if (qr_code_data && validate_qr_code_data(qr_code_data)) {
		create_qr_code_preview_section(frm, qr_code_data, status);
	}
}

function validate_qr_code_data(qr_data) {
	if (!qr_data || qr_data.trim() === '') {
		return false;
	}
	
	// Basic validation for base64 format
	try {
		const base64Pattern = /^[A-Za-z0-9+/]*={0,2}$/;
		return base64Pattern.test(qr_data);
	} catch (error) {
		console.error('Error validating QR code data:', error);
		return false;
	}
}

function create_qr_code_preview_section(frm, qr_data, status) {
	// Find a good place to insert the QR code preview
	const target_field = frm.get_field('custom_einvoice_qr_code') || frm.get_field('custom_einvoice_status');
	if (!target_field || !target_field.$wrapper) {
		return;
	}
	
	// Create QR code preview HTML
	const qr_preview_html = `
		<div id="qr-code-preview-section" style="margin-top: 15px; padding: 15px; background-color: #f9f9f9; border-radius: 5px; border-left: 4px solid #4CAF50;">
			<h5 style="margin-bottom: 10px; color: #333;">
				<i class="fa fa-qrcode"></i> E-Invoice QR Code Preview
			</h5>
			<div style="display: flex; align-items: flex-start; gap: 15px;">
				<div style="text-align: center;">
					<img id="qr-preview-image" 
						 src="data:image/png;base64,${qr_data}" 
						 alt="E-Invoice QR Code" 
						 style="max-width: 120px; max-height: 120px; border: 1px solid #ddd; border-radius: 3px;">
					<p style="font-size: 11px; margin-top: 5px; color: #666;">Scan for Verification</p>
				</div>
				<div style="flex: 1;">
					<p><strong>Status:</strong> 
						<span style="color: ${getStatusColor(status)}; font-weight: bold;">${status || 'Not Submitted'}</span>
					</p>
					${status === 'Accepted' ? '<p style="color: green; font-weight: bold;"><i class="fa fa-check-circle"></i> Tax Authority Approved</p>' : ''}
					<p style="font-size: 12px; color: #666;">
						This QR code will appear on printed invoices and allows customers to verify the invoice authenticity with tax authorities.
					</p>
					<button class="btn btn-sm btn-default" onclick="preview_qr_print_format('${frm.doc.name}')">
						<i class="fa fa-print"></i> Preview Print with QR
					</button>
				</div>
			</div>
		</div>
	`;
	
	// Insert after the target field
	target_field.$wrapper.after(qr_preview_html);
	
	// Setup error handling for QR image
	const qr_image = document.getElementById('qr-preview-image');
	if (qr_image) {
		qr_image.onerror = function() {
			this.style.display = 'none';
			this.parentElement.innerHTML = '<p style="color: red; font-size: 12px;">QR Code could not be displayed</p>';
		};
	}
}

function remove_qr_code_preview(frm) {
	const existing_preview = document.getElementById('qr-code-preview-section');
	if (existing_preview) {
		existing_preview.remove();
	}
}

function getStatusColor(status) {
	const colors = {
		'Pending': '#666',
		'Submitted': '#0066cc',
		'Accepted': '#4CAF50',
		'Rejected': '#f44336'
	};
	return colors[status] || '#666';
}

// Enhanced Print Preview Functionality
function add_enhanced_print_preview_button(frm) {
	// Only add for submitted invoices or those with QR codes
	if (frm.doc.docstatus === 1 || frm.doc.custom_einvoice_qr_code) {
		frm.add_custom_button(__('Print with QR Code'), function() {
			open_qr_print_preview(frm);
		}, __('Print'));
	}
}

function preview_qr_print_format(invoice_name) {
	// Function called from QR preview section button
	const url = `/printview?doctype=Sales Invoice&name=${invoice_name}&format=Invoice with QR Code&no_letterhead=0&letterhead=No Letterhead&settings={}&_lang=en`;
	window.open(url, '_blank');
}

function open_qr_print_preview(frm) {
	// Enhanced print preview with QR code format
	const print_formats = ['Invoice with QR Code', 'Standard'];
	
	// Create dialog for print format selection
	const d = new frappe.ui.Dialog({
		title: __('Print Preview Options'),
		fields: [
			{
				fieldtype: 'Select',
				fieldname: 'print_format',
				label: __('Print Format'),
				options: print_formats.join('\n'),
				default: 'Invoice with QR Code',
				description: __('Select print format for preview')
			},
			{
				fieldtype: 'Check',
				fieldname: 'include_qr',
				label: __('Include QR Code'),
				default: 1,
				description: __('Include QR code in print format (if available)')
			}
		],
		primary_action_label: __('Preview'),
		primary_action: function(values) {
			const format = values.print_format;
			const url = `/printview?doctype=Sales Invoice&name=${frm.doc.name}&format=${encodeURIComponent(format)}&no_letterhead=0&letterhead=No Letterhead&settings={}&_lang=en`;
			window.open(url, '_blank');
			d.hide();
		}
	});
	
	d.show();
}

// PDF Generation with QR Code
function generate_pdf_with_qr(frm) {
	frappe.call({
		method: 'frappe.utils.print_format.download_pdf',
		args: {
			doctype: 'Sales Invoice',
			name: frm.doc.name,
			format: 'Invoice with QR Code',
			no_letterhead: 0
		},
		callback: function(response) {
			if (response.message) {
				// Handle PDF download
				const link = document.createElement('a');
				link.href = response.message.pdf_data;
				link.download = `${frm.doc.name}_with_qr.pdf`;
				link.click();
			}
		}
	});
}

// Company Configuration Status Indicator (AC: 6)
function add_company_configuration_status(frm) {
	// Remove existing configuration status
	remove_configuration_status(frm);
	
	if (frm.doc.company) {
		// Fetch company configuration status
		frappe.call({
			method: 'jofotara_integration.api.company_config.get_company_configuration_status',
			args: {
				company_name: frm.doc.company
			},
			callback: function(response) {
				if (response.message) {
					create_configuration_status_display(frm, response.message);
				}
			},
			error: function() {
				// Silent fail - don't show configuration status if API fails
			}
		});
	}
}

function create_configuration_status_display(frm, config_status) {
	// Find the company field to insert status after
	const company_field = frm.get_field('company');
	if (!company_field || !company_field.$wrapper) {
		return;
	}
	
	const is_active = config_status.is_active;
	const auto_submit = config_status.auto_submit;
	const has_credentials = config_status.has_complete_credentials;
	
	// Determine overall status
	let status_text, status_color, status_icon;
	if (!is_active) {
		status_text = __('JoFotara Integration Disabled');
		status_color = '#666';
		status_icon = 'fa-times-circle';
	} else if (!has_credentials) {
		status_text = __('JoFotara Integration - Missing Credentials');
		status_color = '#f44336';
		status_icon = 'fa-exclamation-triangle';
	} else if (auto_submit) {
		status_text = __('JoFotara Integration - Auto Submit Enabled');
		status_color = '#4CAF50';
		status_icon = 'fa-check-circle';
	} else {
		status_text = __('JoFotara Integration - Manual Submit Only');
		status_color = '#ff9800';
		status_icon = 'fa-hand-paper-o';
	}
	
	const config_html = `
		<div id="jofotara-config-status" style="margin-top: 10px; padding: 10px; background-color: #f5f5f5; border-radius: 4px; border-left: 4px solid ${status_color};">
			<div style="display: flex; align-items: center; gap: 8px;">
				<i class="fa ${status_icon}" style="color: ${status_color}; font-size: 16px;"></i>
				<strong style="color: ${status_color};">${status_text}</strong>
			</div>
			<div style="margin-top: 6px; font-size: 12px; color: #666;">
				${is_active ? 
					(auto_submit ? 
						__('Invoices will be automatically submitted to JoFotara after submission.') :
						__('Invoices require manual submission to JoFotara.')
					) :
					__('JoFotara integration is disabled for this company.')
				}
				${!has_credentials && is_active ? 
					`<br><span style="color: #f44336;">${__('Missing credentials: Client ID, Secret Key, or Activity Serial')}</span>` :
					''
				}
			</div>
		</div>
	`;
	
	company_field.$wrapper.after(config_html);
}

function remove_configuration_status(frm) {
	const existing_status = document.getElementById('jofotara-config-status');
	if (existing_status) {
		existing_status.remove();
	}
}

// Real-time QR code validation
function validate_qr_code_in_realtime(frm) {
	const qr_field = frm.get_field('custom_einvoice_qr_code');
	if (qr_field) {
		qr_field.$input.on('input', function() {
			const qr_data = $(this).val();
			if (qr_data) {
				setTimeout(() => {
					if (!validate_qr_code_data(qr_data)) {
						frappe.show_alert({
							message: __('Invalid QR code format detected'),
							indicator: 'orange'
						});
					}
				}, 500);
			}
		});
	}
}

// Control e-invoicing section visibility based on company JoFotara activation
function control_einvoicing_section_visibility(frm) {
	if (!frm.doc.company) {
		return;
	}
	
	// Get company's JoFotara activation status
	frappe.db.get_value('Company', frm.doc.company, 'jofotara_is_active')
		.then(r => {
			const is_jofotara_active = r.message && r.message.jofotara_is_active;
			const section_field = frm.get_field('custom_einvoicing_compliance');
			
			if (!section_field) {
				return;
			}
			
			// Determine if section should be visible
			let should_show_section = false;
			
			if (is_jofotara_active) {
				// Always show for active companies
				should_show_section = true;
			} else {
				// For inactive companies, only show if invoice has been submitted to JoFotara
				// (preserve visibility for submitted invoices)
				const has_jofotara_data = frm.doc.custom_einvoice_uuid || 
										  frm.doc.custom_einvoice_status !== 'Pending' ||
										  frm.doc.custom_einvoice_qr_code;
				should_show_section = has_jofotara_data;
			}
			
			// Show/hide the section
			if (should_show_section) {
				section_field.df.hidden = 0;
				frm.layout.show_section(section_field.df);
			} else {
				section_field.df.hidden = 1;
				frm.layout.hide_section(section_field.df);
			}
			
			// Refresh layout to apply changes
			frm.refresh_fields();
		})
		.catch(err => {
			console.error('Error checking company JoFotara status:', err);
		});
}

// Buyer Validation Functions (Task 6)
function add_buyer_validation_status(frm) {
	// Remove existing validation status
	remove_buyer_validation_status(frm);
	
	if (frm.doc.company && (frm.doc.customer || frm.doc.grand_total)) {
		// Perform buyer validation check
		perform_buyer_validation_check(frm);
	}
}

function remove_buyer_validation_status(frm) {
	const existing_status = document.getElementById('buyer-validation-status');
	if (existing_status) {
		existing_status.remove();
	}
}

function perform_buyer_validation_check(frm) {
	// Client-side buyer validation logic
	const validation_result = validate_buyer_requirements_client(frm);
	
	if (validation_result.show_status) {
		create_buyer_validation_display(frm, validation_result);
	}
}

function validate_buyer_requirements_client(frm) {
	const is_pos = frm.doc.is_pos || 0;
	const grand_total = frm.doc.grand_total || 0;
	const currency = frm.doc.currency || 'JOD';
	const customer_name = (frm.doc.customer_name || '').trim();
	
	let validation_result = {
		show_status: false,
		is_valid: true,
		status_text: '',
		status_color: '#4CAF50',
		status_icon: 'fa-check-circle',
		requirements: [],
		errors: [],
		warnings: []
	};
	
	// Determine if buyer name is required
	let requires_buyer_name = false;
	let requirement_reason = '';
	
	if (!is_pos) {
		// Credit invoices always require buyer name
		requires_buyer_name = true;
		requirement_reason = __('Credit invoices require buyer name');
	} else if (is_pos && grand_total >= 10000) {
		// High-value cash invoices require buyer name
		requires_buyer_name = true;
		if (currency === 'JOD') {
			requirement_reason = __('Cash invoices ≥ JOD 10,000 require buyer name');
		} else {
			requirement_reason = __('High-value cash invoices require buyer name (≥ JOD 10,000 equivalent)');
		}
	}
	
	if (requires_buyer_name) {
		validation_result.show_status = true;
		validation_result.requirements.push(requirement_reason);
		
		if (!customer_name || customer_name.length < 2) {
			validation_result.is_valid = false;
			validation_result.status_text = __('Buyer Name Required');
			validation_result.status_color = '#f44336';
			validation_result.status_icon = 'fa-exclamation-triangle';
			validation_result.errors.push(__('Please enter customer name (minimum 2 characters)'));
		} else {
			validation_result.status_text = __('Buyer Validation Passed');
			validation_result.status_color = '#4CAF50';
			validation_result.status_icon = 'fa-check-circle';
		}
	}
	
	// Add warnings for edge cases
	if (currency !== 'JOD' && grand_total >= 10000) {
		validation_result.warnings.push(__('High-value invoice in {0} may require additional documentation', [currency]));
	}
	
	return validation_result;
}

function create_buyer_validation_display(frm, validation_result) {
	// Find the customer field to insert status after
	const customer_field = frm.get_field('customer_name') || frm.get_field('customer');
	if (!customer_field || !customer_field.$wrapper) {
		return;
	}
	
	let content_html = `
		<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
			<i class="fa ${validation_result.status_icon}" style="color: ${validation_result.status_color}; font-size: 16px;"></i>
			<strong style="color: ${validation_result.status_color};">${validation_result.status_text}</strong>
		</div>
	`;
	
	// Add requirements
	if (validation_result.requirements.length > 0) {
		content_html += `
			<div style="margin-bottom: 8px; font-size: 12px; color: #666;">
				<strong>${__('Requirements:')}</strong>
				<ul style="margin: 5px 0; padding-left: 20px;">
					${validation_result.requirements.map(req => `<li>${req}</li>`).join('')}
				</ul>
			</div>
		`;
	}
	
	// Add errors
	if (validation_result.errors.length > 0) {
		content_html += `
			<div style="margin-bottom: 8px; font-size: 12px; color: #f44336;">
				<strong>${__('Issues:')}</strong>
				<ul style="margin: 5px 0; padding-left: 20px;">
					${validation_result.errors.map(error => `<li>${error}</li>`).join('')}
				</ul>
			</div>
		`;
	}
	
	// Add warnings
	if (validation_result.warnings.length > 0) {
		content_html += `
			<div style="margin-bottom: 8px; font-size: 12px; color: #ff9800;">
				<strong>${__('Warnings:')}</strong>
				<ul style="margin: 5px 0; padding-left: 20px;">
					${validation_result.warnings.map(warning => `<li>${warning}</li>`).join('')}
				</ul>
			</div>
		`;
	}
	
	const validation_html = `
		<div id="buyer-validation-status" style="margin-top: 10px; padding: 10px; background-color: #f5f5f5; border-radius: 4px; border-left: 4px solid ${validation_result.status_color};">
			${content_html}
		</div>
	`;
	
	customer_field.$wrapper.after(validation_html);
}

function validate_buyer_requirements(frm) {
	// Client-side validation before submission
	const validation_result = validate_buyer_requirements_client(frm);
	
	if (!validation_result.is_valid) {
		frappe.msgprint({
			title: __('Buyer Validation Failed'),
			message: validation_result.errors.join('<br>'),
			indicator: 'red'
		});
		return false;
	}
	
	// Show warning dialog for high-value invoices
	if (validation_result.warnings.length > 0) {
		return new Promise((resolve) => {
			frappe.confirm(
				__('Validation Warnings:<br>{0}<br><br>Continue with submission?', [validation_result.warnings.join('<br>')]),
				() => resolve(true),
				() => resolve(false)
			);
		});
	}
	
	return true;
}

// Export invoice type detection (for display purposes)
function get_invoice_type_display(frm) {
	if (!frm.doc.customer) {
		return __('Local Invoice');
	}
	
	// This would need to be enhanced to check customer territory and development area
	// For now, just show Local as default
	return __('Local Invoice');
} 