"""
Jira Ticket Update and Get Tools
Get and update existing Jira tickets using the Jira REST API
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Dict, Any
import requests
import json
import os


class GetJiraTicketInput(BaseModel):
    """Input schema for GetJiraTicket tool"""
    ticket_id: str = Field(description="The Jira ticket ID (e.g., DS-123)")


class GetJiraTicket(BaseTool):
    """Tool to get an existing Jira ticket by ID"""
    
    name: str = "get_jira_ticket"
    description: str = (
        "Retrieves an existing Jira ticket by its ID (e.g., DS-123). "
        "Returns the ticket details including summary, description, assignee, priority, status, etc."
    )
    args_schema: Type[BaseModel] = GetJiraTicketInput

    def _get_jira_credentials(self):
        """Get Jira credentials from environment variables"""
        jira_domain = os.getenv("JIRA_DOMAIN")
        jira_email = os.getenv("JIRA_EMAIL")
        jira_token = os.getenv("JIRA_API_TKN")
        
        if not all([jira_domain, jira_email, jira_token]):
            raise ValueError("Missing Jira credentials in environment variables")
        
        return jira_domain, jira_email, jira_token

    def _run(self, ticket_id: str) -> str:
        """Get a Jira ticket by ID"""
        
        try:
            # Get Jira credentials
            jira_domain, jira_email, jira_token = self._get_jira_credentials()
            
            # Validate ticket ID format
            if not ticket_id or "-" not in ticket_id:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid ticket ID format: {ticket_id}. Expected format: DS-123"
                }, indent=2)

            # Get ticket
            url = f"https://{jira_domain}/rest/api/3/issue/{ticket_id}"
            
            response = requests.get(
                url,
                auth=(jira_email, jira_token),
                headers={"Accept": "application/json"}
            )

            if response.status_code == 200:
                ticket = response.json()
                fields = ticket.get("fields", {})
                
                # Extract assignee
                assignee = fields.get("assignee")
                assignee_name = assignee.get("displayName") if assignee else "Unassigned"
                
                # Extract priority
                priority = fields.get("priority")
                priority_name = priority.get("name") if priority else "None"
                
                # Extract status
                status = fields.get("status")
                status_name = status.get("name") if status else "None"
                
                # Extract description
                description_obj = fields.get("description")
                description = ""
                if description_obj and isinstance(description_obj, dict):
                    content = description_obj.get("content", [])
                    for block in content:
                        if block.get("type") == "paragraph":
                            for item in block.get("content", []):
                                if item.get("type") == "text":
                                    description += item.get("text", "")
                            description += "\n"
                
                return json.dumps({
                    "success": True,
                    "ticket_id": ticket_id,
                    "ticket_key": ticket.get("key"),
                    "summary": fields.get("summary", ""),
                    "description": description.strip(),
                    "assignee": assignee_name,
                    "priority": priority_name,
                    "status": status_name,
                    "created": fields.get("created", ""),
                    "updated": fields.get("updated", ""),
                    "reporter": fields.get("reporter", {}).get("displayName", "Unknown"),
                    "message": f"✅ Ticket {ticket_id} found"
                }, indent=2)
            elif response.status_code == 404:
                return json.dumps({
                    "success": False,
                    "error": f"Ticket {ticket_id} not found",
                    "ticket_id": ticket_id
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Failed to get ticket: {response.text}",
                    "status_code": response.status_code
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Exception occurred: {str(e)}"
            }, indent=2)


class UpdateJiraTicketInput(BaseModel):
    """Input schema for UpdateJiraTicket tool"""
    ticket_id: str = Field(description="The Jira ticket ID to update (e.g., DS-123)")
    summary: Optional[str] = Field(default=None, description="New summary/title or None to keep current")
    description: Optional[str] = Field(default=None, description="New description or None to keep current")
    assignee: Optional[str] = Field(default=None, description="New assignee name or None to keep current")
    priority: Optional[str] = Field(default=None, description="New priority (High/Medium/Low) or None to keep current")
    status: Optional[str] = Field(default=None, description="New status or None to keep current")
    additional_fields: Optional[Dict[str, Any]] = Field(default=None, description="Additional fields to update")


class UpdateJiraTicket(BaseTool):
    """Tool to update an existing Jira ticket"""
    
    name: str = "update_jira_ticket"
    description: str = (
        "Updates an existing Jira ticket with new information. "
        "Only updates the fields that are provided. Fields set to None will keep their current values."
    )
    args_schema: Type[BaseModel] = UpdateJiraTicketInput

    def _get_jira_credentials(self):
        """Get Jira credentials from environment variables"""
        jira_domain = os.getenv("JIRA_DOMAIN")
        jira_email = os.getenv("JIRA_EMAIL")
        jira_token = os.getenv("JIRA_API_TKN")
        
        if not all([jira_domain, jira_email, jira_token]):
            raise ValueError("Missing Jira credentials in environment variables")
        
        return jira_domain, jira_email, jira_token

    def _get_assignee_account_id(self, assignee_name: str, jira_domain: str, jira_email: str, jira_token: str) -> Optional[str]:
        """Get Jira account ID from assignee name"""
        if not assignee_name or assignee_name.lower() in ["unassigned", "none", ""]:
            return None
        
        try:
            url = f"https://{jira_domain}/rest/api/3/user/search"
            params = {"query": assignee_name}
            
            response = requests.get(
                url,
                auth=(jira_email, jira_token),
                params=params,
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                users = response.json()
                if users:
                    return users[0].get("accountId")
            
            return None
            
        except Exception as e:
            print(f"Error getting assignee account ID: {e}")
            return None

    def _map_priority_to_id(self, priority: str) -> str:
        """Map priority name to Jira priority ID"""
        priority_map = {
            "highest": "1",
            "high": "2",
            "medium": "3",
            "low": "4",
            "lowest": "5"
        }
        return priority_map.get(priority.lower(), "3")

    def _run(
        self,
        ticket_id: str,
        summary: Optional[str] = None,
        description: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """Update a Jira ticket"""
        
        try:
            # Get Jira credentials
            jira_domain, jira_email, jira_token = self._get_jira_credentials()
            
            # Validate ticket ID
            if not ticket_id or "-" not in ticket_id:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid ticket ID format: {ticket_id}"
                }, indent=2)

            # Build update payload
            fields = {}
            
            if summary:
                fields["summary"] = summary
            
            if description:
                fields["description"] = {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                }
            
            if assignee:
                assignee_account_id = self._get_assignee_account_id(assignee, jira_domain, jira_email, jira_token)
                if assignee_account_id:
                    fields["assignee"] = {"accountId": assignee_account_id}
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"Assignee '{assignee}' not found"
                    }, indent=2)
            
            if priority:
                fields["priority"] = {"id": self._map_priority_to_id(priority)}
            
            if additional_fields:
                fields.update(additional_fields)
            
            # Update ticket
            url = f"https://{jira_domain}/rest/api/3/issue/{ticket_id}"
            payload = {"fields": fields}
            
            # Add status transition if provided
            if status:
                # Note: Status updates require transitions, which is more complex
                # For now, we'll skip status updates or handle them separately
                pass
            
            response = requests.put(
                url,
                auth=(jira_email, jira_token),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code in [200, 204]:
                ticket_url = f"https://{jira_domain}/browse/{ticket_id}"
                
                return json.dumps({
                    "success": True,
                    "ticket_id": ticket_id,
                    "ticket_url": ticket_url,
                    "updated_fields": list(fields.keys()),
                    "message": f"✅ Ticket {ticket_id} updated successfully!"
                }, indent=2)
            else:
                error_msg = response.text
                try:
                    error_json = response.json()
                    error_details = error_json.get("errors", error_json.get("errorMessages", []))
                    error_msg = json.dumps(error_details, indent=2)
                except:
                    pass
                
                return json.dumps({
                    "success": False,
                    "error": f"Failed to update ticket: {error_msg}",
                    "status_code": response.status_code
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Exception occurred: {str(e)}"
            }, indent=2)

