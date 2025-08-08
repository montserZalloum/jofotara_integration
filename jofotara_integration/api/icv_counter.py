import frappe
from frappe import _
import threading
from contextlib import contextmanager


class ICVCounterManager:
    """
    Atomic ICV Counter Management Service
    Provides thread-safe operations for company-specific Invoice Counter Values
    """
    
    # Thread lock for atomic operations
    _lock = threading.Lock()
    
    def get_next_icv(self, company_name):
        """
        Atomically get next ICV and increment counter for a company
        
        Args:
            company_name (str): Company name
            
        Returns:
            int: Next sequential ICV value
            
        Raises:
            Exception: If company not found or database error occurs
        """
        if not company_name:
            frappe.throw(_("Company name is required"))
        
        with self._atomic_counter_operation():
            try:
                # First check if company exists
                if not frappe.db.exists("Company", company_name):
                    frappe.throw(_("Company {0} not found").format(company_name))
                
                # Use SQL UPDATE with WHERE clause for atomic increment
                # This avoids the potential implicit commit issue
                frappe.db.sql("""
                    UPDATE `tabCompany` 
                    SET current_icv_counter = COALESCE(current_icv_counter, 0) + 1
                    WHERE name = %s
                """, (company_name,))
                
                # Get the updated counter value
                next_icv = frappe.db.get_value("Company", company_name, "current_icv_counter")
                
                if not next_icv:
                    frappe.throw(_("Failed to retrieve updated ICV counter"))
                
                frappe.logger().info(f"ICV Counter: Company {company_name} - assigned ICV {next_icv}")
                
                return int(next_icv)
                
            except frappe.DoesNotExistError:
                frappe.throw(_("Company {0} not found").format(company_name))
            except Exception as e:
                frappe.log_error(
                    f"ICV Counter Error for company {company_name}: {str(e)}",
                    "ICV Counter Management Error"
                )
                frappe.throw(_("Failed to get next ICV counter: {0}").format(str(e)))
    
    def initialize_counter(self, company_name):
        """
        Initialize ICV counter for a new company
        
        Args:
            company_name (str): Company name
            
        Returns:
            bool: True if successfully initialized
        """
        if not company_name:
            frappe.throw(_("Company name is required"))
        
        try:
            # Check if company exists
            if not frappe.db.exists("Company", company_name):
                frappe.throw(_("Company {0} not found").format(company_name))
            
            # Initialize counter to 0 (next will be 1)
            frappe.db.set_value(
                "Company", 
                company_name, 
                "current_icv_counter", 
                0
            )
            
            frappe.logger().info(f"ICV Counter: Initialized for company {company_name}")
            
            return True
            
        except Exception as e:
            frappe.log_error(
                f"ICV Counter Initialization Error for company {company_name}: {str(e)}",
                "ICV Counter Initialization Error"
            )
            frappe.throw(_("Failed to initialize ICV counter: {0}").format(str(e)))
    
    def get_current_counter(self, company_name):
        """
        Get current ICV counter value for a company (read-only)
        
        Args:
            company_name (str): Company name
            
        Returns:
            int: Current counter value
        """
        if not company_name:
            return 0

    def get_assigned_icv(self, sales_invoice_name):
        """
        Get the already assigned ICV for a Sales Invoice, if any.
        
        Args:
            sales_invoice_name (str): Sales Invoice name/ID
        
        Returns:
            int: Assigned ICV value or 0 if not assigned
        """
        if not sales_invoice_name:
            return 0
        try:
            icv = frappe.db.get_value("Sales Invoice", sales_invoice_name, "custom_icv_counter")
            return int(icv or 0)
        except Exception:
            return 0

    def reserve_icv_for_invoice(self, company_name, sales_invoice_name):
        """
        Atomically reserve ICV for a Sales Invoice on first submission attempt.
        If the invoice already has an assigned ICV (> 0), it is returned unchanged.
        
        This method increments the Company's current_icv_counter and writes the
        reserved value to Sales Invoice.custom_icv_counter in the same locked
        section to ensure idempotency and avoid race conditions.
        
        Args:
            company_name (str): Company name
            sales_invoice_name (str): Sales Invoice name/ID
        
        Returns:
            int: The assigned ICV value for this invoice
        """
        if not company_name:
            frappe.throw(_("Company name is required"))
        if not sales_invoice_name:
            frappe.throw(_("Sales Invoice name is required"))

        with self._atomic_counter_operation():
            # Re-check if already assigned to ensure idempotency
            already_assigned = self.get_assigned_icv(sales_invoice_name)
            if already_assigned and already_assigned > 0:
                return already_assigned

            # Validate existence
            if not frappe.db.exists("Company", company_name):
                frappe.throw(_("Company {0} not found").format(company_name))
            if not frappe.db.exists("Sales Invoice", sales_invoice_name):
                frappe.throw(_("Sales Invoice {0} not found").format(sales_invoice_name))

            # Increment company counter atomically
            frappe.db.sql(
                """
                UPDATE `tabCompany`
                SET current_icv_counter = COALESCE(current_icv_counter, 0) + 1
                WHERE name = %s
                """,
                (company_name,)
            )

            next_icv = frappe.db.get_value("Company", company_name, "current_icv_counter")
            if not next_icv:
                frappe.throw(_("Failed to retrieve updated ICV counter"))

            # Persist ICV to invoice
            frappe.db.set_value(
                "Sales Invoice",
                sales_invoice_name,
                "custom_icv_counter",
                int(next_icv),
                update_modified=False,
            )

            frappe.logger().info(
                f"ICV Reservation: Invoice {sales_invoice_name} assigned ICV {next_icv} for company {company_name}"
            )
            return int(next_icv)
        
        try:
            company_doc = frappe.get_doc("Company", company_name)
            return int(company_doc.get("current_icv_counter") or 0)
        except:
            return 0
    
    def validate_counter_integrity(self, company_name):
        """
        Validate counter state consistency for a company
        
        Args:
            company_name (str): Company name
            
        Returns:
            dict: Validation results with integrity status and details
        """
        try:
            # Get current counter value
            current_counter = self.get_current_counter(company_name)
            
            # Get highest ICV value from submitted invoices
            max_icv_in_invoices = frappe.db.sql("""
                SELECT COALESCE(MAX(custom_icv_counter), 0) as max_icv
                FROM `tabSales Invoice`
                WHERE company = %s 
                AND docstatus = 1 
                AND custom_icv_counter IS NOT NULL
                AND custom_icv_counter > 0
            """, [company_name], as_dict=True)
            
            max_icv = max_icv_in_invoices[0].get("max_icv", 0) if max_icv_in_invoices else 0
            
            # Validation: current_counter should be >= max_icv in invoices
            is_valid = current_counter >= max_icv
            
            result = {
                "company": company_name,
                "current_counter": current_counter,
                "max_icv_in_invoices": max_icv,
                "is_valid": is_valid,
                "discrepancy": current_counter - max_icv if not is_valid else 0
            }
            
            if not is_valid:
                frappe.log_error(
                    f"ICV Counter Integrity Issue: {result}",
                    "ICV Counter Integrity Check"
                )
            
            return result
            
        except Exception as e:
            frappe.log_error(
                f"ICV Counter Integrity Check Error for company {company_name}: {str(e)}",
                "ICV Counter Integrity Error"
            )
            return {
                "company": company_name,
                "current_counter": 0,
                "max_icv_in_invoices": 0,
                "is_valid": False,
                "error": str(e)
            }
    
    @contextmanager
    def _atomic_counter_operation(self):
        """
        Context manager for atomic counter operations with proper locking
        """
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()


