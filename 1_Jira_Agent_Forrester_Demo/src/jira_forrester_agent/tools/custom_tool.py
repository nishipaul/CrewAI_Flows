import os
import json
from typing import Type, List, Dict
from pathlib import Path
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import requests
from requests.auth import HTTPBasicAuth

# Load environment variables from .env file (development only)
# In production (CrewAI Enterprise), environment variables are set directly
# and will be available via os.getenv() without needing load_dotenv()
try:
    from dotenv import load_dotenv
    # Only load .env file if it exists (development mode)
    # In production, CrewAI Enterprise sets env vars directly, so we skip this
    env_paths = [
        Path(__file__).parent.parent.parent.parent / '.env',  # Project root from tools/
        Path.cwd() / '.env',  # Current working directory
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            break
    else:
        # Fallback: try loading from current directory (only if file exists)
        if Path('.env').exists():
            load_dotenv(override=False)
except ImportError:
    # dotenv not available - this is fine for production
    pass


class FetchJiraTicketsInput(BaseModel):
    """Input schema for FetchJiraTicketsTool."""
    board_id: int = Field(..., description="Jira board ID to fetch tickets from")
    sprint_name: str = Field(default="26.01 Sprint 2", description="Sprint name to filter tickets")


class FetchJiraTicketsTool(BaseTool):
    name: str = "fetch_jira_tickets"
    description: str = (
        "Fetches all Jira tickets from the specified board for the given sprint. "
        "Returns JSON with assigned tickets and unassigned tickets separately."
    )
    args_schema: Type[BaseModel] = FetchJiraTicketsInput

    def _run(self, board_id: int, sprint_name: str = "26.01 Sprint 2") -> str:
        """Fetch tickets from Jira board and return as JSON string."""
        assigned_tickets = []
        unassigned_tickets = []

        jira_domain = os.getenv('JIRA_DOMAIN')
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_tkn = os.getenv('JIRA_API_TKN')

        if not all([jira_domain, jira_email, jira_api_tkn]):
            missing = []
            if not jira_domain:
                missing.append('JIRA_DOMAIN')
            if not jira_email:
                missing.append('JIRA_EMAIL')
            if not jira_api_tkn:
                missing.append('JIRA_API_TKN')
            return json.dumps({
                "error": f"Missing required environment variables: {', '.join(missing)}",
                "success": False
            })

        # Strip any quotes that might be in the .env file values
        jira_domain = jira_domain.strip().strip('"').strip("'")
        jira_email = jira_email.strip().strip('"').strip("'")
        jira_api_tkn = jira_api_tkn.strip().strip('"').strip("'")

        auth = HTTPBasicAuth(jira_email, jira_api_tkn)

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        start_at = 0
        max_results = 10

        jql = f'sprint = "{sprint_name}"'

        url = f"https://{jira_domain}/rest/agile/1.0/board/{board_id}/issue"
        
        # Fetch all tickets with pagination
        while True:
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': max_results,
                'fields': 'summary,description,assignee,status,created,reporter,priority,sprint,customfield_10004'
            }

            try:
                response = requests.get(url, auth=auth, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    return json.dumps({
                        "error": f"Board ID {board_id} does not exist or is not accessible.",
                        "success": False
                    })
                return json.dumps({
                    "error": f"Failed to fetch tickets: {str(e)}",
                    "success": False
                })
            except requests.exceptions.RequestException as e:
                return json.dumps({
                    "error": f"Failed to fetch tickets: {str(e)}",
                    "success": False
                })

            issues = data.get('issues', [])

            for issue in issues:
                fields = issue.get('fields', {})
                assignee = fields.get('assignee')
                priority = fields.get('priority')
                status = fields.get('status')
                sprint = fields.get('sprint')
                
                candidate_name = assignee.get('displayName', 'Unassigned') if assignee else 'Unassigned'
                account_id = assignee.get('accountId', '') if assignee else ''
                
                ticket_data = {
                    "TicketKey": issue.get('key', 'Unknown'),
                    "Candidate": candidate_name,
                    "AccountId": account_id,
                    "CandidateEmail": assignee.get('emailAddress', '') if assignee else '',
                    "Priority": priority.get('name', 'Unknown') if priority else 'Unknown',
                    "Status": status.get('name', 'Unknown') if status else 'Unknown',
                    "StoryPoints": fields.get('customfield_10004', 0) or 0,
                    "Sprint": sprint.get('name', 'Unknown') if sprint else 'Unknown',
                    "Summary": fields.get('summary', '')
                }
                
                if candidate_name == 'Unassigned':
                    unassigned_tickets.append(ticket_data)
                else:
                    assigned_tickets.append(ticket_data)

            # Check if there are more results
            total = data.get('total', 0)
            start_at += len(issues)
            if start_at >= total or len(issues) == 0:
                break

        return json.dumps({
            "success": True,
            "board_id": board_id,
            "assigned_count": len(assigned_tickets),
            "unassigned_count": len(unassigned_tickets),
            "tickets": assigned_tickets,
            "unassigned_tickets": unassigned_tickets
        })


class CalculateWorkloadInput(BaseModel):
    """Input schema for CalculateWorkloadTool."""
    ticket_data: str = Field(..., description="The complete JSON string output from fetch_jira_tickets tool")
    action: str = Field(default="rebalance", description="Action: 'show' or 'rebalance'")


class CalculateWorkloadTool(BaseTool):
    name: str = "calculate_workload"
    description: str = (
        "Analyzes ticket data and generates rebalancing report. "
        "For 'rebalance': Shows current workload, suggested reassignments, assigns unassigned tickets (REAL), and projected table. "
        "Only moves To Do tickets with Low/Medium priority. Never touches High priority."
    )
    args_schema: Type[BaseModel] = CalculateWorkloadInput

    def _build_summary(self, ticket_details: List[Dict]) -> Dict[str, Dict]:
        """Build candidate summary from ticket details."""
        candidate_summary = {}
        
        for ticket in ticket_details:
            if not isinstance(ticket, dict):
                continue
            
            name = ticket.get('Candidate', 'Unknown')
            
            # Skip Unassigned
            if name == 'Unassigned':
                continue
                
            email = ticket.get('CandidateEmail', '')
            account_id = ticket.get('AccountId', '')
            story_points = ticket.get('StoryPoints', 0) or 0
            priority = str(ticket.get('Priority', '')).lower()
            status = str(ticket.get('Status', '')).lower()

            if name not in candidate_summary:
                candidate_summary[name] = {
                    "Name": name,
                    "Email": email,
                    "AccountId": account_id,
                    "NoOfTickets": 0,
                    "ToDo": 0,
                    "InProgress": 0,
                    "Completed": 0,
                    "TotalStoryPoints": 0,
                    "LowPriorityIncomplete": 0,
                    "MediumPriorityIncomplete": 0,
                    "HighPriorityIncomplete": 0,
                    "ReassignableTickets": []
                }

            candidate_summary[name]["NoOfTickets"] += 1
            candidate_summary[name]["TotalStoryPoints"] += story_points
            if email and not candidate_summary[name]["Email"]:
                candidate_summary[name]["Email"] = email
            if account_id and not candidate_summary[name]["AccountId"]:
                candidate_summary[name]["AccountId"] = account_id

            if status in ["new", "reopened", "to do", "open"]:
                candidate_summary[name]["ToDo"] += 1
            elif status == "in progress":
                candidate_summary[name]["InProgress"] += 1
            elif status in ["closed", "done", "completed", "resolved"]:
                candidate_summary[name]["Completed"] += 1

            if status in ["new", "reopened", "to do", "in progress", "open"]:
                if priority == "low":
                    candidate_summary[name]["LowPriorityIncomplete"] += 1
                elif priority == "medium":
                    candidate_summary[name]["MediumPriorityIncomplete"] += 1
                elif priority == "high":
                    candidate_summary[name]["HighPriorityIncomplete"] += 1

            # Only To Do/New with Low/Medium priority can be reassigned (NOT High priority)
            if status in ["new", "to do", "open"] and priority in ["low", "medium"]:
                candidate_summary[name]["ReassignableTickets"].append({
                    "TicketKey": ticket.get('TicketKey', ''),
                    "Priority": ticket.get('Priority', ''),
                    "Status": ticket.get('Status', ''),
                    "Summary": ticket.get('Summary', ''),
                    "StoryPoints": story_points
                })
        
        return candidate_summary

    def _format_table(self, candidates_list: List[Dict]) -> str:
        """Format candidate summary as markdown table."""
        lines = []
        lines.append("| Name | No of Tickets | To Do | In Progress | Completed | Total Story Points | Low Priority Incomplete | Medium Priority Incomplete | High Priority Incomplete |")
        lines.append("|--------------------|---------------|-------|-------------|-----------|--------------------|-----------------------|---------------------------|--------------------------|")
        
        for c in candidates_list:
            row = f"| {c['Name']:<18} | {c['NoOfTickets']:<13} | {c['ToDo']:<5} | {c['InProgress']:<11} | {c['Completed']:<9} | {c['TotalStoryPoints']:<18} | {c['LowPriorityIncomplete']:<21} | {c['MediumPriorityIncomplete']:<25} | {c['HighPriorityIncomplete']:<24} |"
            lines.append(row)
        
        return "\n".join(lines)

    def _smart_rebalance(self, candidate_summary: Dict[str, Dict]) -> List[Dict]:
        """
        Smart rebalancing: redistribute To Do tickets from high workload to low workload.
        Moves one ticket at a time from the MOST overloaded to the LEAST loaded.
        Only moves tickets with To Do/New status AND Low/Medium priority.
        """
        candidates = list(candidate_summary.values())
        
        if len(candidates) < 2:
            return []
        
        suggestions = []
        
        # Track current To Do counts for simulation
        current_todo = {c["Name"]: c["ToDo"] for c in candidates}
        
        # Track available reassignable tickets per candidate
        available_tickets = {}
        for c in candidates:
            available_tickets[c["Name"]] = list(c.get("ReassignableTickets", []))
        
        # Keep rebalancing until workload is balanced
        while True:
            # Sort by current To Do count (highest first)
            sorted_by_todo = sorted(candidates, key=lambda x: current_todo[x["Name"]], reverse=True)
            
            # Find the person with MOST To Do who has reassignable tickets
            giver = None
            for c in sorted_by_todo:
                if available_tickets[c["Name"]]:
                    giver = c
                    break
            
            if not giver:
                break
            
            # Find the person with LEAST To Do (last in sorted list)
            receiver = None
            for c in reversed(sorted_by_todo):
                if c["Name"] != giver["Name"]:
                    receiver = c
                    break
            
            if not receiver:
                break
            
            # Check if rebalancing makes sense (giver has at least 2 more To Do than receiver)
            if current_todo[giver["Name"]] <= current_todo[receiver["Name"]] + 1:
                break
            
            # Move one ticket from giver to receiver
            ticket = available_tickets[giver["Name"]].pop(0)
            
            suggestions.append({
                "TicketKey": ticket["TicketKey"],
                "Status": ticket["Status"],
                "Priority": ticket["Priority"],
                "StoryPoints": ticket["StoryPoints"],
                "FromName": giver["Name"],
                "ToName": receiver["Name"]
            })
            
            # Update simulated counts
            current_todo[giver["Name"]] -= 1
            current_todo[receiver["Name"]] += 1
        
        return suggestions

    def _assign_unassigned_tickets(self, unassigned_tickets: List[Dict], candidate_summary: Dict[str, Dict]) -> tuple:
        """Assign unassigned tickets to members with least workload - REAL assignment."""
        if not unassigned_tickets or not candidate_summary:
            return [], []
        
        # Get Jira credentials
        jira_domain = os.getenv('JIRA_DOMAIN')
        jira_email = os.getenv('JIRA_EMAIL')
        jira_api_tkn = os.getenv('JIRA_API_TKN')

        if not all([jira_domain, jira_email, jira_api_tkn]):
            return [], [{"ticket": "ALL", "reason": "Missing Jira credentials"}]

        # Strip any quotes that might be in the environment variable values
        jira_domain = jira_domain.strip().strip('"').strip("'")
        jira_email = jira_email.strip().strip('"').strip("'")
        jira_api_tkn = jira_api_tkn.strip().strip('"').strip("'")

        auth = HTTPBasicAuth(jira_email, jira_api_tkn)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Track current workload for distribution
        workload = {name: {"ToDo": c["ToDo"], "AccountId": c.get("AccountId", "")} 
                    for name, c in candidate_summary.items()}
        
        assignments = []
        failed_assignments = []
        
        for ticket in unassigned_tickets:
            # Find person with least To Do
            sorted_members = sorted(workload.items(), key=lambda x: x[1]["ToDo"])
            
            if not sorted_members:
                failed_assignments.append({"ticket": ticket["TicketKey"], "reason": "No members available"})
                continue
            
            assignee_name = sorted_members[0][0]
            assignee_account_id = sorted_members[0][1]["AccountId"]
            
            if not assignee_account_id:
                failed_assignments.append({"ticket": ticket["TicketKey"], "reason": f"No account ID for {assignee_name}"})
                continue
            
            # Make the actual assignment in Jira
            url = f"https://{jira_domain}/rest/api/3/issue/{ticket['TicketKey']}/assignee"
            payload = {"accountId": assignee_account_id}
            
            try:
                response = requests.put(url, auth=auth, headers=headers, json=payload)
                response.raise_for_status()
                
                assignments.append({
                    "TicketKey": ticket["TicketKey"],
                    "Priority": ticket.get("Priority", ""),
                    "Status": ticket.get("Status", ""),
                    "StoryPoints": ticket.get("StoryPoints", 0),
                    "AssignedTo": assignee_name,
                    "Reason": f"{assignee_name} has least To Do tasks ({workload[assignee_name]['ToDo']})"
                })
                
                # Update workload
                workload[assignee_name]["ToDo"] += 1
                
            except requests.exceptions.RequestException as e:
                failed_assignments.append({"ticket": ticket["TicketKey"], "reason": str(e)})
        
        return assignments, failed_assignments

    def _run(self, ticket_data: str, action: str = "rebalance") -> str:
        """Calculate workload analysis and return formatted markdown report."""
        # Parse input
        ticket_details = []
        unassigned_tickets = []
        
        try:
            if isinstance(ticket_data, str):
                data = json.loads(ticket_data)
            else:
                data = ticket_data
            
            if isinstance(data, dict):
                if not data.get('success', True):
                    return f"Error: {data.get('error', 'Unknown error')}"
                ticket_details = data.get('tickets', [])
                unassigned_tickets = data.get('unassigned_tickets', [])
            elif isinstance(data, list):
                ticket_details = data
        except (json.JSONDecodeError, Exception) as e:
            return f"Error: Failed to parse data - {str(e)}"

        # Filter out Unassigned from assigned tickets
        ticket_details = [t for t in ticket_details if t.get('Candidate', 'Unassigned') != 'Unassigned']

        if not ticket_details:
            return "No assigned tickets found."

        # Build current summary
        current_summary = self._build_summary(ticket_details)
        current_list = sorted(
            list(current_summary.values()),
            key=lambda x: x["ToDo"],
            reverse=True
        )
        
        current_table = self._format_table(current_list)

        # For "show" action - just return current table
        if action.lower() == "show":
            report = []
            report.append("## Current Workload")
            report.append("")
            report.append(current_table)
            if unassigned_tickets:
                report.append("")
                report.append(f"**Unassigned Tickets:** {len(unassigned_tickets)}")
            return "\n".join(report)

        # For "rebalance" action - full report with suggestions AND real assignment of unassigned
        suggestions = self._smart_rebalance(current_summary)
        
        # Build the report
        report = []
        report.append("## Current Workload")
        report.append("")
        report.append(current_table)
        
        # Suggested Reassignments section
        report.append("")
        report.append("---")
        report.append("")
        report.append("### Suggested Reassignments")
        report.append("")
        
        if not suggestions:
            report.append("Workload is already balanced or no eligible tickets to move (only To Do with Low/Medium priority can be reassigned).")
        else:
            report.append("| Ticket Key | Status | Priority | Story Points | From | To |")
            report.append("|------------|--------|----------|--------------|--------------|---------------|")
            for s in suggestions:
                report.append(f"| {s['TicketKey']} | {s['Status']} | {s['Priority']} | {s['StoryPoints']} | {s['FromName']} | {s['ToName']} |")
        
        # Unassigned Tickets Assignment section (REAL assignment)
        assignments = []
        failed_assignments = []
        
        report.append("")
        report.append("---")
        report.append("")
        report.append("### Unassigned Tickets - ASSIGNING NOW")
        report.append("")
        
        if unassigned_tickets:
            report.append(f"Found {len(unassigned_tickets)} unassigned ticket(s). Assigning to team members with least workload...")
            report.append("")
            
            assignments, failed_assignments = self._assign_unassigned_tickets(unassigned_tickets, current_summary)
            
            if assignments:
                report.append("| Ticket Key | Status | Priority | Assigned To | Reason |")
                report.append("|------------|--------|----------|-------------|--------|")
                for a in assignments:
                    report.append(f"| {a['TicketKey']} | {a['Status']} | {a['Priority']} | {a['AssignedTo']} | {a['Reason']} |")
            
            if failed_assignments:
                report.append("")
                report.append("**Failed Assignments:**")
                for f in failed_assignments:
                    report.append(f"  • {f['ticket']}: {f['reason']}")
        else:
            report.append("No unassigned tickets found.")
        
        # Build projected workload (after suggestions + assignments)
        projected_tickets = list(ticket_details)
        
        # Apply suggestion changes (simulated)
        suggestion_map = {s["TicketKey"]: s["ToName"] for s in suggestions}
        for i, ticket in enumerate(projected_tickets):
            if ticket.get("TicketKey") in suggestion_map:
                projected_tickets[i] = ticket.copy()
                projected_tickets[i]["Candidate"] = suggestion_map[ticket["TicketKey"]]
        
        # Add assigned tickets to projected
        for a in assignments:
            projected_tickets.append({
                "TicketKey": a["TicketKey"],
                "Candidate": a["AssignedTo"],
                "Priority": a["Priority"],
                "Status": a["Status"],
                "StoryPoints": a.get("StoryPoints", 0)
            })
        
        projected_summary = self._build_summary(projected_tickets)
        projected_list = sorted(
            list(projected_summary.values()),
            key=lambda x: x["ToDo"],
            reverse=True
        )
        projected_table = self._format_table(projected_list)
        
        report.append("")
        report.append("---")
        report.append("")
        report.append("### Projected Workload After Rebalancing")
        report.append("")
        report.append(projected_table)
        
        # Summary
        report.append("")
        report.append("---")
        report.append("")
        report.append("### Summary")
        report.append("")
        report.append(f"• Total tickets suggested for redistribution: {len(suggestions)}")
        report.append(f"• Total unassigned tickets assigned: {len(assignments)}")
        report.append("")
        
        if suggestions:
            by_from = {}
            by_to = {}
            for s in suggestions:
                if s["FromName"] not in by_from:
                    by_from[s["FromName"]] = []
                by_from[s["FromName"]].append(s["TicketKey"])
                
                if s["ToName"] not in by_to:
                    by_to[s["ToName"]] = []
                by_to[s["ToName"]].append(s["TicketKey"])
            
            report.append("**Suggested Reassignments:**  ")
            report.append("*From:*  ")
            for name, tickets in by_from.items():
                report.append(f"  • {name}: {len(tickets)} ticket(s) → {', '.join(tickets)}  ")
            report.append("")
            report.append("*To:*  ")
            for name, tickets in by_to.items():
                report.append(f"  • {name}: receives {len(tickets)} ticket(s) → {', '.join(tickets)}  ")
            report.append("")
        
        if assignments:
            report.append("**Unassigned Tickets Assigned (DONE):**  ")
            for a in assignments:
                report.append(f"  • {a['TicketKey']} → {a['AssignedTo']} ({a['Reason']})  ")
            report.append("")
        
        report.append("---")
        report.append("")
        report.append("**Note:** Suggested reassignments are suggestions only. Unassigned ticket assignments have been completed in Jira.")
        
        return "\n".join(report)
