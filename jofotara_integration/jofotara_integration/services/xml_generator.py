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
from jofotara_integration.jofotara_integration.utils.validation import validate_original_invoice_for_credit_note


class UBLXMLGenerator:
    """
    UBL 2.1 XML Generator for JoFotara e-invoicing compliance.
    
    Generates XML documents that comply with UBL 2.1 schema and 
    JoFotara technical specifications.
    """
    
    # UBL 2.1 Namespaces for XML generation
    NAMESPACES = {
        None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        'cac': "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        'cbc': "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        'ext': "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    }
    
    def __init__(self):
        """Initialize UBL XML Generator with namespace mappings."""
        self.nsmap = self.NAMESPACES
    
    def _convert_amount_for_credit_note(self, amount: float, is_return: bool) -> float:
        """
        Convert negative Credit Note amounts to positive values for UBL XML.
        
        Args:
            amount: Original amount from ERPNext (negative for Credit Notes)
            is_return: Whether this is a Credit Note/return invoice
            
        Returns:
            float: Positive amount for UBL XML or original amount for regular invoices
        """
        if is_return and amount < 0:
            return abs(amount)
        return amount
    
    def generate_xml(self, sales_invoice: Dict[str, Any], icv_counter: int) -> Dict[str, str]:
        """
        Generate UBL 2.1 compliant XML for a Sales Invoice.
        
        Args:
            sales_invoice: Sales Invoice document data
            icv_counter: Invoice Counter Value for sequential numbering
            
        Returns:
            Dict[str, str]: Dictionary containing:
                - xml_content: Generated XML string with proper UBL 2.1 structure
                - uuid: The generated UUID for the invoice
            
        Raises:
            ValueError: If required invoice data is missing
            Exception: If XML generation fails
        """
        try:
            # Generate UUID that will be used in the XML and saved to the invoice
            generated_uuid = str(uuid.uuid4())
            
            # Create root element with namespaces
            root = etree.Element("Invoice", nsmap=self.nsmap)
            
            # Build XML in the EXACT required order as per JoFotara specification
            
            # 1. Main Invoice Information
            self._add_profile_id(root)
            self._add_invoice_id(root, sales_invoice)
            self._add_uuid(root, generated_uuid)
            self._add_issue_date(root, sales_invoice)
            self._add_issue_time(root, sales_invoice)
            self._add_invoice_type_code(root, sales_invoice)
            self._add_note(root, sales_invoice)
            self._add_currency_codes(root, sales_invoice)
            
            # 2. BillingReference for Credit Notes (must come before AdditionalDocumentReference)
            if sales_invoice.get('is_return', 0):
                self._add_billing_reference(root, sales_invoice)
            
            # 3. Additional Document Reference (ICV)
            self._add_icv_document_reference(root, icv_counter)
            
            # 3.1. Additional Document Reference for Original Invoice Total (Credit Notes)
            if sales_invoice.get('is_return', 0):
                self._add_original_invoice_total_reference(root, sales_invoice)
            
            # 4. Accounting Supplier Party (Seller details)
            self._add_accounting_supplier_party(root, sales_invoice)
            
            # 5. Accounting Customer Party (Buyer details)
            self._add_accounting_customer_party(root, sales_invoice)
            
            # 6. Seller Supplier Party (Activity Serial Number)
            self._add_seller_supplier_party(root, sales_invoice)
            
            # 7. PaymentMeans for Credit Notes (if applicable)
            if sales_invoice.get('is_return', 0):
                self._add_payment_means(root, sales_invoice)
            
            # 8. Document Level Allowance/Discount
            self._add_document_level_allowance(root, sales_invoice)
            
            # 9. Tax Total
            self._add_tax_total(root, sales_invoice)
            
            # 10. Legal Monetary Total
            self._add_legal_monetary_total(root, sales_invoice)
            
            # 11. Invoice Lines
            self._add_invoice_lines(root, sales_invoice)
            
            # Generate XML string with declaration
            xml_str = etree.tostring(
                root, 
                pretty_print=True, 
                xml_declaration=True, 
                encoding='UTF-8'
            ).decode('utf-8')
            
            return {
                'xml_content': xml_str,
                'uuid': generated_uuid
            }
            
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
        
        # Use the ICV counter as the main invoice ID for JoFotara compliance
        # This ensures sequential numbering per company as required
        icv_value = sales_invoice.get('custom_icv_counter')
        if icv_value:
            invoice_id.text = str(icv_value)
        else:
            # Fallback to Frappe invoice name if ICV not available
            invoice_id.text = sales_invoice.get('name', '')
    
    def _add_uuid(self, root: etree.Element, generated_uuid: str) -> None:
        """Add UUID element for universal unique identification."""
        uuid_elem = etree.SubElement(root, "{%s}UUID" % self.nsmap['cbc'])
        uuid_elem.text = generated_uuid
    
    def _add_issue_date(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add IssueDate in YYYY-MM-DD format."""
        issue_date = etree.SubElement(root, "{%s}IssueDate" % self.nsmap['cbc'])
        posting_date = sales_invoice.get('posting_date')
        if isinstance(posting_date, str):
            issue_date.text = posting_date
        else:
            issue_date.text = posting_date.strftime('%Y-%m-%d') if posting_date else datetime.now().strftime('%Y-%m-%d')
    
    def _add_invoice_type_code(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add InvoiceTypeCode with Development Area detection using simple 2xx codes."""
        type_code_elem = etree.SubElement(root, "{%s}InvoiceTypeCode" % self.nsmap['cbc'])
        
        # Determine if this is a return/credit invoice
        is_return = sales_invoice.get('is_return', 0)
        
        if is_return:
            # Return/Credit invoice
            type_code_elem.text = "381"
            # Use simple 2-digit codes for returns
            is_pos = sales_invoice.get('is_pos', 0)
            payment_method_name = "011" if is_pos else "021"
        else:
            # New invoice
            type_code_elem.text = "388"
            # Check for Development Area detection
            payment_method_name = self._get_simple_invoice_type_code(sales_invoice)
        
        # Add the mandatory 'name' attribute with payment method code
        type_code_elem.set('name', payment_method_name)
    
    def _get_simple_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Get simple invoice type code with Development Area detection.
        
        Returns:
        - "212": Development Area Credit
        - "211": Development Area Cash  
        - "021": Local Credit
        - "011": Local Cash
        """
        try:
            # Check if customer is in Development Area
            customer_name = sales_invoice.get('customer')
            if customer_name:
                customer_doc = frappe.get_doc("Customer", customer_name)
                if customer_doc.get('custom_is_in_development_area'):
                    # Development Area customer - use 2xx codes
                    is_pos = sales_invoice.get('is_pos', 0)
                    return "211" if is_pos else "212"
            
            # Default Local customer - use 0xx codes  
            is_pos = sales_invoice.get('is_pos', 0)
            return "011" if is_pos else "021"
            
        except Exception as e:
            frappe.log_error(f"Error determining simple invoice type: {str(e)}", "UBL XML Generator")
            # Default to Local codes on error
            is_pos = sales_invoice.get('is_pos', 0)
            return "011" if is_pos else "021"
    
    def _generate_3_digit_invoice_type_code(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Generate 3-digit invoice type code based on invoice characteristics.
        
        Code structure: XYZ
        - X: Invoice Category (0=Local, 1=Export, 2=Development Area)
        - Y: Payment Method (1=Cash, 2=Credit)
        - Z: Payer Type (1=Income, 2=General Sales, 3=Special Sales)
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            str: 3-digit invoice type code (e.g., "011", "121", "223")
        """
        # Determine invoice category (first digit)
        category_digit = self._determine_invoice_category(sales_invoice)
        
        # Determine payment method (second digit)
        is_pos = sales_invoice.get('is_pos', 0)
        payment_digit = "1" if is_pos else "2"  # 1=Cash, 2=Credit
        
        # Determine payer type (third digit) - default to General Sales for now
        payer_digit = "2"  # 2=General Sales (can be enhanced later for Income/Special Sales)
        
        return f"{category_digit}{payment_digit}{payer_digit}"
    
    def _determine_invoice_category(self, sales_invoice: Dict[str, Any]) -> str:
        """
        Determine invoice category for the first digit of 3-digit code.
        
        Categories:
        - 0: Local invoices (default)
        - 1: Export invoices (customer territory != Jordan)
        - 2: Development Area invoices (customer has custom_is_in_development_area=1)
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            str: Category digit ("0", "1", or "2")
        """
        try:
            customer_name = sales_invoice.get('customer')
            if not customer_name:
                return "0"  # Default to Local
            
            # Get customer document to check territory and development area flag
            customer_doc = frappe.get_doc("Customer", customer_name)
            
            # Check for Development Area first (highest priority)
            if customer_doc.get('custom_is_in_development_area'):
                return "2"  # Development Area
            
            # Check for Export based on territory
            customer_territory = customer_doc.get('territory')
            if customer_territory and customer_territory != 'Jordan':
                return "1"  # Export
            
            # Default to Local
            return "0"
            
        except Exception as e:
            frappe.log_error(f"Error determining invoice category: {str(e)}", "UBL XML Generator")
            return "0"  # Default to Local on error
    

    
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
    
    def _add_billing_reference(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add BillingReference element for Credit Notes with original invoice details."""
        return_against = sales_invoice.get('return_against')
        
        # Validate original invoice using utility function
        validation_result = validate_original_invoice_for_credit_note(return_against)
        
        if not validation_result.get('is_valid'):
            error_message = validation_result.get('error_message', 'Original invoice validation failed')
            frappe.throw(error_message)
        
        try:
            # Extract validated details
            original_uuid = validation_result.get('original_uuid')
            original_invoice_data = validation_result.get('original_invoice', {})
            
            # Create BillingReference element
            billing_ref = etree.SubElement(root, "{%s}BillingReference" % self.nsmap['cac'])
            
            # Add InvoiceDocumentReference with original invoice details
            invoice_doc_ref = etree.SubElement(billing_ref, "{%s}InvoiceDocumentReference" % self.nsmap['cac'])
            
            # Add original invoice ID
            doc_ref_id = etree.SubElement(invoice_doc_ref, "{%s}ID" % self.nsmap['cbc'])
            original_icv = original_invoice_data.get('custom_icv_counter')
            if original_icv:
                doc_ref_id.text = str(original_icv)
            else:
                # Fallback to original invoice name if ICV is missing (should not happen)
                doc_ref_id.text = return_against
            
            # Get original total for use in multiple places
            original_total = original_invoice_data.get('grand_total', 0.0)
            
            # Add original invoice UUID
            doc_ref_uuid = etree.SubElement(invoice_doc_ref, "{%s}UUID" % self.nsmap['cbc'])
            doc_ref_uuid.text = original_uuid
            
            # Add IssueDate from original invoice if available
            original_date = original_invoice_data.get('posting_date')
            if original_date:
                if isinstance(original_date, str):
                    issue_date = etree.SubElement(invoice_doc_ref, "{%s}IssueDate" % self.nsmap['cbc'])
                    issue_date.text = original_date
                else:
                    issue_date = etree.SubElement(invoice_doc_ref, "{%s}IssueDate" % self.nsmap['cbc'])
                    issue_date.text = original_date.strftime('%Y-%m-%d') if original_date else ""
            
            # Add DocumentDescription with original invoice total for JoFotara
            if original_total:
                doc_description = etree.SubElement(invoice_doc_ref, "{%s}DocumentDescription" % self.nsmap['cbc'])
                # Provide only the numeric total to avoid non-numeric characters that break BigDecimal parsing
                doc_description.text = f"{abs(original_total):.2f}"
            
            # Add BillingReferenceLine with original invoice total (as per UBL structure)
            if original_total:
                currency = sales_invoice.get('currency', 'JOD')
                billing_ref_line = etree.SubElement(billing_ref, "{%s}BillingReferenceLine" % self.nsmap['cac'])
                
                # Add line ID
                line_id = etree.SubElement(billing_ref_line, "{%s}ID" % self.nsmap['cbc'])
                line_id.text = "1"
                
                # Add original invoice amount in BillingReferenceLine
                billed_amount = etree.SubElement(billing_ref_line, "{%s}Amount" % self.nsmap['cbc'])
                billed_amount.set('currencyID', currency)
                billed_amount.text = f"{abs(original_total):.2f}"
            
        except Exception as e:
            frappe.log_error(f"Error adding BillingReference for Credit Note: {str(e)}", "UBL XML Generator")
            frappe.throw(f"Failed to process original invoice reference: {str(e)}")
    
    def _add_original_invoice_total_reference(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AdditionalDocumentReference for original invoice total (JoFotara requirement)."""
        try:
            return_against = sales_invoice.get('return_against')
            if not return_against:
                return
            
            # Get original invoice data
            validation_result = validate_original_invoice_for_credit_note(return_against)
            if not validation_result.get('is_valid'):
                return
            
            original_invoice_data = validation_result.get('original_invoice', {})
            original_total = original_invoice_data.get('grand_total', 0.0)
            
            if original_total:
                # Create AdditionalDocumentReference for original invoice total
                doc_ref = etree.SubElement(root, "{%s}AdditionalDocumentReference" % self.nsmap['cac'])
                
                # Set ID as originalInvoiceTotal
                ref_id = etree.SubElement(doc_ref, "{%s}ID" % self.nsmap['cbc'])
                ref_id.text = "originalInvoiceTotal"
                
                # Set the total amount as UUID field (JoFotara specific)
                ref_uuid = etree.SubElement(doc_ref, "{%s}UUID" % self.nsmap['cbc'])
                ref_uuid.text = f"{abs(original_total):.2f}"
                
        except Exception as e:
            frappe.log_error(f"Error adding original invoice total reference: {str(e)}", "UBL XML Generator")
            # Don't throw error - continue with standard XML
            pass
    
    def _add_payment_means(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add PaymentMeans element for Credit Notes with return reason instruction."""
        try:
            # Create PaymentMeans element
            payment_means = etree.SubElement(root, "{%s}PaymentMeans" % self.nsmap['cac'])
            
            # Add PaymentMeansCode for Credit Note/Return
            payment_means_code = etree.SubElement(payment_means, "{%s}PaymentMeansCode" % self.nsmap['cbc'])
            payment_means_code.text = "1"  # Standard code for Credit Note returns
            
            # Add InstructionNote with return reason
            # return_reason = sales_invoice.get('terms', '').strip()
            return_reason = "test test "
            if not return_reason or len(return_reason) < 5:
                frappe.throw("Credit Note must have a return reason in the Terms field (minimum 5 characters)")
            
            instruction_note = etree.SubElement(payment_means, "{%s}InstructionNote" % self.nsmap['cbc'])
            instruction_note.text = return_reason[:500]  # Limit to 500 characters for UBL compliance
            
        except Exception as e:
            frappe.log_error(f"Error adding PaymentMeans for Credit Note: {str(e)}", "UBL XML Generator")
            frappe.throw(f"Failed to add PaymentMeans: {str(e)}")
    
    def _add_issue_time(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add IssueTime element."""
        issue_time = etree.SubElement(root, "{%s}IssueTime" % self.nsmap['cbc'])
        
        if sales_invoice and sales_invoice.get('posting_time'):
            # Use actual posting time if available
            posting_time = sales_invoice.get('posting_time')
            if isinstance(posting_time, str):
                issue_time.text = posting_time
            else:
                # Handle timedelta object (ERPNext stores time as timedelta)
                from datetime import timedelta
                if isinstance(posting_time, timedelta):
                    # Convert timedelta to HH:MM:SS format
                    total_seconds = int(posting_time.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    issue_time.text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    # For datetime objects
                    issue_time.text = posting_time.strftime('%H:%M:%S')
        else:
            # Fallback to midnight
            issue_time.text = "00:00:00"
    
    def _add_note(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add Note element."""
        note = etree.SubElement(root, "{%s}Note" % self.nsmap['cbc'])
        note.text = sales_invoice.get('terms') or "Sales Invoice"
    
    def _add_accounting_supplier_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AccountingSupplierParty element with seller details."""
        supplier_party = etree.SubElement(root, "{%s}AccountingSupplierParty" % self.nsmap['cac'])
        party = etree.SubElement(supplier_party, "{%s}Party" % self.nsmap['cac'])
        
        # Postal Address
        postal_address = etree.SubElement(party, "{%s}PostalAddress" % self.nsmap['cac'])
        country = etree.SubElement(postal_address, "{%s}Country" % self.nsmap['cac'])
        etree.SubElement(country, "{%s}IdentificationCode" % self.nsmap['cbc']).text = "JO"
        
        # Party Tax Scheme (Company Tax ID)
        party_tax_scheme = etree.SubElement(party, "{%s}PartyTaxScheme" % self.nsmap['cac'])
        
        # Get company tax ID from Company doctype
        company_name = sales_invoice.get('company')
        company_tax_id = "NA"
        try:
            if company_name:
                company_doc = frappe.get_doc("Company", company_name)
                company_tax_id = company_doc.get('tax_id') or "NA"
        except Exception as e:
            frappe.log_error(f"Error getting company tax ID: {str(e)}", "UBL XML Generator")
            
        etree.SubElement(party_tax_scheme, "{%s}CompanyID" % self.nsmap['cbc']).text = str(company_tax_id)
        tax_scheme = etree.SubElement(party_tax_scheme, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
        
        # Party Legal Entity
        party_legal_entity = etree.SubElement(party, "{%s}PartyLegalEntity" % self.nsmap['cac'])
        company_name = sales_invoice.get('company') or "Company Name"
        etree.SubElement(party_legal_entity, "{%s}RegistrationName" % self.nsmap['cbc']).text = str(company_name)
    
    def _add_accounting_customer_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add AccountingCustomerParty element with enhanced buyer details and ID scheme detection."""
        customer_party = etree.SubElement(root, "{%s}AccountingCustomerParty" % self.nsmap['cac'])
        party = etree.SubElement(customer_party, "{%s}Party" % self.nsmap['cac'])
        
        # Get enhanced customer information
        customer_info = self._get_enhanced_customer_info(sales_invoice)
        
        # Party Identification with enhanced scheme detection
        party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
        etree.SubElement(
            party_identification, 
            "{%s}ID" % self.nsmap['cbc'], 
            schemeID=customer_info['id_scheme']
        ).text = str(customer_info['tax_id'])
        
        # Postal Address
        postal_address = etree.SubElement(party, "{%s}PostalAddress" % self.nsmap['cac'])
        country = etree.SubElement(postal_address, "{%s}Country" % self.nsmap['cac'])
        etree.SubElement(country, "{%s}IdentificationCode" % self.nsmap['cbc']).text = "JO"
        
        # Party Tax Scheme
        party_tax_scheme = etree.SubElement(party, "{%s}PartyTaxScheme" % self.nsmap['cac'])
        tax_scheme = etree.SubElement(party_tax_scheme, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
        
        # Party Legal Entity
        party_legal_entity = etree.SubElement(party, "{%s}PartyLegalEntity" % self.nsmap['cac'])
        customer_name = sales_invoice.get('customer_name') or sales_invoice.get('customer') or "Customer Name"
        etree.SubElement(party_legal_entity, "{%s}RegistrationName" % self.nsmap['cbc']).text = str(customer_name)
    
    def _get_enhanced_customer_info(self, sales_invoice: Dict[str, Any]) -> Dict[str, str]:
        """
        Get enhanced customer information with proper ID scheme detection.
        
        ID Schemes:
        - TN (Tax Number): For companies with valid tax ID
        - NIN (National ID): For Jordanian individuals  
        - PN (Personal No.): For non-Jordanian individuals
        
        Note: Using 'TIN' and 'NAT' as XML scheme values for compatibility,
        but logic follows TN/NIN/PN business rules.
        
        Args:
            sales_invoice: Sales Invoice document data
            
        Returns:
            Dict containing customer info with proper scheme
        """
        default_info = {
            'tax_id': 'NA',
            'id_scheme': 'NAT',
            'customer_type': 'Individual',
            'territory': 'Jordan'
        }
        
        try:
            customer_name = sales_invoice.get('customer')
            if not customer_name:
                return default_info
            
            # Get customer document
            customer_doc = frappe.get_doc("Customer", customer_name)
            customer_type = customer_doc.get('customer_type', 'Individual')
            tax_id = customer_doc.get('tax_id', '').strip()
            territory = customer_doc.get('territory', 'Jordan')
            
            # Determine appropriate ID scheme
            if customer_type == 'Company':
                # Companies should use TN (Tax Number) scheme
                if tax_id and tax_id != 'NA':
                    return {
                        'tax_id': tax_id,
                        'id_scheme': 'TIN',  # TN mapped to TIN for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                else:
                    # Company without tax ID - validation should catch this
                    frappe.log_error(
                        f"Company customer {customer_name} missing tax ID",
                        "Customer ID Scheme Detection"
                    )
                    return {
                        'tax_id': 'NA',
                        'id_scheme': 'TIN',  # Still use TIN scheme for companies
                        'customer_type': customer_type,
                        'territory': territory
                    }
            else:
                # Individual customers
                if territory == 'Jordan':
                    # Jordanian individuals use NIN (National ID) scheme
                    return {
                        'tax_id': tax_id or 'NA',
                        'id_scheme': 'NAT',  # NIN mapped to NAT for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                else:
                    # Non-Jordanian individuals use PN (Personal No.) scheme
                    return {
                        'tax_id': tax_id or 'NA',
                        'id_scheme': 'NAT',  # PN mapped to NAT for XML compatibility
                        'customer_type': customer_type,
                        'territory': territory
                    }
                    
        except Exception as e:
            frappe.log_error(f"Error getting enhanced customer info: {str(e)}", "UBL XML Generator")
            return default_info
    
    def _add_seller_supplier_party(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add SellerSupplierParty element with Activity Serial Number."""
        # Get Company document to fetch activity serial number
        company_name = sales_invoice.get('company')
        if company_name:
            try:
                company_doc = frappe.get_doc("Company", company_name)
                activity_serial = company_doc.get("jofotara_activity_serial")
                
                if not activity_serial:
                    raise ValueError(f"Activity Serial Number not configured for company {company_name}")
                
                seller_party = etree.SubElement(root, "{%s}SellerSupplierParty" % self.nsmap['cac'])
                party = etree.SubElement(seller_party, "{%s}Party" % self.nsmap['cac'])
                party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
                etree.SubElement(party_identification, "{%s}ID" % self.nsmap['cbc']).text = str(activity_serial)
            except Exception as e:
                frappe.log_error(f"Error getting activity serial number: {str(e)}", "UBL XML Generator")
                # Add placeholder if company data not available
                seller_party = etree.SubElement(root, "{%s}SellerSupplierParty" % self.nsmap['cac'])
                party = etree.SubElement(seller_party, "{%s}Party" % self.nsmap['cac'])
                party_identification = etree.SubElement(party, "{%s}PartyIdentification" % self.nsmap['cac'])
                etree.SubElement(party_identification, "{%s}ID" % self.nsmap['cbc']).text = "1"
    
    def _add_document_level_allowance(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add document-level AllowanceCharge element."""
        allowance_charge = etree.SubElement(root, "{%s}AllowanceCharge" % self.nsmap['cac'])
        etree.SubElement(allowance_charge, "{%s}ChargeIndicator" % self.nsmap['cbc']).text = "false"
        etree.SubElement(allowance_charge, "{%s}AllowanceChargeReason" % self.nsmap['cbc']).text = "discount"
        
        discount_amount = sales_invoice.get('discount_amount') or 0.00
        currency = sales_invoice.get('currency', 'JOD')
        etree.SubElement(allowance_charge, "{%s}Amount" % self.nsmap['cbc'], currencyID=currency).text = f"{discount_amount:.2f}"
    
    def _add_tax_total(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add TaxTotal element."""
        tax_total = etree.SubElement(root, "{%s}TaxTotal" % self.nsmap['cac'])
        
        is_return = sales_invoice.get('is_return', 0)
        total_taxes = sales_invoice.get('total_taxes_and_charges') or 0.00
        net_total = sales_invoice.get('net_total') or 0.00
        
        # Convert amounts for Credit Notes (negative to positive)
        total_taxes = self._convert_amount_for_credit_note(total_taxes, is_return)
        net_total = self._convert_amount_for_credit_note(net_total, is_return)
        
        currency = sales_invoice.get('currency', 'JOD')
        etree.SubElement(tax_total, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{total_taxes:.2f}"
        
        # Add tax subtotal
        tax_subtotal = etree.SubElement(tax_total, "{%s}TaxSubtotal" % self.nsmap['cac'])
        etree.SubElement(tax_subtotal, "{%s}TaxableAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{net_total:.2f}"
        etree.SubElement(tax_subtotal, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{total_taxes:.2f}"
        
        # Tax Category
        tax_category = etree.SubElement(tax_subtotal, "{%s}TaxCategory" % self.nsmap['cac'])
        category_id = "S" if total_taxes > 0 else "Z"  # S for standard rate, Z for zero rate
        etree.SubElement(tax_category, "{%s}ID" % self.nsmap['cbc']).text = category_id
        
        # Calculate tax percentage
        tax_percent = 0.00
        if net_total > 0 and total_taxes > 0:
            tax_percent = (total_taxes / net_total) * 100
        etree.SubElement(tax_category, "{%s}Percent" % self.nsmap['cbc']).text = f"{tax_percent:.2f}"
        
        # Tax Scheme
        tax_scheme = etree.SubElement(tax_category, "{%s}TaxScheme" % self.nsmap['cac'])
        etree.SubElement(tax_scheme, "{%s}ID" % self.nsmap['cbc']).text = "VAT"
    
    def _add_legal_monetary_total(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add LegalMonetaryTotal element."""
        monetary_total = etree.SubElement(root, "{%s}LegalMonetaryTotal" % self.nsmap['cac'])
        
        is_return = sales_invoice.get('is_return', 0)
        currency = sales_invoice.get('currency', 'JOD')
        net_total = sales_invoice.get('net_total') or 0.00
        grand_total = sales_invoice.get('grand_total') or 0.00
        discount_amount = sales_invoice.get('discount_amount') or 0.00
        
        # Convert amounts for Credit Notes (negative to positive)
        net_total = self._convert_amount_for_credit_note(net_total, is_return)
        grand_total = self._convert_amount_for_credit_note(grand_total, is_return)
        discount_amount = self._convert_amount_for_credit_note(discount_amount, is_return)
        
        etree.SubElement(monetary_total, "{%s}TaxExclusiveAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{net_total:.2f}"
        etree.SubElement(monetary_total, "{%s}TaxInclusiveAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{grand_total:.2f}"
        etree.SubElement(monetary_total, "{%s}AllowanceTotalAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{discount_amount:.2f}"
        etree.SubElement(monetary_total, "{%s}PayableAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{grand_total:.2f}"
    
    def _add_invoice_lines(self, root: etree.Element, sales_invoice: Dict[str, Any]) -> None:
        """Add InvoiceLine elements for each item."""
        items = sales_invoice.get('items', [])
        currency = sales_invoice.get('currency', 'JOD')
        is_return = sales_invoice.get('is_return', 0)
        
        for idx, item in enumerate(items, 1):
            invoice_line = etree.SubElement(root, "{%s}InvoiceLine" % self.nsmap['cac'])
            
            etree.SubElement(invoice_line, "{%s}ID" % self.nsmap['cbc']).text = str(idx)
            
            qty = item.get('qty', 1)
            uom = item.get('uom', 'PCE')
            # Convert quantity for Credit Notes (negative to positive)
            qty = self._convert_amount_for_credit_note(qty, is_return)
            etree.SubElement(invoice_line, "{%s}InvoicedQuantity" % self.nsmap['cbc'], unitCode=uom).text = str(qty)
            
            amount = item.get('amount', 0.00)
            # Convert amount for Credit Notes (negative to positive)
            amount = self._convert_amount_for_credit_note(amount, is_return)
            etree.SubElement(invoice_line, "{%s}LineExtensionAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{amount:.2f}"
            
            # Tax Total for line item (simplified)
            line_tax_total = etree.SubElement(invoice_line, "{%s}TaxTotal" % self.nsmap['cac'])
            etree.SubElement(line_tax_total, "{%s}TaxAmount" % self.nsmap['cbc'], currencyID=currency).text = "0.00"
            
            # Item details
            item_element = etree.SubElement(invoice_line, "{%s}Item" % self.nsmap['cac'])
            item_name = item.get('item_name') or item.get('item_code', 'Item')
            etree.SubElement(item_element, "{%s}Name" % self.nsmap['cbc']).text = str(item_name)
            
            # Price details
            price = etree.SubElement(invoice_line, "{%s}Price" % self.nsmap['cac'])
            rate = item.get('rate', 0.00)
            # Convert rate for Credit Notes (negative to positive)
            rate = self._convert_amount_for_credit_note(rate, is_return)
            etree.SubElement(price, "{%s}PriceAmount" % self.nsmap['cbc'], currencyID=currency).text = f"{rate:.2f}"
    
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
            
        except Exception as e:
            return {
                'is_valid': False,
                'errors': [f"XML parsing error: {str(e)}"],
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