# Global instance for use across the application
icv_counter_manager = ICVCounterManager()


@frappe.whitelist()
def get_next_icv_for_company(company_name):
    """
    API endpoint to get next ICV for a company
    
    Args:
        company_name (str): Company name
        
    Returns:
        dict: Response with next ICV value
    """
    try:
        if not frappe.has_permission("Company", "read"):
            frappe.throw(_("Insufficient permissions"))
        
        next_icv = icv_counter_manager.get_next_icv(company_name)
        
        return {
            "success": True,
            "company": company_name,
            "next_icv": next_icv
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def get_assigned_icv(sales_invoice_name):
    """
    API endpoint to get assigned ICV for a Sales Invoice (0 if none)
    """
    try:
        if not frappe.has_permission("Sales Invoice", "read"):
            frappe.throw(_("Insufficient permissions"))
        value = icv_counter_manager.get_assigned_icv(sales_invoice_name)
        return {"success": True, "assigned_icv": value}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def reserve_icv_for_invoice(company_name, sales_invoice_name):
    """
    API endpoint to reserve ICV for a Sales Invoice if not already assigned
    """
    try:
        if not frappe.has_permission("Sales Invoice", "write"):
            frappe.throw(_("Insufficient permissions"))
        icv = icv_counter_manager.reserve_icv_for_invoice(company_name, sales_invoice_name)
        return {"success": True, "assigned_icv": icv}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def initialize_company_counter(company_name):
    """
    API endpoint to initialize counter for a company
    
    Args:
        company_name (str): Company name
        
    Returns:
        dict: Response with initialization status
    """
    try:
        if not frappe.has_permission("Company", "write"):
            frappe.throw(_("Insufficient permissions"))
        
        success = icv_counter_manager.initialize_counter(company_name)
        
        return {
            "success": success,
            "company": company_name,
            "message": _("ICV counter initialized successfully")
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@frappe.whitelist()
def validate_counter_integrity(company_name):
	"""
	API endpoint to validate counter integrity for a company
	
	Args:
		company_name (str): Company name
		
	Returns:
		dict: Validation results
	"""
	try:
		if not frappe.has_permission("Company", "read"):
			frappe.throw(_("Insufficient permissions"))
		
		result = icv_counter_manager.validate_counter_integrity(company_name)
		result["success"] = True
		
		return result
		
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}


def validate_all_company_counters():
	"""
	Validate counter integrity for all companies with JoFotara enabled
	Used during system startup and maintenance
	
	Returns:
		dict: Overall validation results
	"""
	try:
		# Get all companies with JoFotara integration enabled
		companies = frappe.db.sql("""
			SELECT name, company_name
			FROM `tabCompany`
			WHERE jofotara_is_active = 1
		""", as_dict=True)
		
		results = []
		overall_status = True
		
		for company in companies:
			company_name = company.get("name")
			validation_result = icv_counter_manager.validate_counter_integrity(company_name)
			results.append(validation_result)
			
			if not validation_result.get("is_valid", False):
				overall_status = False
				frappe.log_error(
					f"Counter integrity issue found for company {company_name}: {validation_result}",
					"ICV Counter System Validation"
				)
		
		summary = {
			"overall_valid": overall_status,
			"companies_checked": len(companies),
			"detailed_results": results,
			"timestamp": frappe.utils.now()
		}
		
		if overall_status:
			frappe.logger().info(f"ICV Counter System: All {len(companies)} companies passed integrity check")
		else:
			frappe.logger().warning(f"ICV Counter System: Integrity issues found - check error logs")
		
		return summary
		
	except Exception as e:
		frappe.log_error(
			f"ICV Counter System Validation Error: {str(e)}",
			"ICV Counter System Validation Error"
		)
		return {
			"overall_valid": False,
			"error": str(e),
			"timestamp": frappe.utils.now()
		}


@frappe.whitelist()
def system_startup_validation():
	"""
	API endpoint for system startup counter validation
	
	Returns:
		dict: System validation results
	"""
	try:
		if not frappe.has_permission("Company", "read"):
			frappe.throw(_("Insufficient permissions"))
		
		return validate_all_company_counters()
		
	except Exception as e:
		return {
			"success": False,
			"error": str(e)
		}
