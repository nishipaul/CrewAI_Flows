"""
Custom Jira Tool - Direct API integration with caching
"""
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
from requests.auth import HTTPBasicAuth
import json
import os
from .ticket_cache_manager import TicketCacheManager


class JiraSearchInput(BaseModel):
    """Input schema for Jira search tool."""
    board_id: Optional[str] = Field(
        None,
        description="The Jira board ID to fetch tickets from"
    )
    days_to_look_back: int = Field(
        default=30,
        description="Number of days to look back when fetching tickets"
    )
    search_text: Optional[str] = Field(
        None,
        description="Text to search for in ticket summaries and descriptions"
    )


class CustomJiraTool(BaseTool):
    """Custom tool for fetching and searching Jira tickets using direct API."""
    
    name: str = "search_jira_tickets"
    description: str = (
        "Search and fetch tickets from Jira boards using direct API integration. "
        "Returns detailed ticket information including key, summary, assignee, description, status, and created date. "
        "Can filter by board, date range, and search text. "
        "Requires JIRA_DOMAIN, JIRA_EMAIL, and JIRA_API_TKN environment variables."
    )
    args_schema: Type[BaseModel] = JiraSearchInput

    def extract_text_from_nested_dict(self, data: Any) -> str:
        """Helper function to recursively extract text from nested dictionaries (ADF format)."""
        if isinstance(data, dict):
            text_parts = []
            for key, value in data.items():
                if key == 'text' and isinstance(value, str):
                    text_parts.append(value)
                elif key == 'content':
                    nested_text = self.extract_text_from_nested_dict(value)
                    if nested_text:
                        text_parts.append(nested_text)
                else:
                    nested_text = self.extract_text_from_nested_dict(value)
                    if nested_text:
                        text_parts.append(nested_text)
            return ' '.join(text_parts)
        elif isinstance(data, list):
            text_parts = []
            for item in data:
                nested_text = self.extract_text_from_nested_dict(item)
                if nested_text:
                    text_parts.append(nested_text)
            return ' '.join(text_parts)
        elif isinstance(data, str):
            return data
        return ""

    def get_tickets_from_board(self, board_id: str, days_to_look_back: int, search_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tickets from a Jira board with optional text search."""
        try:
            # Get environment variables
            jira_domain = os.getenv('JIRA_DOMAIN')
            jira_email = os.getenv('JIRA_EMAIL')
            jira_api_tkn = os.getenv('JIRA_API_TKN')
            
            if not all([jira_domain, jira_email, jira_api_tkn]):
                return [{
                    "error": "Missing required environment variables: JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TKN",
                    "success": False
                }]

            # Create auth
            auth = HTTPBasicAuth(jira_email, jira_api_tkn)
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }

            tickets = []
            start_at = 0
            max_results = 50

            while True:
                # Construct JQL query
                jql_parts = [f'created >= -{days_to_look_back}d']
                if search_text:
                    jql_parts.append(f'text ~ "{search_text}"')
                jql = ' AND '.join(jql_parts)

                # Use Agile API to get board issues
                url = f"https://{jira_domain}/rest/agile/1.0/board/{board_id}/issue"
                params = {
                    'jql': jql,
                    'startAt': start_at,
                    'maxResults': max_results,
                    'fields': 'summary,description,assignee,status,created,reporter,priority'
                }

                response = requests.get(url, auth=auth, headers=headers, params=params)
                
                if response.status_code != 200:
                    return [{
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "success": False
                    }]

                data = response.json()
                issues = data.get('issues', [])
                
                if not issues:
                    break

                for issue in issues:
                    ticket_details = self.parse_ticket_details(issue)
                    tickets.append(ticket_details)

                if len(issues) < max_results:
                    break
                    
                start_at += max_results

            return tickets if tickets else [{
                "message": f"No tickets found in board {board_id} matching the criteria",
                "success": True,
                "count": 0
            }]

        except Exception as e:
            return [{
                "error": f"Exception: {str(e)}",
                "success": False
            }]

    def parse_ticket_details(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Parse ticket details from Jira API response."""
        try:
            fields = issue.get('fields', {})
            
            # Extract key
            ticket_key = issue.get('key', 'Unknown')
            
            # Extract summary
            summary = fields.get('summary', 'Not available')
            
            # Extract description
            description_raw = fields.get('description', {})
            description = self.extract_text_from_nested_dict(description_raw).strip() or 'Not available'
            
            # Extract assignee
            assignee_info = fields.get('assignee')
            assignee = assignee_info.get('displayName', 'Unassigned') if assignee_info else 'Unassigned'
            
            # Extract status
            status_info = fields.get('status', {})
            status = status_info.get('name', 'Unknown')
            
            # Extract created date
            created = fields.get('created', 'Unknown')
            if created != 'Unknown':
                # Format: 2023-10-01T12:00:00.000+0000 -> 2023-10-01
                created = created.split('T')[0]
            
            # Extract reporter
            reporter_info = fields.get('reporter')
            reporter = reporter_info.get('displayName', 'Unknown') if reporter_info else 'Unknown'
            
            # Extract priority
            priority_info = fields.get('priority', {})
            priority = priority_info.get('name', 'Unknown') if isinstance(priority_info, dict) else 'Unknown'
            
            # Check for function lead in custom fields
            function_lead = 'N/A'
            for key, value in fields.items():
                if 'customfield' in key and value:
                    if isinstance(value, dict) and 'displayName' in value:
                        function_lead = value.get('displayName', 'N/A')
                        break
                    elif isinstance(value, str) and 'lead' in key.lower():
                        function_lead = value
                        break
            
            return {
                "jira_ticket_key": ticket_key,
                "summary": summary,
                "assignee": assignee,
                "description": description,
                "status": status,
                "created_date": created,
                "reporter": reporter,
                "priority": priority,
                "function_lead": function_lead,
                "success": True
            }
            
        except Exception as e:
            return {
                "error": f"Error parsing ticket: {str(e)}",
                "success": False
            }

    def _run(self, board_id: Optional[str] = None, days_to_look_back: int = 30, search_text: Optional[str] = None) -> str:
        """Execute the Jira search with caching."""
        try:
            if not board_id:
                return json.dumps({
                    "error": "board_id is required",
                    "success": False
                }, indent=2)

            # Initialize cache manager
            cache_manager = TicketCacheManager()
            
            # Check if cache exists for today
            if cache_manager.cache_exists(board_id, str(days_to_look_back)):
                print(f"✅ Loading tickets from cache: {cache_manager.get_cache_filename(board_id, str(days_to_look_back))}")
                cache_data = cache_manager.load_tickets(board_id, str(days_to_look_back))
                
                if cache_data:
                    # Return cached data
                    return json.dumps({
                        "message": "Loaded from cache",
                        "board_id": board_id,
                        "days_looked_back": days_to_look_back,
                        "search_text": search_text or "all tickets",
                        "count": cache_data.get("tickets", {}).get("count", 0) if isinstance(cache_data.get("tickets"), dict) else len(cache_data.get("tickets", [])),
                        "tickets": cache_data.get("tickets", []),
                        "cached_at": cache_data.get("cached_at"),
                        "from_cache": True,
                        "success": True
                    }, indent=2)

            # Cache doesn't exist, fetch from Jira
            print(f"📡 Fetching tickets from Jira API for board {board_id}...")
            tickets = self.get_tickets_from_board(board_id, days_to_look_back, search_text)
            
            # Format output
            if tickets and tickets[0].get("success") == False:
                # Error occurred
                return json.dumps(tickets[0], indent=2)
            
            if tickets and tickets[0].get("count") == 0:
                # No tickets found
                result = {
                    "message": f"No tickets found matching the search criteria",
                    "board_id": board_id,
                    "days_looked_back": days_to_look_back,
                    "search_text": search_text or "all tickets",
                    "count": 0,
                    "success": True
                }
                return json.dumps(result, indent=2)
            
            # Format successful results
            result = {
                "board_id": board_id,
                "days_looked_back": days_to_look_back,
                "search_text": search_text or "all tickets",
                "count": len(tickets),
                "tickets": tickets,
                "from_cache": False,
                "success": True
            }
            
            # Save to cache
            cache_file = cache_manager.save_tickets(board_id, str(days_to_look_back), result)
            print(f"💾 Saved tickets to cache: {cache_file}")
            result["cache_file"] = cache_file
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Tool execution error: {str(e)}",
                "success": False
            }, indent=2)

