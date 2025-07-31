"""
UBL 2.1 XML Generator Service for JoFotara Integration

This module provides XML generation functionality for Sales Invoices
according to UBL 2.1 specifications and JoFotara API requirements.
"""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional
import frappe
from lxml import etree


class UBLXMLGenerator:
    """
    UBL 2.1 XML Generator for JoFotara e-invoicing compliance.
    
    Generates XML documents that comply with UBL 2.1 schema and 
    JoFotara technical specifications.
    """
    
    # UBL 2.1 namespace definitions as per JoFotara specification
    NAMESPACES = {
        None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    }
    
    def __init__(self):
        """Initialize the XML generator with proper namespace configuration."""
        self.nsmap = self.NAMESPACES
    
    def generate_xml(self, sales_invoice: Dict[str, Any], icv_counter: int) -> str:
        """
        Generate UBL 2.1 compliant XML for a Sales Invoice.
        
        Args:
            sales_invoice: Sales Invoice document data
            icv_counter: Invoice Counter Value for sequential numbering
            
        Returns:
            str: Generated XML string with proper UBL 2.1 structure
            
        Raises:
            ValueError: If required invoice data is missing
            Exception: If XML generation fails
        """
        try:
            # Create root element with namespaces
            root = etree.Element("Invoice", nsmap=self.nsmap)
            
            # Add mandatory elements
            self._add_profile_id(root)
            self._add_invoice_id(root, sales_invoice)
            self._add_uuid(root)
            self._add_issue_date(root, sales_invoice)
            self._add_invoice_type_code(root, sales_invoice)
            self._add_currency_codes(root, sales_invoice)
            self._add_icv_document_reference(root, icv_counter)
            
            # Generate XML string with declaration
            xml_str = etree.tostring(
                root, 
                pretty_print=True, 
                xml_declaration=True, 
                encoding='UTF-8'
            ).decode('utf-8')
            
            return xml_str
            
        except Exception as e:
            frappe.log_error(f"XML Generation failed: {str(e)}", "UBL XML Generator")
            raise
    
    def _add_profile_id(self, root: etree.Element) -> None:
        """Add ProfileID element as per JoFotara specification."""
        profile_id = etree.SubElement(root, "{%s}ProfileID" % self.nsmap['cbc'])
        profile_id.text = "reporting:1.0"
    
    def _add_invoice_id(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add Invoice ID element (must be unique per seller)."""
        invoice_id = etree.SubElement(root, "{%s}ID" % self.nsmap['cbc'])
        invoice_id.text = sales_invoice.get('name', '')
    
    def _add_uuid(self, root: etree.Element) -> None:
        """Add UUID element for universal unique identification."""
        uuid_elem = etree.SubElement(root, "{%s}UUID" % self.nsmap['cbc'])
        uuid_elem.text = str(uuid.uuid4())
    
    def _add_issue_date(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add IssueDate in YYYY-MM-DD format."""
        issue_date = etree.SubElement(root, "{%s}IssueDate" % self.nsmap['cbc'])
        posting_date = sales_invoice.get('posting_date')
        if isinstance(posting_date, str):
            issue_date.text = posting_date
        else:
            issue_date.text = posting_date.strftime('%Y-%m-%d') if posting_date else datetime.now().strftime('%Y-%m-%d')
    
    def _add_invoice_type_code(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add InvoiceTypeCode with 3-digit code in name attribute."""
        type_code_elem = etree.SubElement(root, "{%s}InvoiceTypeCode" % self.nsmap['cbc'])
        
        # Determine invoice type code
        type_code = self.determine_invoice_type_code(sales_invoice)
        type_code_elem.text = "388"  # Standard invoice value
        type_code_elem.set("name", type_code)
    
    def _add_currency_codes(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add DocumentCurrencyCode and TaxCurrencyCode."""
        currency = sales_invoice.get('currency', 'JOD')
        
        doc_currency = etree.SubElement(root, "{%s}DocumentCurrencyCode" % self.nsmap['cbc'])
        doc_currency.text = currency
        
        tax_currency = etree.SubElement(root, "{%s}TaxCurrencyCode" % self.nsmap['cbc'])
        tax_currency.text = currency
    
    def _add_icv_document_reference(self, root: etree.Element, icv_counter: int) -> None:
        """Add AdditionalDocumentReference container for ICV."""
        doc_ref = etree.SubElement(root, "{%s}AdditionalDocumentReference" % self.nsmap['cac'])
        
        ref_id = etree.SubElement(doc_ref, "{%s}ID" % self.nsmap['cbc'])
        ref_id.text = "ICV"
        
        ref_uuid = etree.SubElement(doc_ref, "{%s}UUID" % self.nsmap['cbc'])
        ref_uuid.text = str(icv_counter)
    
    def determine_invoice_type_code(self, invoice_data: Dict[str, Any]) -> str:
        """
        Calculate 3-digit invoice type code based on invoice characteristics.
        
        Args:
            invoice_data: Sales Invoice document data
            
        Returns:
            str: 3-digit invoice type code
            
        Logic:
            - Local/Export/Development Area classification
            - Cash/Credit payment terms 
            - Income/General Sales/Special Sales categorization
        """
        # For standard invoices, return 388 as specified
        # Future enhancement: implement 3-digit code logic for Local/Export/Development Area
        # + Cash/Credit + Income/General Sales/Special Sales combinations
        return "388"
    
    def validate_xml_schema(self, xml_content: str) -> Dict[str, Any]:
        """
        Validate generated XML against UBL 2.1 schema.
        
        Args:
            xml_content: XML string to validate
            
        Returns:
            Dict containing validation results:
            - is_valid: bool
            - errors: list of error messages
            - warnings: list of warning messages
        """
        try:
            # Parse XML content
            doc = etree.fromstring(xml_content.encode('utf-8'))
            
            # Basic validation - check required elements exist
            required_elements = [
                './/{%s}ProfileID' % self.nsmap['cbc'],
                './/{%s}ID' % self.nsmap['cbc'], 
                './/{%s}UUID' % self.nsmap['cbc'],
                './/{%s}IssueDate' % self.nsmap['cbc'],
                './/{%s}InvoiceTypeCode' % self.nsmap['cbc'],
                './/{%s}DocumentCurrencyCode' % self.nsmap['cbc'],
                './/{%s}TaxCurrencyCode' % self.nsmap['cbc']
            ]
            
            errors = []
            for xpath in required_elements:
                if doc.find(xpath) is None:
                    element_name = xpath.split('}')[-1]
                    errors.append(f"Required element {element_name} is missing")
            
            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': []
            }
            
        except etree.XMLSyntaxError as e:
            return {
                'is_valid': False,
                'errors': [f"XML Syntax Error: {str(e)}"],
                'warnings': []
            }
        except Exception as e:
            frappe.log_error(f"XML Schema validation failed: {str(e)}", "UBL XML Generator")
            return {
                'is_valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': []
            }
    
    def calculate_line_extension_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal = Decimal('0')) -> Decimal:
        """
        Calculate line extension amount with 9 decimal precision.
        
        Formula: ROUND((quantity * unitPrice) - Discount, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item
            discount: Discount amount
            
        Returns:
            Decimal: Line extension amount rounded to 9 decimal places
        """
        result = (quantity * unit_price) - discount
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
    
    def calculate_tax_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal, tax_percent: Decimal) -> Decimal:
        """
        Calculate tax amount with 9 decimal precision.
        
        Formula: ROUND(((quantity * unitPrice) - discount) * taxPercent, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item  
            discount: Discount amount
            tax_percent: Tax percentage (as decimal, e.g., 0.16 for 16%)
            
        Returns:
            Decimal: Tax amount rounded to 9 decimal places
        """
        taxable_amount = (quantity * unit_price) - discount
        result = taxable_amount * tax_percent
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP)
    
    def calculate_rounding_amount(self, quantity: Decimal, unit_price: Decimal, discount: Decimal, tax_amount: Decimal) -> Decimal:
        """
        Calculate rounding amount with 9 decimal precision.
        
        Formula: ROUND((quantity * unitPrice - discount) + TaxAmount, 9)
        
        Args:
            quantity: Item quantity
            unit_price: Unit price per item
            discount: Discount amount
            tax_amount: Calculated tax amount
            
        Returns:
            Decimal: Rounding amount rounded to 9 decimal places
        """
        base_amount = (quantity * unit_price) - discount
        result = base_amount + tax_amount
        return result.quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP) 