"""
Multi-Currency Service for JoFotara Integration

This module provides currency validation, conversion, and utility functions
for multi-currency e-invoicing compliance with JoFotara requirements.
"""

import frappe
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any


class MultiCurrencyService:
    """
    Service for handling multi-currency operations in JoFotara e-invoicing.
    
    Provides currency validation, conversion, and compliance utilities
    for all JoFotara-supported currencies with proper precision handling.
    """
    
    # JoFotara supported currencies as per requirements
    SUPPORTED_CURRENCIES = {
        'JOD', 'USD', 'EUR', 'SAR', 'AED', 'OMR', 'GBP', 'QAR', 
        'KWD', 'BHD', 'AUD', 'CAD', 'JPY', 'CHF', 'TRY', 'SYP', 'EGP'
    }
    
    # Default currency for Jordan tax purposes
    DEFAULT_TAX_CURRENCY = 'JOD'
    
    # JOD threshold for buyer validation (10,000 JOD)
    JOD_THRESHOLD = Decimal('10000.00')
    
    def __init__(self):
        """Initialize Multi-Currency Service."""
        pass
    
    def validate_currency_support(self, currency: str) -> Dict[str, Any]:
        """
        Validate if currency is supported by JoFotara.
        
        Args:
            currency: Currency code to validate (e.g., 'USD', 'EUR')
            
        Returns:
            Dict containing:
            - is_valid: bool - Whether currency is supported
            - currency: str - Normalized currency code
            - error_message: str - Error message if invalid
        """
        if not currency:
            return {
                'is_valid': False,
                'currency': None,
                'error_message': 'Currency code is required'
            }
        
        currency_upper = currency.upper().strip()
        
        if currency_upper not in self.SUPPORTED_CURRENCIES:
            return {
                'is_valid': False,
                'currency': currency_upper,
                'error_message': f'Currency {currency_upper} is not supported by JoFotara. Supported currencies: {", ".join(sorted(self.SUPPORTED_CURRENCIES))}'
            }
        
        return {
            'is_valid': True,
            'currency': currency_upper,
            'error_message': None
        }
    
    def get_document_and_tax_currencies(self, invoice_currency: str) -> Tuple[str, str]:
        """
        Get proper DocumentCurrencyCode and TaxCurrencyCode for UBL XML.
        
        As per JoFotara API requirements (updated based on API response):
        - DocumentCurrencyCode: The invoice currency
        - TaxCurrencyCode: MUST be the same as DocumentCurrencyCode (not always JOD)
        
        Args:
            invoice_currency: Currency from the sales invoice
            
        Returns:
            Tuple[str, str]: (document_currency, tax_currency)
        """
        # Validate currency first
        validation = self.validate_currency_support(invoice_currency)
        if not validation['is_valid']:
            frappe.throw(validation['error_message'])
        
        document_currency = validation['currency']
        tax_currency = document_currency  # JoFotara requires both to be the same
        
        return document_currency, tax_currency
    
    def convert_currency(self, amount: Decimal, from_currency: str, to_currency: str, 
                        conversion_date: Optional[str] = None) -> Decimal:
        """
        Convert currency amount with 9 decimal precision.
        
        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code  
            conversion_date: Date for exchange rate lookup (defaults to today)
            
        Returns:
            Decimal: Converted amount with 9 decimal precision
        """
        if from_currency == to_currency:
            return self._round_to_precision(amount)
        
        # Validate both currencies
        from_validation = self.validate_currency_support(from_currency)
        to_validation = self.validate_currency_support(to_currency)
        
        if not from_validation['is_valid']:
            frappe.throw(from_validation['error_message'])
        if not to_validation['is_valid']:
            frappe.throw(to_validation['error_message'])
        
        try:
            # Get exchange rate from ERPNext currency exchange
            exchange_rate = self._get_exchange_rate(
                from_validation['currency'], 
                to_validation['currency'], 
                conversion_date
            )
            
            if exchange_rate is None:
                # Log detailed information for debugging
                frappe.log_error(
                    f"Exchange rate lookup failed: {from_validation['currency']} to {to_validation['currency']}. "
                    f"Amount: {amount}. Check Currency Exchange doctype for missing rates.",
                    "Currency Exchange Missing"
                )
                frappe.throw(
                    f"No exchange rate found for {from_validation['currency']} to {to_validation['currency']}"
                )
            
            converted_amount = amount * Decimal(str(exchange_rate))
            return self._round_to_precision(converted_amount)
            
        except Exception as e:
            frappe.log_error(f"Currency conversion error: {str(e)}", "Multi-Currency Service")
            frappe.throw(f"Failed to convert {from_currency} to {to_currency}: {str(e)}")
    
    def validate_multi_currency_threshold(self, invoice_amount: Decimal, invoice_currency: str, 
                                        customer_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate invoice amount against 10,000 JOD threshold for buyer validation.
        
        Args:
            invoice_amount: Invoice total amount
            invoice_currency: Invoice currency
            customer_info: Customer information for validation context
            
        Returns:
            Dict containing validation results:
            - exceeds_threshold: bool
            - jod_equivalent: Decimal
            - requires_buyer_validation: bool
        """
        try:
            # Convert to JOD if needed
            jod_amount = self.convert_currency(
                invoice_amount, 
                invoice_currency, 
                self.DEFAULT_TAX_CURRENCY
            )
            
            exceeds_threshold = jod_amount >= self.JOD_THRESHOLD
            
            return {
                'exceeds_threshold': exceeds_threshold,
                'jod_equivalent': jod_amount,
                'requires_buyer_validation': exceeds_threshold,
                'threshold_amount': self.JOD_THRESHOLD,
                'original_amount': invoice_amount,
                'original_currency': invoice_currency
            }
            
        except Exception as e:
            frappe.log_error(f"Threshold validation error: {str(e)}", "Multi-Currency Service")
            # Conservative fallback: try to convert using fallback rate or assume 1:1 if very small
            try:
                # If the original amount is very small (< 100 in original currency), 
                # it's very unlikely to exceed 10,000 JOD threshold
                if invoice_amount < Decimal('100'):
                    fallback_jod = invoice_amount  # Assume similar magnitude
                    exceeds_threshold = fallback_jod >= self.JOD_THRESHOLD
                else:
                    # For larger amounts, be conservative and assume validation required
                    fallback_jod = invoice_amount
                    exceeds_threshold = True
                
                return {
                    'exceeds_threshold': exceeds_threshold,
                    'jod_equivalent': fallback_jod,
                    'requires_buyer_validation': exceeds_threshold,
                    'threshold_amount': self.JOD_THRESHOLD,
                    'original_amount': invoice_amount,
                    'original_currency': invoice_currency,
                    'error': str(e),
                    'fallback_used': True
                }
            except:
                # Last resort: conservative fallback
                return {
                    'exceeds_threshold': True,
                    'jod_equivalent': self.JOD_THRESHOLD,  # Set to threshold to indicate uncertainty
                    'requires_buyer_validation': True,
                    'threshold_amount': self.JOD_THRESHOLD,
                    'original_amount': invoice_amount,
                    'original_currency': invoice_currency,
                    'error': str(e),
                    'fallback_used': True
                }
    
    def determine_special_sales_eligibility(self, sales_invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine if invoice qualifies for Special Sales type (3rd digit = 3).
        
        Special Sales criteria:
        - Items with special tax rates
        - Specific item categories or tax templates
        - Custom business rules
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing:
            - is_special_sales: bool
            - reasons: List[str] - Reasons for classification
            - special_items: List[Dict] - Items that qualify as special sales
        """
        try:
            items = sales_invoice.get('items', [])
            special_items = []
            reasons = []
            
            for item in items:
                # Check for special tax rates or categories
                tax_rate = item.get('rate', 0)
                item_tax_template = item.get('item_tax_template')
                
                # Example logic - can be customized based on business rules
                if item_tax_template and 'special' in str(item_tax_template).lower():
                    special_items.append({
                        'item_code': item.get('item_code'),
                        'item_name': item.get('item_name'),
                        'tax_template': item_tax_template,
                        'reason': 'Special tax template'
                    })
                    reasons.append(f"Item {item.get('item_code')} has special tax template")
                
                # Check for zero-rated or exempt items (potential special sales)
                if tax_rate == 0 and item_tax_template:
                    special_items.append({
                        'item_code': item.get('item_code'),
                        'item_name': item.get('item_name'),
                        'tax_rate': tax_rate,
                        'reason': 'Zero-rated with tax template'
                    })
                    reasons.append(f"Item {item.get('item_code')} is zero-rated with tax template")
            
            is_special_sales = len(special_items) > 0
            
            return {
                'is_special_sales': is_special_sales,
                'reasons': reasons,
                'special_items': special_items,
                'total_items': len(items),
                'special_item_count': len(special_items)
            }
            
        except Exception as e:
            frappe.log_error(f"Special sales detection error: {str(e)}", "Multi-Currency Service")
            return {
                'is_special_sales': False,
                'reasons': [f"Error in detection: {str(e)}"],
                'special_items': [],
                'total_items': 0,
                'special_item_count': 0
            }
    
    def validate_currency_compatibility(self, invoice_currency: str, customer_territory: str, 
                                      invoice_type: str) -> Dict[str, Any]:
        """
        Validate currency compatibility with customer territory and invoice type.
        
        Args:
            invoice_currency: Invoice currency code
            customer_territory: Customer's territory/country
            invoice_type: Invoice type (Local/Export/Development Area)
            
        Returns:
            Dict containing validation results
        """
        validation_result = {
            'is_compatible': True,
            'warnings': [],
            'recommendations': []
        }
        
        try:
            # Validate currency support first
            currency_validation = self.validate_currency_support(invoice_currency)
            if not currency_validation['is_valid']:
                validation_result['is_compatible'] = False
                validation_result['warnings'].append(currency_validation['error_message'])
                return validation_result
            
            currency = currency_validation['currency']
            
            # Business rules for currency-territory compatibility
            if invoice_type == 'Local' and currency != 'JOD':
                validation_result['warnings'].append(
                    f"Local invoices typically use JOD currency, but {currency} is specified"
                )
                validation_result['recommendations'].append(
                    "Consider using JOD for local transactions or verify export classification"
                )
            
            if invoice_type == 'Export':
                if customer_territory == 'Jordan' and currency != 'JOD':
                    validation_result['warnings'].append(
                        "Export invoice to Jordan with non-JOD currency - verify classification"
                    )
                elif customer_territory != 'Jordan' and currency == 'JOD':
                    validation_result['warnings'].append(
                        f"Export invoice to {customer_territory} using JOD - consider local currency"
                    )
            
            # Regional currency recommendations
            regional_currencies = {
                'Saudi Arabia': 'SAR',
                'UAE': 'AED',
                'Kuwait': 'KWD', 
                'Bahrain': 'BHD',
                'Qatar': 'QAR',
                'Oman': 'OMR'
            }
            
            if customer_territory in regional_currencies:
                recommended_currency = regional_currencies[customer_territory]
                if currency not in ['JOD', recommended_currency, 'USD']:
                    validation_result['recommendations'].append(
                        f"Consider using {recommended_currency} or USD for {customer_territory}"
                    )
            
            return validation_result
            
        except Exception as e:
            frappe.log_error(f"Currency compatibility validation error: {str(e)}", "Multi-Currency Service")
            return {
                'is_compatible': False,
                'warnings': [f"Validation error: {str(e)}"],
                'recommendations': ['Please verify currency and customer details manually']
            }
    
    def get_or_create_default_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get exchange rate or create default rate for supported currencies.
        
        Args:
            from_currency: Source currency
            to_currency: Target currency
            
        Returns:
            Optional[float]: Exchange rate or None if not available
        """
        # Default exchange rates (approximate, for fallback only)
        default_rates = {
            ('USD', 'JOD'): 0.708,  # 1 USD = 0.708 JOD (approximate)
            ('EUR', 'JOD'): 0.765,  # 1 EUR = 0.765 JOD (approximate)
            ('SAR', 'JOD'): 0.189,  # 1 SAR = 0.189 JOD (approximate)
            ('AED', 'JOD'): 0.193,  # 1 AED = 0.193 JOD (approximate)
            ('GBP', 'JOD'): 0.895,  # 1 GBP = 0.895 JOD (approximate)
        }
        
        # Check if we have a default rate
        rate_key = (from_currency, to_currency)
        reverse_key = (to_currency, from_currency)
        
        if rate_key in default_rates:
            return default_rates[rate_key]
        elif reverse_key in default_rates:
            return 1.0 / default_rates[reverse_key]
        
        return None
    
    def _get_exchange_rate(self, from_currency: str, to_currency: str, 
                          conversion_date: Optional[str] = None) -> Optional[float]:
        """
        Get exchange rate from ERPNext Currency Exchange.
        
        Args:
            from_currency: Source currency
            to_currency: Target currency
            conversion_date: Date for rate lookup
            
        Returns:
            Optional[float]: Exchange rate or None if not found
        """
        try:
            from frappe.utils import getdate, nowdate
            
            date = conversion_date or nowdate()
            if isinstance(date, str):
                date = getdate(date)
            
            # Try to get exchange rate from ERPNext
            exchange_rate = frappe.db.get_value(
                "Currency Exchange",
                {
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "date": ["<=", date]
                },
                "exchange_rate",
                order_by="date desc"
            )
            
            if exchange_rate:
                return float(exchange_rate)
            
            # Try reverse rate
            reverse_rate = frappe.db.get_value(
                "Currency Exchange", 
                {
                    "from_currency": to_currency,
                    "to_currency": from_currency,
                    "date": ["<=", date]
                },
                "exchange_rate",
                order_by="date desc"
            )
            
            if reverse_rate:
                return 1.0 / float(reverse_rate)
            
            # If no rate found, try to get from Currency doctype default rate
            try:
                currency_doc = frappe.get_doc("Currency", to_currency)
                if hasattr(currency_doc, 'exchange_rate') and currency_doc.exchange_rate:
                    return float(currency_doc.exchange_rate)
            except:
                pass
            
            # Try default exchange rates as last resort
            default_rate = self.get_or_create_default_exchange_rate(from_currency, to_currency)
            if default_rate:
                frappe.log_error(
                    f"Using default exchange rate for {from_currency} to {to_currency}: {default_rate}. "
                    f"Consider adding proper exchange rate in Currency Exchange doctype.",
                    "Default Exchange Rate Used"
                )
                return default_rate
            
            return None
            
        except Exception as e:
            frappe.log_error(f"Exchange rate lookup error: {str(e)}", "Multi-Currency Service")
            return None
    
    def _round_to_precision(self, amount: Decimal) -> Decimal:
        """
        Round amount to 9 decimal places as per JoFotara requirements.
        
        Args:
            amount: Amount to round
            
        Returns:
            Decimal: Amount rounded to 9 decimal places
        """
        return amount.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)


# Global service instance
multi_currency_service = MultiCurrencyService()


def get_multi_currency_service() -> MultiCurrencyService:
    """Get the global multi-currency service instance."""
    return multi_currency_service
