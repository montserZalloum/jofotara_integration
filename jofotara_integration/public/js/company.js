frappe.ui.form.on('Company', {
	refresh: function(frm) {
		// Add JoFotara configuration status indicator (AC: 6)
		add_jofotara_configuration_indicator(frm);
		
		// Add configuration summary button for System Managers
		if (frappe.user.has_role('System Manager')) {
			add_configuration_summary_button(frm);
		}
	},
	
	jofotara_is_active: function(frm) {
		// Update configuration indicator when active status changes (AC: 5)
		add_jofotara_configuration_indicator(frm);
	},
	
	jofotara_auto_submit: function(frm) {
		// Update configuration indicator when auto submit changes (AC: 5)
		add_jofotara_configuration_indicator(frm);
	},
	
	jofotara_client_id: function(frm) {
		// Update configuration indicator when credentials change (AC: 5)
		add_jofotara_configuration_indicator(frm);
	},
	
	jofotara_secret_key: function(frm) {
		// Update configuration indicator when credentials change (AC: 5)
		add_jofotara_configuration_indicator(frm);
	},
	
	jofotara_activity_serial: function(frm) {
		// Update configuration indicator when credentials change (AC: 5)
		add_jofotara_configuration_indicator(frm);
	}
});

function add_jofotara_configuration_indicator(frm) {
	// Remove existing indicator
	remove_jofotara_configuration_indicator();
	
	// Get current configuration values
	const is_active = frm.doc.jofotara_is_active;
	const auto_submit = frm.doc.jofotara_auto_submit;
	const has_client_id = frm.doc.jofotara_client_id;
	const has_secret_key = frm.doc.jofotara_secret_key;
	const has_activity_serial = frm.doc.jofotara_activity_serial;
	
	const has_complete_credentials = has_client_id && has_secret_key && has_activity_serial;
	
	// Determine indicator status
	let status_text, status_color, status_icon, warning_text = '';
	
	if (!is_active) {
		status_text = __('JoFotara Integration: Disabled');
		status_color = '#666';
		status_icon = 'fa-times-circle';
	} else if (!has_complete_credentials) {
		status_text = __('JoFotara Integration: Missing Credentials');
		status_color = '#f44336';
		status_icon = 'fa-exclamation-triangle';
		
		const missing = [];
		if (!has_client_id) missing.push(__('Client ID'));
		if (!has_secret_key) missing.push(__('Secret Key'));
		if (!has_activity_serial) missing.push(__('Activity Serial'));
		warning_text = __('Missing: {0}', [missing.join(', ')]);
	} else if (auto_submit) {
		status_text = __('JoFotara Integration: Auto Submit Enabled');
		status_color = '#4CAF50';
		status_icon = 'fa-check-circle';
		warning_text = __('New invoices will be automatically submitted to JoFotara');
	} else {
		status_text = __('JoFotara Integration: Manual Submit Only');
		status_color = '#ff9800';
		status_icon = 'fa-hand-paper-o';
		warning_text = __('Invoices require manual submission to JoFotara');
	}
	
	// Create indicator HTML
	const indicator_html = `
		<div id="jofotara-config-indicator" style="margin: 15px 0; padding: 12px; background-color: #f8f9fa; border-radius: 6px; border-left: 4px solid ${status_color};">
			<div style="display: flex; align-items: center; gap: 10px; margin-bottom: 5px;">
				<i class="fa ${status_icon}" style="color: ${status_color}; font-size: 18px;"></i>
				<strong style="color: ${status_color}; font-size: 14px;">${status_text}</strong>
			</div>
			${warning_text ? `<div style="font-size: 12px; color: #666; margin-left: 28px;">${warning_text}</div>` : ''}
			${is_active && has_complete_credentials ? 
				`<div style="margin-top: 8px; margin-left: 28px;">
					<button class="btn btn-sm btn-default" onclick="test_jofotara_connection('${frm.doc.name}')">
						<i class="fa fa-wifi"></i> Test Connection
					</button>
				</div>` : ''
			}
		</div>
	`;
	
	// Find JoFotara section and add indicator after it
	const jofotara_section = frm.get_field('jofotara_section');
	if (jofotara_section && jofotara_section.$wrapper) {
		jofotara_section.$wrapper.after(indicator_html);
	}
}

function remove_jofotara_configuration_indicator() {
	const existing_indicator = document.getElementById('jofotara-config-indicator');
	if (existing_indicator) {
		existing_indicator.remove();
	}
}

function test_jofotara_connection(company_name) {
	frappe.call({
		method: 'jofotara_integration.api.company_config.test_company_connection',
		args: {
			company_name: company_name
		},
		callback: function(response) {
			if (response.message) {
				const result = response.message;
				frappe.msgprint({
					title: __('Connection Test Result'),
					message: result.success ? 
						__('✅ Connection successful! JoFotara integration is properly configured.') :
						__('❌ Connection failed: {0}', [result.error]),
					indicator: result.success ? 'green' : 'red'
				});
			}
		},
		error: function(error) {
			frappe.msgprint({
				title: __('Connection Test Failed'),
				message: __('Unable to test connection: {0}', [error.message || 'Unknown error']),
				indicator: 'red'
			});
		}
	});
}

function add_configuration_summary_button(frm) {
	frm.add_custom_button(__('JoFotara Configuration Summary'), function() {
		show_all_companies_configuration();
	}, __('Tools'));
}

function show_all_companies_configuration() {
	frappe.call({
		method: 'jofotara_integration.api.company_config.get_all_companies_configuration',
		callback: function(response) {
			if (response.message) {
				create_configuration_summary_dialog(response.message);
			}
		},
		error: function(error) {
			frappe.msgprint({
				title: __('Failed to Load Configuration'),
				message: __('Unable to load configuration summary: {0}', [error.message || 'Unknown error']),
				indicator: 'red'
			});
		}
	});
}

function create_configuration_summary_dialog(companies) {
	// Create a dialog to show all companies configuration
	const fields = companies.map(company => {
		const status_color = get_status_color(company.status_summary);
		return {
			fieldtype: 'HTML',
			fieldname: `company_${company.company}`,
			options: `
				<div style="padding: 10px; margin: 5px 0; border: 1px solid #ddd; border-radius: 4px; border-left: 4px solid ${status_color};">
					<div style="display: flex; justify-content: between; align-items: center;">
						<strong>${company.company_name}</strong>
						<span style="color: ${status_color}; font-size: 12px; margin-left: auto;">${company.status_summary}</span>
					</div>
					<div style="font-size: 12px; color: #666; margin-top: 5px;">
						${company.is_active ? '✅ Active' : '❌ Inactive'} | 
						${company.auto_submit ? '🔄 Auto Submit' : '✋ Manual Submit'} | 
						${company.has_complete_credentials ? '🔑 Credentials OK' : '⚠️ Missing Credentials'}
					</div>
				</div>
			`
		};
	});
	
	const d = new frappe.ui.Dialog({
		title: __('JoFotara Configuration Summary - All Companies'),
		fields: fields,
		size: 'large'
	});
	
	d.show();
}

function get_status_color(status_summary) {
	const colors = {
		'Integration Disabled': '#666',
		'Missing Credentials': '#f44336',
		'Auto Submit Enabled': '#4CAF50',
		'Manual Submit Only': '#ff9800'
	};
	return colors[status_summary] || '#666';
}
