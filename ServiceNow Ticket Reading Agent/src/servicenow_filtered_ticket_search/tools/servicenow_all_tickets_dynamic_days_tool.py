from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
from datetime import datetime, timedelta
import os

class ServiceNowAllTicketsDynamicDaysRequest(BaseModel):
    """Input schema for ServiceNow All Tickets Dynamic Days Tool."""
    base_url: Optional[str] = Field(None, description="ServiceNow instance base URL (e.g., 'https://your-instance.service-now.com'). If not provided, will use SERVICENOW_BASE_URL environment variable.")
    username: Optional[str] = Field(None, description="ServiceNow username for authentication. If not provided, will use SERVICENOW_USERNAME environment variable.")
    password: Optional[str] = Field(None, description="ServiceNow password for authentication. If not provided, will use SERVICENOW_PWD environment variable.")
    days: int = Field(30, description="Number of days to go back (default: 30, range: 1-365)")
    limit: Optional[int] = Field(100, description="Maximum number of records to retrieve per table (default: 100)")

class ServiceNowAllTicketsDynamicDaysTool(BaseTool):
    """Tool for retrieving all tasks and incidents from ServiceNow for a user-specified number of days back."""

    name: str = "servicenow_all_tickets_dynamic_days"
    description: str = (
        "Retrieves all tasks and incidents from ServiceNow for the specified number of days back "
        "(user-defined) including assigned, unassigned, and all states. Fetches from both task and "
        "incident tables with comprehensive details including task number, incident ID, description, "
        "state, priority, and assignment information. No filters applied for assignment status - "
        "returns all tickets regardless of assignment."
    )
    args_schema: Type[BaseModel] = ServiceNowAllTicketsDynamicDaysRequest

    def _validate_days_parameter(self, days: int) -> str:
        """Validate the days parameter."""
        if not isinstance(days, int):
            return "Error: Days parameter must be an integer."
        
        if days < 1:
            return "Error: Days parameter must be at least 1."
        
        if days > 365:
            return "Error: Days parameter cannot exceed 365 (one year)."
        
        return ""  # No error

    def _get_state_name(self, state_value: str, record_type: str) -> str:
        """Convert state number to readable name."""
        try:
            state_num = int(state_value) if state_value else 0
        except (ValueError, TypeError):
            return "Unknown"
        
        if record_type == "Task":
            task_states = {
                -5: "Pending", 1: "Open", 2: "Work in Progress", 3: "Closed Complete",
                4: "Closed Incomplete", 7: "Closed Skipped", 8: "Canceled"
            }
            return task_states.get(state_num, f"State {state_num}")
        else:  # Incident
            incident_states = {
                1: "New", 2: "In Progress", 3: "On Hold", 6: "Resolved", 7: "Closed", 8: "Canceled"
            }
            return incident_states.get(state_num, f"State {state_num}")

    def _get_priority_name(self, priority_value: str) -> str:
        """Convert priority number to readable name."""
        try:
            priority_num = int(priority_value) if priority_value else 5
        except (ValueError, TypeError):
            return "Unknown"
        
        priorities = {
            1: "1 - Critical", 2: "2 - High", 3: "3 - Moderate",
            4: "4 - Low", 5: "5 - Planning"
        }
        return priorities.get(priority_num, f"Priority {priority_num}")

    def _make_servicenow_request(self, base_url: str, username: str, password: str, 
                               table: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to ServiceNow API."""
        url = f"{base_url.rstrip('/')}/api/now/table/{table}"
        
        try:
            response = requests.get(
                url,
                auth=(username, password),
                params=params,
                headers={
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if response.status_code == 401:
                return {"error": "Authentication failed. Please check your credentials."}
            elif response.status_code == 403:
                return {"error": "Access forbidden. Please check your permissions."}
            elif response.status_code != 200:
                return {"error": f"ServiceNow API error: {response.status_code} - {response.text}"}
            
            return response.json()
            
        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Please try again."}
        except requests.exceptions.ConnectionError:
            return {"error": "Connection error. Please check your ServiceNow instance URL."}
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}

    def _run(self, base_url: Optional[str] = None, username: Optional[str] = None, 
             password: Optional[str] = None, days: int = 30, limit: Optional[int] = 100) -> str:
        try:
            # Validate days parameter first
            validation_error = self._validate_days_parameter(days)
            if validation_error:
                return validation_error

            # Get credentials from parameters or environment variables
            actual_base_url = base_url or os.getenv('SERVICENOW_BASE_URL')
            actual_username = username or os.getenv('SERVICENOW_USERNAME')
            actual_password = password or os.getenv('SERVICENOW_PWD')
            
            # Validate credentials
            if not all([actual_base_url, actual_username, actual_password]):
                return (
                    f"Error: Missing ServiceNow credentials for the last {days} days query. Please provide:\n"
                    "1. base_url parameter or SERVICENOW_BASE_URL environment variable\n"
                    "2. username parameter or SERVICENOW_USERNAME environment variable\n"
                    "3. password parameter or SERVICENOW_PWD environment variable"
                )
            
            # Validate base_url format
            if not actual_base_url.startswith('http'):
                return "Error: base_url must be a valid URL starting with http:// or https://"
            
            # Calculate date for the specified number of days ago
            days_ago = datetime.now() - timedelta(days=days)
            date_filter = days_ago.strftime('%Y-%m-%d %H:%M:%S')
            
            # Common parameters for both queries
            common_params = {
                'sysparm_query': f'sys_created_on>={date_filter}',
                'sysparm_limit': str(limit),
                'sysparm_offset': '0'
            }
            
            all_records = []
            
            # Fetch Tasks
            task_params = {
                **common_params,
                'sysparm_fields': 'number,short_description,description,state,priority,assigned_to.name,sys_created_on,sys_updated_on,active'
            }
            
            task_response = self._make_servicenow_request(actual_base_url, actual_username, actual_password, 'task', task_params)
            
            if 'error' in task_response:
                return f"Error fetching tasks for the last {days} days: {task_response['error']}"
            
            # Process tasks
            for task in task_response.get('result', []):
                record = {
                    'record_type': 'Task',
                    'number': task.get('number', ''),
                    'short_description': task.get('short_description', ''),
                    'description': task.get('description', ''),
                    'state': task.get('state', ''),
                    'state_name': self._get_state_name(task.get('state', ''), 'Task'),
                    'priority': task.get('priority', ''),
                    'priority_name': self._get_priority_name(task.get('priority', '')),
                    'assigned_to': task.get('assigned_to', {}).get('name', 'Unassigned') if isinstance(task.get('assigned_to'), dict) else 'Unassigned',
                    'sys_created_on': task.get('sys_created_on', ''),
                    'sys_updated_on': task.get('sys_updated_on', ''),
                    'active': task.get('active', '')
                }
                all_records.append(record)
            
            # Fetch Incidents
            incident_params = {
                **common_params,
                'sysparm_fields': 'number,short_description,description,state,priority,assigned_to.name,sys_created_on,sys_updated_on,active,incident_state'
            }
            
            incident_response = self._make_servicenow_request(actual_base_url, actual_username, actual_password, 'incident', incident_params)
            
            if 'error' in incident_response:
                return f"Error fetching incidents for the last {days} days: {incident_response['error']}"
            
            # Process incidents
            for incident in incident_response.get('result', []):
                record = {
                    'record_type': 'Incident',
                    'number': incident.get('number', ''),
                    'short_description': incident.get('short_description', ''),
                    'description': incident.get('description', ''),
                    'state': incident.get('incident_state', incident.get('state', '')),
                    'state_name': self._get_state_name(incident.get('incident_state', incident.get('state', '')), 'Incident'),
                    'priority': incident.get('priority', ''),
                    'priority_name': self._get_priority_name(incident.get('priority', '')),
                    'assigned_to': incident.get('assigned_to', {}).get('name', 'Unassigned') if isinstance(incident.get('assigned_to'), dict) else 'Unassigned',
                    'sys_created_on': incident.get('sys_created_on', ''),
                    'sys_updated_on': incident.get('sys_updated_on', ''),
                    'active': incident.get('active', '')
                }
                all_records.append(record)
            
            # Sort by creation date (newest first)
            all_records.sort(key=lambda x: x['sys_created_on'], reverse=True)
            
            # Format output
            if not all_records:
                return f"No tickets found for the last {days} days (since {date_filter})"
            
            output = f"ServiceNow Tickets - Last {days} Days ({len(all_records)} records found)\n"
            output += f"Date Range: {date_filter} to present\n"
            output += "=" * 80 + "\n\n"
            
            # Summary statistics
            task_count = len([r for r in all_records if r['record_type'] == 'Task'])
            incident_count = len([r for r in all_records if r['record_type'] == 'Incident'])
            assigned_count = len([r for r in all_records if r['assigned_to'] != 'Unassigned'])
            unassigned_count = len(all_records) - assigned_count
            
            output += f"SUMMARY:\n"
            output += f"- Total Records: {len(all_records)}\n"
            output += f"- Tasks: {task_count}\n"
            output += f"- Incidents: {incident_count}\n"
            output += f"- Assigned: {assigned_count}\n"
            output += f"- Unassigned: {unassigned_count}\n\n"
            
            # Detailed records with enhanced descriptions
            output += "DETAILED RECORDS:\n"
            output += "-" * 80 + "\n"
            
            for i, record in enumerate(all_records, 1):
                output += f"{i}. {record['record_type']}: {record['number']}\n"
                
                # Enhanced description handling - show full descriptions
                short_desc = record['short_description'] or 'No short description'
                full_desc = record['description'] or 'No detailed description'
                
                output += f"   Short Description: {short_desc}\n"
                if full_desc != short_desc and full_desc.strip():
                    # Show full description if it's different from short description
                    output += f"   Full Description: {full_desc}\n"
                
                output += f"   State: {record['state_name']}\n"
                output += f"   Priority: {record['priority_name']}\n"
                output += f"   Assigned To: {record['assigned_to']}\n"
                output += f"   Created: {record['sys_created_on']}\n"
                output += f"   Updated: {record['sys_updated_on']}\n"
                output += f"   Active: {record['active']}\n"
                output += "\n"
            
            return output
            
        except Exception as e:
            return f"Error retrieving ServiceNow tickets for the last {days if 'days' in locals() else 'specified'} days: {str(e)}"