import unittest
import threading
import time
import frappe
from concurrent.futures import ThreadPoolExecutor, as_completed
from jofotara_integration.api.icv_counter import ICVCounterManager


class TestCounterConcurrency(unittest.TestCase):
    """Integration tests for ICV counter concurrency and race conditions"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test data"""
        # Create test company with JoFotara enabled
        cls.test_company = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test Concurrency Company",
            "abbr": "TCC",
            "default_currency": "USD",
            "jofotara_is_active": 1,
            "jofotara_client_id": "test_client_123",
            "jofotara_secret_key": "test_secret_key",
            "jofotara_activity_serial": "12345",
            "current_icv_counter": 0
        })
        
        try:
            cls.test_company.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            cls.test_company = frappe.get_doc("Company", "Test Concurrency Company")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        try:
            if frappe.db.exists("Company", "Test Concurrency Company"):
                frappe.delete_doc("Company", "Test Concurrency Company", force=True)
            frappe.db.commit()
        except:
            pass
    
    def setUp(self):
        """Reset counter before each test"""
        frappe.db.set_value("Company", "Test Concurrency Company", "current_icv_counter", 0)
        frappe.db.commit()
    
    def test_concurrent_counter_increment(self):
        """Test concurrent counter increments maintain atomicity"""
        counter_manager = ICVCounterManager()
        num_threads = 10
        results = []
        errors = []
        
        def get_icv_worker():
            """Worker function for concurrent ICV requests"""
            try:
                # Add small random delay to increase concurrency chances
                time.sleep(0.01)
                icv = counter_manager.get_next_icv("Test Concurrency Company")
                return icv
            except Exception as e:
                errors.append(str(e))
                return None
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_icv_worker) for _ in range(num_threads)]
            
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent execution: {errors}")
        self.assertEqual(len(results), num_threads, "All threads should have received ICV values")
        
        # Check that all ICVs are unique and sequential
        results.sort()
        expected = list(range(1, num_threads + 1))
        self.assertEqual(results, expected, "ICVs should be unique and sequential")
        
        # Verify final counter state
        final_counter = frappe.db.get_value("Company", "Test Concurrency Company", "current_icv_counter")
        self.assertEqual(final_counter, num_threads)
    
    def test_high_concurrency_stress_test(self):
        """Stress test with high concurrency load"""
        counter_manager = ICVCounterManager()
        num_threads = 50
        results = []
        errors = []
        
        def stress_worker():
            """Worker for stress testing"""
            try:
                icv = counter_manager.get_next_icv("Test Concurrency Company")
                return icv
            except Exception as e:
                errors.append(str(e))
                return None
        
        # Execute high-concurrency requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(stress_worker) for _ in range(num_threads)]
            
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Errors in stress test: {errors}")
        self.assertEqual(len(results), num_threads, "All requests should succeed")
        
        # Verify uniqueness and range
        self.assertEqual(len(set(results)), num_threads, "All ICVs should be unique")
        self.assertEqual(min(results), 1, "Minimum ICV should be 1")
        self.assertEqual(max(results), num_threads, f"Maximum ICV should be {num_threads}")
    
    def test_concurrent_with_database_rollback(self):
        """Test concurrent access with simulated database errors"""
        counter_manager = ICVCounterManager()
        num_threads = 5
        success_count = 0
        error_count = 0
        results = []
        
        def worker_with_potential_error(thread_id):
            """Worker that may encounter database errors"""
            try:
                # Simulate some database contention
                if thread_id % 3 == 0:
                    # Introduce small delay for some threads
                    time.sleep(0.02)
                
                icv = counter_manager.get_next_icv("Test Concurrency Company")
                return ("success", icv)
            except Exception as e:
                return ("error", str(e))
        
        # Execute concurrent requests
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_with_potential_error, i) for i in range(num_threads)]
            
            for future in as_completed(futures):
                result_type, result_value = future.result()
                if result_type == "success":
                    success_count += 1
                    results.append(result_value)
                else:
                    error_count += 1
        
        # At least some requests should succeed
        self.assertGreater(success_count, 0, "At least some requests should succeed")
        
        # All successful results should be unique
        if results:
            self.assertEqual(len(set(results)), len(results), "All successful ICVs should be unique")
    
    def test_counter_isolation_between_companies(self):
        """Test that counters are isolated between different companies"""
        # Create second test company
        company2 = frappe.get_doc({
            "doctype": "Company",
            "company_name": "Test Concurrency Company 2",
            "abbr": "TCC2",
            "default_currency": "USD",
            "jofotara_is_active": 1,
            "jofotara_client_id": "test_client_456",
            "jofotara_secret_key": "test_secret_key_2",
            "jofotara_activity_serial": "67890",
            "current_icv_counter": 0
        })
        
        try:
            company2.insert()
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            company2 = frappe.get_doc("Company", "Test Concurrency Company 2")
        
        try:
            counter_manager = ICVCounterManager()
            num_threads_per_company = 5
            company1_results = []
            company2_results = []
            
            def worker_company1():
                return counter_manager.get_next_icv("Test Concurrency Company")
            
            def worker_company2():
                return counter_manager.get_next_icv("Test Concurrency Company 2")
            
            # Execute concurrent requests for both companies
            with ThreadPoolExecutor(max_workers=num_threads_per_company * 2) as executor:
                # Submit jobs for company 1
                company1_futures = [executor.submit(worker_company1) for _ in range(num_threads_per_company)]
                # Submit jobs for company 2
                company2_futures = [executor.submit(worker_company2) for _ in range(num_threads_per_company)]
                
                # Collect results
                for future in as_completed(company1_futures):
                    company1_results.append(future.result())
                
                for future in as_completed(company2_futures):
                    company2_results.append(future.result())
            
            # Verify isolation - both companies should have independent sequential counters
            company1_results.sort()
            company2_results.sort()
            
            expected = list(range(1, num_threads_per_company + 1))
            self.assertEqual(company1_results, expected, "Company 1 should have sequential ICVs")
            self.assertEqual(company2_results, expected, "Company 2 should have sequential ICVs")
            
            # Verify final counter states
            final_counter1 = frappe.db.get_value("Company", "Test Concurrency Company", "current_icv_counter")
            final_counter2 = frappe.db.get_value("Company", "Test Concurrency Company 2", "current_icv_counter")
            
            self.assertEqual(final_counter1, num_threads_per_company)
            self.assertEqual(final_counter2, num_threads_per_company)
            
        finally:
            # Clean up second company
            try:
                frappe.delete_doc("Company", "Test Concurrency Company 2", force=True)
                frappe.db.commit()
            except:
                pass
    
    def test_performance_under_load(self):
        """Test performance characteristics under concurrent load"""
        counter_manager = ICVCounterManager()
        num_threads = 20
        
        start_time = time.time()
        
        def performance_worker():
            return counter_manager.get_next_icv("Test Concurrency Company")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(performance_worker) for _ in range(num_threads)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(execution_time, 5.0, "Concurrent operations should complete within reasonable time")
        self.assertEqual(len(results), num_threads, "All operations should complete")
        self.assertEqual(len(set(results)), num_threads, "All results should be unique")
        
        # Log performance metrics
        frappe.logger().info(f"Concurrency Test Performance: {num_threads} operations in {execution_time:.3f}s")


if __name__ == "__main__":
    unittest.main()
