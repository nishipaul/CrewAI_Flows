from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional
import requests
from requests.auth import HTTPBasicAuth
import re

class ServiceNowConnectionInput(BaseModel):
    """Input schema for ServiceNow Connection Tool."""
    base_url: Optional[str] = Field(
        None, 
        description="The base URL of the ServiceNow instance (e.g., https://your-instance.service-now.com)"
    )
    username: Optional[str] = Field(
        None,
        description="ServiceNow username for authentication"
    )
    password: Optional[str] = Field(
        None,
        description="ServiceNow password for authentication"
    )

class ServiceNowConnectionTool(BaseTool):
    """Tool for testing connectivity to ServiceNow instances using basic authentication."""

    name: str = "servicenow_connection_tool"
    description: str = (
        "Establishes and tests connection to ServiceNow instance using basic authentication. "
        "Accepts optional ServiceNow credentials (base_url, username, password) as input parameters. "
        "Tests connectivity by making a GET request to the sys_user table endpoint. "
        "Returns success message if connection works, error message if it fails, or validation errors if credentials are missing."
    )
    args_schema: Type[BaseModel] = ServiceNowConnectionInput

    def _run(self, base_url: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None) -> str:
        try:
            # Validate required parameters
            if not base_url:
                return "❌ Error: base_url parameter is required"
            if not username:
                return "❌ Error: username parameter is required"
            if not password:
                return "❌ Error: password parameter is required"

            # Clean and validate base URL format
            base_url = base_url.strip()
            if not re.match(r'^https?://', base_url):
                return "❌ Error: base_url must start with http:// or https://"
            
            # Remove trailing slash if present
            base_url = base_url.rstrip('/')

            # Construct the API endpoint
            api_endpoint = f"{base_url}/api/now/table/sys_user"

            # Prepare request parameters
            params = {
                'sysparm_limit': 1  # Limit to 1 record for testing
            }

            # Make the GET request with basic authentication
            response = requests.get(
                api_endpoint,
                auth=HTTPBasicAuth(username, password),
                params=params,
                timeout=10,
                headers={'Accept': 'application/json'}
            )

            # Handle various HTTP status codes
            if response.status_code == 200:
                return f"✅ Success: Successfully connected to ServiceNow instance at {base_url}"
            elif response.status_code == 401:
                return "❌ Authentication failed: Invalid username or password"
            elif response.status_code == 403:
                return "❌ Access forbidden: User doesn't have permission to access sys_user table"
            elif response.status_code == 404:
                return "❌ Endpoint not found: The API endpoint may not exist or ServiceNow instance is incorrect"
            else:
                return f"❌ Connection failed: HTTP {response.status_code} - {response.reason}"

        except requests.exceptions.Timeout:
            return "⚠️ Connection timeout: Request timed out after 10 seconds"
        except requests.exceptions.SSLError:
            return "❌ SSL Error: SSL certificate verification failed"
        except requests.exceptions.ConnectionError:
            return "❌ Connection Error: Unable to establish connection to ServiceNow instance"
        except requests.exceptions.RequestException as e:
            return f"❌ Request Error: {str(e)}"
        except Exception as e:
            return f"❌ Unexpected Error: {str(e)}"