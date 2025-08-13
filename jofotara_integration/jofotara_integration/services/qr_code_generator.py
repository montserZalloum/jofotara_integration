import frappe
import qrcode
import base64
import io
from PIL import Image
from frappe import _


class QRCodeGenerator:
	"""
	Service for generating QR codes from Base64 strings received from JoFotara API
	
	Provides methods to convert JoFotara Base64 response data into proper QR code images
	that can be stored in Sales Invoice custom_invoice_qr_code image fields
	"""
	
	def __init__(self):
		"""Initialize QR code generator with standard configuration"""
		self.qr_config = {
			'version': 1,
			'error_correction': qrcode.constants.ERROR_CORRECT_L,
			'box_size': 10,
			'border': 4
		}
		self.image_config = {
			'fill_color': 'black',
			'back_color': 'white',
			'format': 'PNG'
		}
	
	def generate_qr_from_base64_string(self, base64_string):
		"""
		Generate QR code image from JoFotara Base64 string response
		
		Args:
			base64_string (str): Base64 string received from JoFotara API response
			
		Returns:
			str: Base64 encoded PNG image data for storage in image field
			
		Raises:
			ValueError: If Base64 string is invalid or QR generation fails
			Exception: If image processing fails
		"""
		if not base64_string or not isinstance(base64_string, str):
			raise ValueError("Base64 string is required and must be a valid string")
		
		# Validate Base64 string format
		try:
			# Test decode to validate Base64 format
			base64.b64decode(base64_string, validate=True)
		except Exception:
			raise ValueError("Invalid Base64 string format provided")
		
		try:
			# Create QR code instance with configured parameters
			qr = qrcode.QRCode(
				version=self.qr_config['version'],
				error_correction=self.qr_config['error_correction'],
				box_size=self.qr_config['box_size'],
				border=self.qr_config['border']
			)
			
			# Add the Base64 data to QR code
			qr.add_data(base64_string)
			qr.make(fit=True)
			
			# Generate QR code image
			qr_image = qr.make_image(
				fill_color=self.image_config['fill_color'],
				back_color=self.image_config['back_color']
			)
			
			# Ensure image is proper size (150x150px as per AC)
			if qr_image.size != (150, 150):
				qr_image = qr_image.resize((150, 150), Image.Resampling.LANCZOS)
			
			# Convert to bytes for Base64 encoding
			img_byte_array = io.BytesIO()
			qr_image.save(img_byte_array, format=self.image_config['format'])
			img_byte_array.seek(0)
			
			# Encode as Base64 for image field storage
			img_base64 = base64.b64encode(img_byte_array.getvalue()).decode('utf-8')
			
			# Return with data URI prefix for image field compatibility
			return f"data:image/png;base64,{img_base64}"
			
		except Exception as e:
			frappe.log_error(f"QR code generation failed: {str(e)}", "QR Code Generation Error")
			raise Exception(f"Failed to generate QR code: {str(e)}")
	
	def validate_qr_code_data(self, base64_string):
		"""
		Validate if Base64 string can be used for QR code generation
		
		Args:
			base64_string (str): Base64 string to validate
			
		Returns:
			dict: Validation result with is_valid boolean and error message if applicable
		"""
		try:
			if not base64_string or not isinstance(base64_string, str):
				return {
					'is_valid': False,
					'error': 'Base64 string is required and must be a valid string'
				}
			
			# Test Base64 decoding
			base64.b64decode(base64_string, validate=True)
			
			# Test QR code generation without saving
			qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L)
			qr.add_data(base64_string)
			qr.make(fit=True)
			
			return {'is_valid': True, 'error': None}
			
		except Exception as e:
			return {
				'is_valid': False,
				'error': f"Invalid QR data: {str(e)}"
			}


def generate_qr_from_base64_string(base64_string):
	"""
	Convenience function for QR code generation from Base64 strings
	
	Args:
		base64_string (str): Base64 string from JoFotara API response
		
	Returns:
		str: Base64 encoded PNG image data for image field storage
		
	Raises:
		ValueError: If Base64 string is invalid
		Exception: If QR generation fails
	"""
	generator = QRCodeGenerator()
	return generator.generate_qr_from_base64_string(base64_string)


def validate_qr_code_data(base64_string):
	"""
	Convenience function for QR code data validation
	
	Args:
		base64_string (str): Base64 string to validate
		
	Returns:
		dict: Validation result with is_valid boolean and error message
	"""
	generator = QRCodeGenerator()
	return generator.validate_qr_code_data(base64_string)
