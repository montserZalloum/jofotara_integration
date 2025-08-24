# Jofotara Payer Type Logic Documentation

## Overview

The Jofotara Payer Type logic automatically determines the correct Payer Type for Jordanian sales invoices based on company registration status and item tax templates. This ensures compliance with Jordanian tax regulations without manual intervention.

## Payer Type Values

- **'1'**: Non-registered companies (cannot have tax charges)
- **'2'**: Registered companies with general items
- **'3'**: Registered companies with special tax rate items

## Configuration Requirements

### Company Configuration

1. **Set Company Country**: Ensure the company's country is set to "Jordan"
2. **Tax Registration Status**: Check/uncheck "Registered for Jordanian Sales Tax" field
   - **Checked**: Company is registered for General Sales Tax with Jordan's ISTD
   - **Unchecked**: Company is not registered (Payer Type will be '1')

### Item Tax Template Configuration

1. **General Tax Templates**: Leave "Is Jofotara Special Tax" unchecked
2. **Special Tax Templates**: Check "Is Jofotara Special Tax" for items with special tax rates (e.g., tobacco)

## Logic Flow

### Pre-check
- Only applies to companies with country = "Jordan"
- Non-Jordanian companies are ignored

### Branch 1: Non-registered Companies
- **Condition**: `is_jordan_sales_tax_registered = 0`
- **Result**: Payer Type = '1'
- **Validation**: Cannot have tax charges (`total_taxes_and_charges > 0`)

### Branch 2: Registered Companies
- **Condition**: `is_jordan_sales_tax_registered = 1`
- **Logic**: Check all invoice items for special tax templates
- **Result**: 
  - Payer Type = '3' if any item has `is_jofotara_special_tax = 1`
  - Payer Type = '2' otherwise (general items or zero-rated)

## Validation Rules

### Non-registered Companies
- **Error**: "This company is not registered for sales tax. Invoices cannot include tax charges. Please remove all taxes to proceed."
- **Trigger**: When `total_taxes_and_charges > 0`

### Registered Companies
- **No restrictions**: Can have any combination of tax charges
- **Automatic classification**: Based on item tax templates

## Implementation Details

### Trigger Events
- **Sales Invoice Validate**: Automatically calculates Payer Type on save
- **Sales Invoice Before Submit**: Ensures Payer Type is set before submission

### Field Updates
- **jofotara_payer_type**: Automatically populated with '1', '2', or '3'
- **Read-only**: Users cannot manually edit this field

### Performance Considerations
- Early break in special item detection loop for efficiency
- Minimal impact on existing Sales Invoice operations

## Error Handling

- **Graceful degradation**: Errors are logged but don't block invoice creation
- **User-friendly messages**: Clear validation errors for compliance issues
- **Non-blocking**: System continues to function even if Payer Type calculation fails

## Testing Scenarios

1. **Non-registered + Zero Tax**: Payer Type '1' ✓
2. **Non-registered + Tax**: Validation Error ✓
3. **Registered + General Items**: Payer Type '2' ✓
4. **Registered + Special Items**: Payer Type '3' ✓
5. **Registered + Zero-rated**: Payer Type '2' ✓

## Troubleshooting

### Common Issues

1. **Payer Type not set**: Check if company country is "Jordan"
2. **Validation errors**: Ensure non-registered companies have no tax charges
3. **Wrong Payer Type**: Verify item tax template configurations

### Debug Information

- Check Sales Invoice validation logs for calculation errors
- Verify Company and Item Tax Template field values
- Ensure proper field permissions and access

## Integration Notes

- **Existing functionality**: No impact on current Sales Invoice operations
- **Additive changes**: Only new fields and logic, no modifications to existing
- **Backward compatibility**: Works with existing invoices and configurations
