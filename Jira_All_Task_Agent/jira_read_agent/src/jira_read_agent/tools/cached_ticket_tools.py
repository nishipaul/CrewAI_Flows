"""
Tools for working with cached ticket data
"""
from crewai.tools import BaseTool
from typing import Type, Optional, Any
from pydantic import BaseModel, Field
import json
from .ticket_cache_manager import TicketCacheManager


class GetAllAssigneesInput(BaseModel):
    """Input for GetAllAssignees tool"""
    board_id: str = Field(..., description="Jira board ID")
    days: str = Field(..., description="Number of days to look back")


class GetAllAssignees(BaseTool):
    name: str = "get_all_assignees"
    description: str = "Get list of all assignees from cached ticket data. Use this to validate assignee names or list all team members."
    args_schema: Type[BaseModel] = GetAllAssigneesInput
    
    def _run(self, board_id: str, days: str) -> str:
        """Get all assignees from cached data"""
        cache_manager = TicketCacheManager()
        assignees = cache_manager.get_all_assignees(board_id, days)
        
        if not assignees:
            return "No assignees found in cached data. Please ensure tickets have been fetched first."
        
        return json.dumps({
            "assignees": assignees,
            "count": len(assignees)
        }, indent=2)


class GetAssigneeTicketsInput(BaseModel):
    """Input for GetAssigneeTickets tool"""
    board_id: str = Field(..., description="Jira board ID")
    days: str = Field(..., description="Number of days to look back")
    assignee_name: str = Field(..., description="Name of the assignee to get tickets for")


class GetAssigneeTickets(BaseTool):
    name: str = "get_assignee_tickets"
    description: str = "Get all tickets for a specific assignee from cached data. Use this when user asks for a specific person's tickets."
    args_schema: Type[BaseModel] = GetAssigneeTicketsInput
    
    def _run(self, board_id: str, days: str, assignee_name: str) -> str:
        """Get tickets for specific assignee from cached data"""
        cache_manager = TicketCacheManager()
        
        # First check if assignee exists
        all_assignees = cache_manager.get_all_assignees(board_id, days)
        
        # Case-insensitive search for assignee
        assignee_found = None
        for assignee in all_assignees:
            if assignee.lower() == assignee_name.lower():
                assignee_found = assignee
                break
        
        if not assignee_found:
            return json.dumps({
                "error": f"Assignee '{assignee_name}' not found",
                "available_assignees": all_assignees,
                "message": f"Please choose from the available assignees listed above."
            }, indent=2)
        
        # Get tickets for the assignee
        tickets = cache_manager.get_tickets_for_assignee(board_id, days, assignee_found)
        
        if not tickets:
            return json.dumps({
                "assignee": assignee_found,
                "tickets": [],
                "count": 0,
                "message": f"No tickets found for {assignee_found}"
            }, indent=2)
        
        return json.dumps({
            "assignee": assignee_found,
            "tickets": tickets,
            "count": len(tickets)
        }, indent=2)


class LoadCachedTicketsInput(BaseModel):
    """Input for LoadCachedTickets tool"""
    board_id: str = Field(..., description="Jira board ID")
    days: str = Field(..., description="Number of days to look back")


class LoadCachedTickets(BaseTool):
    name: str = "load_cached_tickets"
    description: str = "Load all tickets from cache file. Use this to get complete ticket data without calling Jira API."
    args_schema: Type[BaseModel] = LoadCachedTicketsInput
    
    def _run(self, board_id: str, days: str) -> str:
        """Load all tickets from cache"""
        cache_manager = TicketCacheManager()
        cache_data = cache_manager.load_tickets(board_id, days)
        
        if not cache_data:
            return json.dumps({
                "error": "No cached data found",
                "message": f"Cache file for board {board_id} with {days} days not found. Tickets need to be fetched first."
            }, indent=2)
        
        return json.dumps(cache_data, indent=2)


class CheckCacheExistsInput(BaseModel):
    """Input for CheckCacheExists tool"""
    board_id: str = Field(..., description="Jira board ID")
    days: str = Field(..., description="Number of days to look back")


class CheckCacheExists(BaseTool):
    name: str = "check_cache_exists"
    description: str = "Check if cache file exists for the given board and timeframe. Returns True if cache exists, False otherwise."
    args_schema: Type[BaseModel] = CheckCacheExistsInput
    
    def _run(self, board_id: str, days: str) -> str:
        """Check if cache exists"""
        cache_manager = TicketCacheManager()
        exists = cache_manager.cache_exists(board_id, days)
        
        cache_file = cache_manager.get_cache_filename(board_id, days)
        
        return json.dumps({
            "cache_exists": exists,
            "cache_file": cache_file,
            "board_id": board_id,
            "days": days
        }, indent=2)

