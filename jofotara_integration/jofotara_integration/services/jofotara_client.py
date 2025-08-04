"""
JoFotara API Client Service

Handles secure API connectivity to JoFotara production endpoints for tax compliance.
Provides authentication, request formatting, and response handling for invoice submissions.
"""

import json
import base64
import logging
from typing import Dict, Any, Optional, Tuple
import requests
from requests.exceptions import RequestException, Timeout
import frappe


# Production API endpoint constants
JOFOTARA_PRODUCTION_ENDPOINT = "https://backend.jofotara.gov.jo/core/invoices/"
REQUEST_TIMEOUT_SECONDS = 30

# Response status constants
SUCCESS_STATUS_CODES = [200, 201]
CLIENT_ERROR_CODES = range(400, 500)
SERVER_ERROR_CODES = range(500, 600)

logger = logging.getLogger(__name__)


class JoFotaraClient:
    """
    JoFotara API Client for submitting invoices to tax compliance endpoints.
    
    Handles authentication, payload formatting, HTTP requests, and response processing
    for JoFotara invoice submission workflow.
    """
    
    def __init__(self):
        """Initialize the JoFotara API client."""
        self.api_endpoint = JOFOTARA_PRODUCTION_ENDPOINT
        self.timeout = REQUEST_TIMEOUT_SECONDS
        
    def authenticate_request(self, company_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Format request headers with authentication credentials.
        
        Args:
            company_config: Dictionary containing client_id and secret_key for authentication
            
        Returns:
            Dict containing formatted request headers
            
        Raises:
            ValueError: If required credentials are missing or invalid
        """
        if company_config is None:
            raise ValueError("Company configuration is required for authentication")
            
        client_id = company_config.get('client_id')
        secret_key = company_config.get('secret_key')
        
        if not client_id:
            raise ValueError("Client-Id is required for JoFotara API authentication")
        if not secret_key:
            raise ValueError("Secret-Key is required for JoFotara API authentication")
            
        headers = {
            'Client-Id': str(client_id),
            'Secret-Key': str(secret_key),
            'Content-Type': 'application/json'
        }
        
        return headers
        
    def prepare_payload(self, xml_content: str) -> Dict[str, str]:
        """
        Prepare JSON payload with Base64 encoded XML content.
        
        Args:
            xml_content: UBL 2.1 XML content as string
            
        Returns:
            Dict containing JSON payload with Base64 encoded XML
            
        Raises:
            ValueError: If XML content is empty or invalid
        """
        if not xml_content or not xml_content.strip():
            raise ValueError("XML content is required for payload preparation")
            
        try:
            # Encode XML content to Base64
            xml_bytes = xml_content.encode('utf-8')
            base64_encoded = base64.b64encode(xml_bytes).decode('utf-8')
            
            # Wrap in required JSON format
            payload = {"invoice": base64_encoded}
            
            return payload
            
        except Exception as e:
            raise ValueError(f"Failed to prepare payload: {str(e)}")
            
    def submit_invoice(self, sales_invoice: Dict[str, Any], company_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit invoice to JoFotara API endpoint.
        
        Args:
            sales_invoice: Sales invoice data containing XML content
            company_config: Company configuration with authentication credentials
            
        Returns:
            Dict containing API response data and status information
            
        Raises:
            ValueError: If required parameters are missing
            RequestException: If HTTP request fails
        """
        if not sales_invoice:
            raise ValueError("Sales invoice data is required")
        if not company_config:
            raise ValueError("Company configuration is required")
            
        xml_content = sales_invoice.get('xml_content')
        if not xml_content:
            raise ValueError("XML content is required in sales invoice data")
            
        try:
            # Prepare authentication headers
            headers = self.authenticate_request(company_config)
            
            # Prepare JSON payload with Base64 encoded XML
            payload = self.prepare_payload(xml_content)
            
            # Send HTTP POST request with timeout
            logger.info(f"Submitting invoice to JoFotara API: {self.api_endpoint}")
            
            response = requests.post(
                url=self.api_endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Process response
            return self._process_response(response)
            
        except Timeout:
            logger.error("JoFotara API request timed out")
            return {
                'success': False,
                'error': 'API request timed out',
                'status_code': None,
                'response_time_ms': self.timeout * 1000
            }
        except RequestException as e:
            logger.error(f"JoFotara API request failed: {str(e)}")
            return {
                'success': False,
                'error': f'Network error: {str(e)}',
                'status_code': None,
                'response_time_ms': None
            }
        except Exception as e:
            logger.error(f"Unexpected error during invoice submission: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'status_code': None,
                'response_time_ms': None
            }
            
    def _process_response(self, response: requests.Response) -> Dict[str, Any]:
        """
        Process HTTP response from JoFotara API.
        
        Args:
            response: requests.Response object from API call
            
        Returns:
            Dict containing processed response data
        """
        status_code = response.status_code
        response_time_ms = int(response.elapsed.total_seconds() * 1000)
        
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {'raw_response': response.text}
            
        # Process success responses (200/201)
        if status_code in SUCCESS_STATUS_CODES:
            logger.info(f"JoFotara API success response: {status_code}")
            return {
                'success': True,
                'status_code': status_code,
                'response_time_ms': response_time_ms,
                'uuid': response_data.get('uuid'),
                'qr_code': response_data.get('EINV_QR'),  # Updated to match JoFotara API response field
                'status': response_data.get('status'),
                'submission_time': response_data.get('submission_time'),
                'raw_response': response_data
            }
            
        # Process error responses (4xx/5xx)
        else:
            error_info = self._extract_error_details(response_data)
            logger.error(f"JoFotara API error response: {status_code} - {error_info}")
            return {
                'success': False,
                'status_code': status_code,
                'response_time_ms': response_time_ms,
                'error': error_info,
                'raw_response': response_data
            }
            
    def _extract_error_details(self, response_data: Dict[str, Any]) -> str:
        """
        Extract error details from API error response.
        
        Args:
            response_data: Parsed JSON response data
            
        Returns:
            String containing formatted error message
        """
        # Check for various error response formats
        if 'error' in response_data:
            error_obj = response_data['error']
            if isinstance(error_obj, dict):
                code = error_obj.get('code', 'UNKNOWN_ERROR')
                message = error_obj.get('message', 'Unknown error occurred')
                details = error_obj.get('details', '')
                
                error_msg = f"{code}: {message}"
                if details:
                    error_msg += f" - {details}"
                return error_msg
            else:
                return str(error_obj)
        
        # Check for JoFotara specific error formats
        if 'EINV_RESULTS' in response_data:
            einv_results = response_data['EINV_RESULTS']
            if 'ERRORS' in einv_results and einv_results['ERRORS']:
                errors = []
                for err in einv_results['ERRORS']:
                    error_code = err.get('EINV_CODE', 'UNKNOWN')
                    error_msg = err.get('EINV_MESSAGE', 'Unknown error')
                    errors.append(f"{error_code}: {error_msg}")
                return " | ".join(errors)
        
        # Check for message field
        if 'message' in response_data:
            return str(response_data['message'])
        
        # Return full response data for debugging if no standard error format found
        return f"API error response: {str(response_data)}"
            
    def validate_credentials(self, company_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate company authentication credentials.
        
        Args:
            company_config: Company configuration with credentials to validate
            
        Returns:
            Tuple of (is_valid: bool, message: str)
        """
        try:
            headers = self.authenticate_request(company_config)
            return True, "Credentials are properly formatted"
        except ValueError as e:
            return False, str(e)
            
    def retry_submission(self, log_entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retry failed submission with exponential backoff.
        
        Args:
            log_entry: JoFotara log entry containing original submission data
            
        Returns:
            Dict containing retry attempt result
        """
        # This method will be implemented in future stories with retry logic
        # For now, return a placeholder response
        return {
            'success': False,
            'error': 'Retry functionality not yet implemented',
            'retry_attempted': False
        } 