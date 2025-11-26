from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
import requests
import json
from datetime import datetime

class ServiceNowQueryInput(BaseModel):
    """Input schema for ServiceNow Filtered Query Tool."""
    base_url: str = Field(..., description="The base URL of your ServiceNow instance (e.g., 'yourinstance.service-now.com' or 'https://yourinstance.service-now.com')")
    username: str = Field(..., description="Username for ServiceNow authentication")
    password: str = Field(..., description="Password for ServiceNow authentication")
    query: str = Field(..., description="Search query to filter tickets (searches in description, summary, assigned_to, state)")
    limit: int = Field(default=10, description="Maximum number of results to return (default: 10, range: 1-100)", ge=1, le=100)

class ServiceNowFilteredQueryTool(BaseTool):
    """Tool for searching ServiceNow incidents and tasks based on user queries."""

    name: str = "ServiceNow Filtered Query Tool"
    description: str = (
        "Searches ServiceNow incidents and tasks based on a user query with provided credentials. "
        "Performs case-insensitive search across description, summary, assigned_to, and state fields. "
        "Returns structured ticket data including ticket_id, incident_id, task_id, summary, description, "
        "assigned_to, priority, state, created, and updated timestamps."
    )
    args_schema: Type[BaseModel] = ServiceNowQueryInput

    def _format_url(self, base_url: str) -> str:
        """Format the base URL to ensure proper format."""
        # Remove any trailing slashes
        base_url = base_url.rstrip('/')
        
        # Add https:// if not present
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"https://{base_url}"
        
        # Add .service-now.com if it's just the instance name
        if base_url.count('.') == 0 and not base_url.endswith('.service-now.com'):
            # Extract instance name from full URL if provided
            instance_name = base_url.replace('https://', '').replace('http://', '')
            base_url = f"https://{instance_name}.service-now.com"
        
        return base_url

    def _build_query_filter(self, query: str) -> str:
        """Build the ServiceNow query filter with LIKE operators."""
        # Escape special characters in the query
        escaped_query = query.replace("'", "\\'")
        
        # Build the filter with OR conditions across multiple fields
        filter_conditions = [
            f"short_descriptionLIKE{escaped_query}",
            f"descriptionLIKE{escaped_query}",
            f"assigned_to.nameLIKE{escaped_query}",
            f"stateLIKE{escaped_query}",
            f"numberLIKE{escaped_query}"
        ]
        
        return "^OR".join(filter_conditions)

    def _query_table(self, base_url: str, username: str, password: str, table: str, query_filter: str, limit: int) -> List[Dict]:
        """Query a specific ServiceNow table."""
        try:
            # Build the API endpoint
            api_url = f"{base_url}/api/now/table/{table}"
            
            # Set up parameters
            params = {
                'sysparm_query': query_filter,
                'sysparm_limit': str(limit),
                'sysparm_display_value': 'true',
                'sysparm_fields': 'sys_id,number,short_description,description,assigned_to,priority,state,sys_created_on,sys_updated_on'
            }
            
            # Make the API request
            response = requests.get(
                api_url,
                auth=(username, password),
                params=params,
                headers={'Accept': 'application/json'},
                timeout=30
            )
            
            # Check for authentication errors
            if response.status_code == 401:
                raise Exception("Authentication failed. Please check your username and password.")
            elif response.status_code == 403:
                raise Exception("Access forbidden. Please check your permissions.")
            elif response.status_code != 200:
                raise Exception(f"API request failed with status {response.status_code}: {response.text}")
            
            # Parse the response
            data = response.json()
            return data.get('result', [])
            
        except requests.exceptions.ConnectionError:
            raise Exception(f"Connection error. Please check your ServiceNow instance URL: {base_url}")
        except requests.exceptions.Timeout:
            raise Exception("Request timeout. The ServiceNow instance may be slow or unavailable.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request error: {str(e)}")
        except json.JSONDecodeError:
            raise Exception("Invalid JSON response from ServiceNow API.")

    def _format_ticket_data(self, record: Dict, table_type: str) -> Dict:
        """Format a single ticket record."""
        # Determine ticket type and ID fields
        ticket_id = record.get('sys_id', '')
        incident_id = record.get('number', '') if table_type == 'incident' else ''
        task_id = record.get('number', '') if table_type == 'task' else ''
        
        # Format timestamps
        created = record.get('sys_created_on', '')
        updated = record.get('sys_updated_on', '')
        
        return {
            'type': table_type,
            'ticket_id': ticket_id,
            'incident_id': incident_id,
            'task_id': task_id,
            'number': record.get('number', ''),
            'summary': record.get('short_description', ''),
            'description': record.get('description', ''),
            'assigned_to': record.get('assigned_to', ''),
            'priority': record.get('priority', ''),
            'state': record.get('state', ''),
            'created': created,
            'updated': updated
        }

    def _truncate_description(self, text: str, max_length: int = 100) -> str:
        """Truncate description text if it's too long."""
        if not text:
            return "N/A"
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "..."

    def _format_results(self, tickets: List[Dict]) -> str:
        """Format the results into a readable string."""
        if not tickets:
            return "No tickets found matching your query."
        
        result_lines = [f"Found {len(tickets)} ticket(s) matching your query:\n"]
        
        for i, ticket in enumerate(tickets, 1):
            # Format ticket header
            ticket_type = ticket['type'].upper()
            number = ticket['number']
            summary = ticket['summary'] or 'No summary'
            
            result_lines.append(f"{i}. [{ticket_type}] {number}: {summary}")
            result_lines.append(f"   Ticket ID: {ticket['ticket_id']}")
            
            # Add type-specific IDs
            if ticket['incident_id']:
                result_lines.append(f"   Incident ID: {ticket['incident_id']}")
            if ticket['task_id']:
                result_lines.append(f"   Task ID: {ticket['task_id']}")
            
            # Add other details
            result_lines.append(f"   Description: {self._truncate_description(ticket['description'])}")
            result_lines.append(f"   Assigned To: {ticket['assigned_to'] or 'Unassigned'}")
            result_lines.append(f"   Priority: {ticket['priority'] or 'N/A'}")
            result_lines.append(f"   State: {ticket['state'] or 'N/A'}")
            result_lines.append(f"   Created: {ticket['created']}")
            result_lines.append(f"   Updated: {ticket['updated']}")
            
            # Add separator line except for the last ticket
            if i < len(tickets):
                result_lines.append(f"   {'-' * 50}")
        
        return "\n".join(result_lines)

    def _run(self, base_url: str, username: str, password: str, query: str, limit: int) -> str:
        """Execute the ServiceNow query."""
        try:
            # Input validation
            if not all([base_url.strip(), username.strip(), password.strip(), query.strip()]):
                return "Error: All parameters (base_url, username, password, query) must be provided and non-empty."
            
            # Format the base URL
            formatted_url = self._format_url(base_url)
            
            # Build the query filter
            query_filter = self._build_query_filter(query)
            
            all_tickets = []
            
            # Calculate limit per table (split between incident and task)
            incidents_limit = min(limit, 50)  # Max 50 per table
            tasks_limit = min(limit - len(all_tickets), 50)
            
            # Query incidents table
            try:
                incident_records = self._query_table(formatted_url, username, password, 'incident', query_filter, incidents_limit)
                for record in incident_records:
                    if len(all_tickets) >= limit:
                        break
                    all_tickets.append(self._format_ticket_data(record, 'incident'))
            except Exception as e:
                return f"Error querying incidents table: {str(e)}"
            
            # Query tasks table (only if we haven't reached the limit)
            if len(all_tickets) < limit:
                try:
                    remaining_limit = limit - len(all_tickets)
                    task_records = self._query_table(formatted_url, username, password, 'task', query_filter, remaining_limit)
                    for record in task_records:
                        if len(all_tickets) >= limit:
                            break
                        all_tickets.append(self._format_ticket_data(record, 'task'))
                except Exception as e:
                    # Don't fail completely if tasks query fails, just add a note
                    if all_tickets:
                        return self._format_results(all_tickets) + f"\n\nNote: Error querying tasks table: {str(e)}"
                    else:
                        return f"Error querying tasks table: {str(e)}"
            
            # Format and return results
            return self._format_results(all_tickets)
            
        except Exception as e:
            return f"Error: {str(e)}"