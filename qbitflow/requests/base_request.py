"""
Base request handler for QBitFlow SDK.

This module provides the base class for all API request handlers with
comprehensive error handling and retry logic.
"""

from typing import Any, Dict, Literal, Optional
import time
import httpx
from pydantic import BaseModel, Field

from qbitflow import config
from qbitflow.exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    NotFoundException,
    RateLimitError,
    InvalidRequestError,
)


class SuccessResponse(BaseModel):
    """
    Standard success response model.
    
    Attributes:
        message: Success message from the API.
    """
    message: str = Field(..., description="Success message")


class ErrorResponse(BaseModel):
    """
    Standard error response model.
    
    Attributes:
        error: Error message or code.
    """
    error: str = Field(..., description="Error message or code")


class BaseRequest:
    """
    Base class for all API request handlers.
    
    This class provides common functionality for making HTTP requests to the
    QBitFlow API, including authentication, error handling, and retries.
    
    Attributes:
        api_key: API key for authentication.
        headers: HTTP headers to include in requests.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts.
    """
    
    def __init__(self, api_key: str, timeout: Optional[int] = None, max_retries: Optional[int] = None):
        """
        Initialize the request handler.
        
        Args:
            api_key: API key for authentication.
            timeout: Optional request timeout in seconds (defaults to config.DEFAULT_TIMEOUT).
            max_retries: Optional maximum retry attempts (defaults to config.MAX_RETRIES).
        
        Raises:
            ValueError: If api_key is empty or None.
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        
        self.api_key = api_key
        self.timeout = timeout or config.DEFAULT_TIMEOUT
        self.max_retries = max_retries or config.MAX_RETRIES
        
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _make_request(
        self,
        endpoint: str,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ):
        """
        Make an HTTP request to the API with error handling and retries.
        
        Args:
            endpoint: API endpoint path.
            method: HTTP method to use.
            data: Optional request body data.
            params: Optional query parameters.
            retry_count: Current retry attempt number.
        
        Returns:
            Parsed JSON response from the API.
        
        Raises:
            AuthenticationError: If authentication fails (401).
            NotFoundException: If resource is not found (404).
            RateLimitError: If rate limit is exceeded (429).
            NetworkError: If a network error occurs.
            APIError: For other API errors.
            InvalidRequestError: If the request is malformed.
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        url = f"{config.get_base_url()}{endpoint}"
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    if data is None:
                        raise InvalidRequestError("POST requests require data")
                    response = client.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    if data is None:
                        raise InvalidRequestError("PUT requests require data")
                    response = client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = client.delete(url, headers=self.headers)
                else:
                    raise InvalidRequestError(f"Invalid HTTP method: {method}")
            
            # Handle HTTP errors
            self._handle_http_status(response)
            
            # Parse and return JSON response
            try:
                return response.json()
            except Exception as e:
                raise APIError(
                    f"Failed to parse JSON response: {str(e)}",
                    status_code=response.status_code,
                    response={"raw": response.text}
                )
        
        except httpx.TimeoutException as e:
            if retry_count < self.max_retries:
                # Exponential backoff
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                return self._make_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Request timeout after {self.timeout} seconds: {str(e)}")
        
        except httpx.NetworkError as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                return self._make_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Network error: {str(e)}")
        
        except (AuthenticationError, NotFoundException, RateLimitError, APIError, InvalidRequestError):
            # Don't retry these errors
            raise
        
        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")
    
    def _handle_http_status(self, response: httpx.Response) -> None:
        """
        Handle HTTP response status codes and raise appropriate exceptions.
        
        Args:
            response: HTTP response object.
        
        Raises:
            AuthenticationError: If authentication fails (401).
            NotFoundException: If resource is not found (404).
            RateLimitError: If rate limit is exceeded (429).
            APIError: For other error status codes.
        """
        status_code = response.status_code
        
        # Success codes
        if 200 <= status_code < 300:
            return
        
        # Extract error message from response
        error_message = self._extract_error_message(response)
        
        # Handle specific status codes
        if status_code == 401:
            raise AuthenticationError(
                error_message or "Authentication failed - check your API key",
                status_code=status_code
            )
        
        elif status_code == 404:
            raise NotFoundException(
                error_message or "Resource not found",
                status_code=status_code
            )
        
        elif status_code == 429:
            retry_after = response.headers.get("Retry-After")
            response_data = {"retry_after": retry_after} if retry_after else None
            raise RateLimitError(
                error_message or "Rate limit exceeded",
                status_code=status_code,
                response=response_data
            )
        
        elif 400 <= status_code < 500:
            raise InvalidRequestError(
                error_message or f"Bad request (status {status_code})",
                status_code=status_code
            )
        
        else:
            raise APIError(
                error_message or f"API error (status {status_code})",
                status_code=status_code
            )
    
    def _make_raw_request(
        self,
        endpoint: str,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> str:
        """
        Make an HTTP request and return the raw response text.

        Same retry/error logic as _make_request, but returns response.text
        instead of parsing JSON — useful for CSV or other non-JSON responses.
        """
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = f"{config.get_base_url()}{endpoint}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == "GET":
                    response = client.get(url, headers=self.headers, params=params)
                elif method == "POST":
                    if data is None:
                        raise InvalidRequestError("POST requests require data")
                    response = client.post(url, headers=self.headers, json=data)
                elif method == "PUT":
                    if data is None:
                        raise InvalidRequestError("PUT requests require data")
                    response = client.put(url, headers=self.headers, json=data)
                elif method == "DELETE":
                    response = client.delete(url, headers=self.headers)
                else:
                    raise InvalidRequestError(f"Invalid HTTP method: {method}")

            self._handle_http_status(response)
            return response.text

        except httpx.TimeoutException as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                return self._make_raw_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Request timeout after {self.timeout} seconds: {str(e)}")

        except httpx.NetworkError as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                time.sleep(wait_time)
                return self._make_raw_request(endpoint, method, data, params, retry_count + 1)
            raise NetworkError(f"Network error: {str(e)}")

        except (AuthenticationError, NotFoundException, RateLimitError, APIError, InvalidRequestError):
            raise

        except Exception as e:
            raise APIError(f"Unexpected error: {str(e)}")

    def _extract_error_message(self, response: httpx.Response) -> str:
        """
        Extract error message from response.
        
        Args:
            response: HTTP response object.
        
        Returns:
            Extracted error message or default message.
        """
        try:
            data = response.json()
            
            # Check for common error message fields
            if "error" in data:
                return str(data["error"])
            
            if "message" in data:
                return str(data["message"])
            
            if "errors" in data:
                errors = data["errors"]
                if isinstance(errors, list) and len(errors) > 0:
                    first_error = errors[0]
                    if isinstance(first_error, dict) and "message" in first_error:
                        return str(first_error["message"])
                    return str(first_error)
                return str(errors)
            
            return f"API error (status {response.status_code})"
        
        except Exception:
            return f"API error (status {response.status_code})"
