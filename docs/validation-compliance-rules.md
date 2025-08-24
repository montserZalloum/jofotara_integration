# JoFotara Validation Compliance Rules

## Overview

This document outlines the validation rules implemented to ensure Jordanian tax compliance for companies using the JoFotara integration.

## Enhanced Payer Type Validation for Unregistered Companies

### Background

Based on production testing and compliance requirements, unregistered companies (companies not registered for Jordanian sales tax) cannot include items with special tax templates in their invoices. This validation ensures full compliance with Jordanian tax regulations and prevents potential legal issues or JoFotara system rejection.

### Validation Rules

#### Rule 1: Unregistered Company Special Tax Items Restriction

**Condition:** Company has `jofotara_is_active = checked` AND `is_jordan_sales_tax_registered = unchecked`

**Restriction:** Cannot include items with `is_jofotara_special_tax = checked` in sales invoices

**Validation Trigger:** During invoice save/submit

**Error Message:** 
```
Compliance Violation: Your company is not registered for Jordanian sales tax, 
but this invoice contains items with special tax templates. 
Unregistered companies cannot include items with special tax treatment.

To resolve this issue, you can either:
1. Remove the special tax items from this invoice, or
2. Register your company for Jordanian sales tax in the Company master
```

#### Rule 2: Conditional Validation

**Condition:** Validation only applies when `jofotara_is_active = checked` for the company

**Behavior:** If JoFotara integration is not active, no validation is performed

#### Rule 3: Registered Company Exemption

**Condition:** Company has `is_jordan_sales_tax_registered = checked`

**Behavior:** Registered companies can use special tax templates without restriction

### Implementation Details

#### Server-Side Validation

- **Location:** `apps/jofotara_integration/jofotara_integration/services/validation_service.py`
- **Hook:** Integrated into Sales Invoice validation via `apps/jofotara_integration/jofotara_integration/overrides/sales_invoice.py`
- **Method:** `validate_unregistered_company_special_items()`

#### Frontend Validation

- **Location:** `apps/jofotara_integration/jofotara_integration/public/js/sales_invoice.js`
- **Features:**
  - Real-time validation during item addition
  - Visual indicators for items with special tax templates
  - Immediate feedback for validation violations

### User Experience

#### Visual Indicators

Items with special tax templates are highlighted with:
- Background color: `#fff3cd` (light yellow)
- Left border: `4px solid #ffc107` (warning orange)

#### Real-Time Feedback

- Validation occurs when tax template is changed on invoice items
- Validation occurs when item code is changed
- Error messages are displayed prominently during save/submit

### Resolution Options

When validation fails, users have two options:

1. **Remove Special Tax Items:** Replace items with special tax templates with items using general tax templates
2. **Register Company:** Update the company master to set `is_jordan_sales_tax_registered = checked`

### Technical Implementation

#### Validation Service

```python
class ValidationService:
    def validate_company_item_compliance(self, sales_invoice):
        # Check company registration status
        # Validate special tax items for unregistered companies
        # Return validation result with error message if applicable
```

#### Integration Points

- **Sales Invoice Validation Hook:** Automatically validates during invoice save
- **Frontend JavaScript:** Provides real-time user feedback
- **API Endpoint:** `is_special_tax_template()` for frontend validation

### Testing Scenarios

The validation covers the following scenarios:

1. **Unregistered company + special tax item** → Validation error
2. **Registered company + special tax item** → No error
3. **Unregistered company + general tax item** → No error
4. **Company with jofotara_is_active = unchecked** → No validation
5. **Mixed invoice items (some special, some general)** → Validation error
6. **Credit notes with special tax items** → Validation error

### Backward Compatibility

- Existing functionality for registered companies is preserved
- No changes to existing company setups
- Validation only applies to new compliance requirements

### Error Handling

- Graceful handling of missing or invalid tax templates
- Comprehensive error logging for debugging
- User-friendly error messages with actionable guidance

### Performance Considerations

- Validation is fast enough for real-time user feedback
- Efficient database queries for tax template lookups
- Minimal impact on invoice save/submit performance

## Related Documentation

- [JoFotara Integration Overview](../README.md)
- [Company Configuration Guide](./company-configuration.md)
- [Sales Invoice Workflow](./sales-invoice-workflow.md)
