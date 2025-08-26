import frappe
from frappe import _

class CurrencyService:
    """Service for handling JoFotara currency requirements and validation"""
    
    # Supported JoFotara currencies as per story requirements
    SUPPORTED_CURRENCIES = [
        'JOD', 'USD', 'EUR', 'SAR', 'AED', 'OMR', 'GBP', 'QAR', 
        'KWD', 'BHD', 'AUD', 'CAD', 'JPY', 'CHF', 'TRY', 'SYP', 'EGP'
    ]
    
    @classmethod
    def get_supported_currencies(cls):
        """Get list of supported JoFotara currencies"""
        return cls.SUPPORTED_CURRENCIES.copy()
    
    @classmethod
    def is_currency_supported(cls, currency_code):
        """Check if a currency code is supported by JoFotara"""
        if not currency_code:
            return False
        return currency_code.upper() in cls.SUPPORTED_CURRENCIES
    
    @classmethod
    def validate_currency_for_jofotara(cls, currency_code, company=None):
        """Validate currency for JoFotara integration"""
        if not currency_code:
            return {
                'valid': False,
                'message': _('Currency is required for JoFotara integration')
            }
        
        if not cls.is_currency_supported(currency_code):
            supported_list = ', '.join(cls.SUPPORTED_CURRENCIES)
            return {
                'valid': False,
                'message': _('Currency {0} is not supported by JoFotara. Supported currencies: {1}').format(
                    currency_code, supported_list
                )
            }
        
        # Check if company has JoFotara enabled
        if company:
            company_doc = frappe.get_doc('Company', company)
            if company_doc.jofotara_is_active:
                return {
                    'valid': True,
                    'message': _('Currency {0} is supported for JoFotara integration').format(currency_code)
                }
        
        return {
            'valid': True,
            'message': _('Currency {0} is supported').format(currency_code)
        }
    
    @classmethod
    def get_currency_validation_message(cls, currency_code):
        """Get user-friendly message for currency validation"""
        if cls.is_currency_supported(currency_code):
            return _('Currency {0} is supported for JoFotara integration').format(currency_code)
        else:
            supported_list = ', '.join(cls.SUPPORTED_CURRENCIES)
            return _('Currency {0} is not supported by JoFotara. Please select one of: {1}').format(
                currency_code, supported_list
            )

@frappe.whitelist()
def get_supported_currencies():
    """API endpoint to get supported currencies"""
    return CurrencyService.get_supported_currencies()

@frappe.whitelist()
def validate_currency(currency_code, company=None):
    """API endpoint to validate currency for JoFotara"""
    return CurrencyService.validate_currency_for_jofotara(currency_code, company)
