frappe.ui.form.on('Sales Invoice', {
	refresh: function(frm) {
		// Add JoFotara submission button for submitted invoices
		if (frm.doc.docstatus === 1) {
			add_jofotara_submission_button(frm);
		}
		
		// Setup real-time listeners for submission updates
		setup_realtime_listeners(frm);
	}
});

function add_jofotara_submission_button(frm) {
	const einvoice_status = frm.doc.custom_einvoice_status || frm.doc.e_invoice_status;
	
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
	// Pre-submission validation
	if (!validate_submission_requirements(frm)) {
		return;
	}
	
	// Show progress dialog
	const progress_dialog = show_progress_dialog('Submitting to JoFotara...', 'Preparing submission...');
	
	frappe.call({
		method: 'jofotara_integration.api.submission.submit_invoice_to_jofotara',
		args: {
			sales_invoice_name: frm.doc.name
		},
		callback: function(response) {
			progress_dialog.hide();
			
			if (response.message) {
				const result = response.message;
				
				if (result.status === 'queued') {
					frappe.msgprint({
						title: __('Submission Queued'),
						message: __('Your invoice has been queued for submission to JoFotara. You will be notified when the process completes.'),
						indicator: 'blue'
					});
					
					// Show ongoing progress
					show_submission_progress(frm, result.job_id);
					
					// Refresh form to update status
					frm.reload_doc();
				}
			}
		},
		error: function(error) {
			progress_dialog.hide();
			
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
	const einvoice_status = frm.doc.custom_einvoice_status || frm.doc.e_invoice_status;
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

function show_progress_dialog(title, message) {
	const dialog = new frappe.ui.Dialog({
		title: title,
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'progress_html',
				options: `
					<div class="text-center">
						<div class="spinner-border text-primary" role="status">
							<span class="sr-only">Loading...</span>
						</div>
						<p class="mt-3">${message}</p>
					</div>
				`
			}
		],
		size: 'small',
		static: true
	});
	
	dialog.show();
	return dialog;
}

function show_submission_progress(frm, job_id) {
	// Show a temporary progress indicator
	const progress_area = frm.dashboard.add_progress(__('JoFotara Submission'), 'blue');
	
	// Auto-hide after 30 seconds (reasonable time for submission)
	setTimeout(() => {
		if (progress_area) {
			progress_area.remove();
		}
	}, 30000);
}

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
		const status = frm.doc.custom_einvoice_status || frm.doc.e_invoice_status;
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
		const field = frm.get_field('custom_einvoice_status') || frm.get_field('e_invoice_status');
		if (field && field.$wrapper) {
			field.$wrapper.find('.control-value').css('color', status_colors[status]);
		}
	}
} 