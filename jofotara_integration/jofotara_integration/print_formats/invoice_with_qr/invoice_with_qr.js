frappe.ready(function() {
	// QR Code Display Logic for Invoice Print Format
	
	// Validate and process QR code data
	function validateQRCodeData(doc) {
		if (!doc.custom_einvoice_qr_code) {
			return false;
		}
		
		// Basic validation for base64 format
		try {
			// Check if it's valid base64
			const base64Pattern = /^[A-Za-z0-9+/]*={0,2}$/;
			if (!base64Pattern.test(doc.custom_einvoice_qr_code)) {
				console.warn('Invalid base64 QR code format');
				return false;
			}
			return true;
		} catch (error) {
			console.error('Error validating QR code data:', error);
			return false;
		}
	}
	
	// Handle QR code image loading errors
	function setupQRCodeErrorHandling() {
		const qrCodeImage = document.getElementById('qr-code-image');
		if (qrCodeImage) {
			qrCodeImage.onerror = function() {
				console.error('Failed to load QR code image');
				// Replace with error message
				const container = qrCodeImage.parentElement;
				container.innerHTML = `
					<div style="padding: 20px; text-align: center; border: 1px dashed #ccc;">
						<p style="color: #666; font-size: 12px;">QR Code could not be displayed</p>
						<p style="color: #666; font-size: 10px;">Please contact support if this issue persists</p>
					</div>
				`;
			};
			
			qrCodeImage.onload = function() {
				console.log('QR code image loaded successfully');
			};
		}
	}
	
	// Enhanced QR code display for print preview
	function enhanceQRCodeDisplay(doc) {
		if (!validateQRCodeData(doc)) {
			return;
		}
		
		const qrSection = document.querySelector('.qr-code-section');
		if (qrSection) {
			// Add print-specific enhancements
			qrSection.setAttribute('data-print-enhanced', 'true');
			
			// Ensure QR code is visible in print mode
			const qrImage = document.getElementById('qr-code-image');
			if (qrImage) {
				qrImage.style.printColorAdjust = 'exact';
				qrImage.style.webkitPrintColorAdjust = 'exact';
			}
		}
	}
	
	// Initialize QR code functionality
	function initializeQRCode(doc) {
		if (doc && doc.custom_einvoice_qr_code) {
			// Validate QR code data
			if (validateQRCodeData(doc)) {
				// Setup error handling
				setupQRCodeErrorHandling();
				
				// Enhance display for print
				enhanceQRCodeDisplay(doc);
				
				// Log successful initialization
				console.log('QR code display initialized for invoice:', doc.name);
			} else {
				console.warn('QR code validation failed for invoice:', doc.name);
			}
		} else {
			console.log('No QR code data available for invoice:', doc.name);
		}
	}
	
	// Print format specific initialization
	function initializePrintFormat() {
		// Get document data from frappe context
		if (typeof frappe !== 'undefined' && frappe.get_route) {
			const route = frappe.get_route();
			if (route[0] === 'print' && route[1] === 'Sales Invoice') {
				// In print view - initialize with current document
				const docname = route[2];
				if (docname) {
					frappe.db.get_doc('Sales Invoice', docname).then(doc => {
						initializeQRCode(doc);
					}).catch(error => {
						console.error('Error fetching document for QR code display:', error);
					});
				}
			}
		}
		
		// Also initialize from global doc if available
		if (typeof doc !== 'undefined') {
			initializeQRCode(doc);
		}
	}
	
	// PDF generation enhancements
	function enhancePDFGeneration() {
		// Ensure QR codes are properly rendered in PDF
		const style = document.createElement('style');
		style.textContent = `
			@media print {
				.qr-code-container img {
					max-width: 150px !important;
					max-height: 150px !important;
					display: block !important;
					margin: 0 auto !important;
				}
				
				.qr-code-section {
					page-break-inside: avoid;
				}
				
				.e-invoice-info {
					page-break-inside: avoid;
				}
			}
		`;
		document.head.appendChild(style);
	}
	
	// Main initialization
	try {
		initializePrintFormat();
		enhancePDFGeneration();
	} catch (error) {
		console.error('Error initializing QR code print format:', error);
	}
});

// Export functions for testing
if (typeof module !== 'undefined' && module.exports) {
	module.exports = {
		validateQRCodeData: validateQRCodeData,
		setupQRCodeErrorHandling: setupQRCodeErrorHandling,
		enhanceQRCodeDisplay: enhanceQRCodeDisplay,
		initializeQRCode: initializeQRCode
	};
} 