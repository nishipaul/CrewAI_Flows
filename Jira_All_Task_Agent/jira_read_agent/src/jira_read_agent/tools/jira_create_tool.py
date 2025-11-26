"""
Jira Ticket Creation Tool
Creates new Jira tickets using the Jira REST API
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional, Dict, Any
import requests
import json
import os
from datetime import datetime


class CreateJiraTicketInput(BaseModel):
    """Input schema for CreateJiraTicket tool"""
    board_id: str = Field(description="The Jira project key/board ID (e.g., DS, PROJ)")
    summary: str = Field(description="The ticket summary/title")
    description: str = Field(description="Detailed description of the ticket")
    assignee: Optional[str] = Field(default=None, description="Full name of assignee or None for Unassigned")
    priority: str = Field(default="Medium", description="Priority: High, Medium, or Low")
    due_date: Optional[str] = Field(default=None, description="Due date in YYYY-MM-DD format or None")
    issue_type: str = Field(default="Task", description="Issue type: Task, Bug, Story, etc.")
    additional_fields: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom fields")


class CreateJiraTicket(BaseTool):
    """Tool to create new Jira tickets"""
    
    name: str = "create_jira_ticket"
    description: str = (
        "Creates a new Jira ticket with the provided information. "
        "Returns the created ticket ID and link. "
        "Required: board_id, summary, description. "
        "Optional: assignee, priority, due_date, issue_type, additional_fields."
    )
    args_schema: Type[BaseModel] = CreateJiraTicketInput

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
            # Search for user by name
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
                    # Return first match
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
        return priority_map.get(priority.lower(), "3")  # Default to Medium

    def _run(
        self,
        board_id: str,
        summary: str,
        description: str,
        assignee: Optional[str] = None,
        priority: str = "Medium",
        due_date: Optional[str] = None,
        issue_type: str = "Task",
        additional_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new Jira ticket"""
        
        try:
            # Get Jira credentials
            jira_domain, jira_email, jira_token = self._get_jira_credentials()
            
            # Validate required fields
            if not board_id or not summary or not description:
                return json.dumps({
                    "success": False,
                    "error": "Missing required fields: board_id, summary, and description are required"
                }, indent=2)

            # Get assignee account ID if provided
            assignee_account_id = None
            if assignee:
                assignee_account_id = self._get_assignee_account_id(assignee, jira_domain, jira_email, jira_token)
                if not assignee_account_id:
                    return json.dumps({
                        "success": False,
                        "error": f"Assignee '{assignee}' not found. Please provide a valid assignee name or leave blank for Unassigned."
                    }, indent=2)

            # Build ticket payload
            fields = {
                "project": {"key": board_id},
                "summary": summary,
                "description": {
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
                },
                "issuetype": {"name": issue_type},
                "priority": {"id": self._map_priority_to_id(priority)}
            }

            # Add assignee if provided
            if assignee_account_id:
                fields["assignee"] = {"accountId": assignee_account_id}

            # Add due date if provided
            if due_date:
                try:
                    # Validate date format
                    datetime.strptime(due_date, "%Y-%m-%d")
                    fields["duedate"] = due_date
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "error": f"Invalid date format: {due_date}. Please use YYYY-MM-DD format."
                    }, indent=2)

            # Add additional custom fields
            if additional_fields:
                fields.update(additional_fields)

            # Create ticket
            url = f"https://{jira_domain}/rest/api/3/issue"
            payload = {"fields": fields}
            
            response = requests.post(
                url,
                auth=(jira_email, jira_token),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code in [200, 201]:
                result = response.json()
                ticket_key = result.get("key")
                ticket_id = result.get("id")
                ticket_url = f"https://{jira_domain}/browse/{ticket_key}"
                
                return json.dumps({
                    "success": True,
                    "ticket_id": ticket_key,
                    "ticket_url": ticket_url,
                    "jira_id": ticket_id,
                    "summary": summary,
                    "assignee": assignee or "Unassigned",
                    "priority": priority,
                    "due_date": due_date,
                    "message": f"✅ Ticket {ticket_key} created successfully!"
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
                    "error": f"Failed to create ticket: {error_msg}",
                    "status_code": response.status_code
                }, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Exception occurred: {str(e)}"
            }, indent=2)


class ValidateBoardInput(BaseModel):
    """Input schema for ValidateBoard tool"""
    board_id: str = Field(description="The Jira project key/board ID to validate")


class ValidateBoard(BaseTool):
    """Tool to validate if a board/project exists"""
    
    name: str = "validate_board"
    description: str = "Validates if a Jira board/project exists and is accessible."
    args_schema: Type[BaseModel] = ValidateBoardInput

    def _get_jira_credentials(self):
        """Get Jira credentials from environment variables"""
        jira_domain = os.getenv("JIRA_DOMAIN")
        jira_email = os.getenv("JIRA_EMAIL")
        jira_token = os.getenv("JIRA_API_TKN")
        
        if not all([jira_domain, jira_email, jira_token]):
            raise ValueError("Missing Jira credentials in environment variables")
        
        return jira_domain, jira_email, jira_token

    def _run(self, board_id: str) -> str:
        """Validate board exists"""
        try:
            # Get Jira credentials
            jira_domain, jira_email, jira_token = self._get_jira_credentials()
            
            url = f"https://{jira_domain}/rest/api/3/project/{board_id}"
            
            response = requests.get(
                url,
                auth=(jira_email, jira_token),
                headers={"Accept": "application/json"}
            )
            
            if response.status_code == 200:
                project = response.json()
                return json.dumps({
                    "success": True,
                    "board_id": board_id,
                    "name": project.get("name"),
                    "key": project.get("key"),
                    "message": f"✅ Board '{board_id}' is valid"
                }, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Board '{board_id}' not found or not accessible"
                }, indent=2)
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error validating board: {str(e)}"
            }, indent=2)

