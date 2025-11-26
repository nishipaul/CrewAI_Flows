"""
Ticket Cache Manager
Handles saving and loading Jira tickets to/from files
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


class TicketCacheManager:
    """Manages caching of Jira tickets to files"""
    
    def __init__(self, cache_dir: str = "ticket_cache"):
        """
        Initialize the cache manager
        
        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
    
    def get_cache_filename(self, board_id: str, days: str) -> str:
        """
        Generate cache filename based on board ID, days, and today's date
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            
        Returns:
            Filename in format: {board_id}_{days}_{YYYY-MM-DD}.json
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return f"{board_id}_{days}_{today}.json"
    
    def get_cache_filepath(self, board_id: str, days: str) -> Path:
        """
        Get full path to cache file
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            
        Returns:
            Full path to cache file
        """
        filename = self.get_cache_filename(board_id, days)
        return self.cache_dir / filename
    
    def cache_exists(self, board_id: str, days: str) -> bool:
        """
        Check if cache file exists for today
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            
        Returns:
            True if cache file exists, False otherwise
        """
        filepath = self.get_cache_filepath(board_id, days)
        return filepath.exists()
    
    def save_tickets(self, board_id: str, days: str, tickets_data: Dict[str, Any]) -> str:
        """
        Save tickets data to cache file
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            tickets_data: Dictionary containing tickets data
            
        Returns:
            Path to saved cache file
        """
        filepath = self.get_cache_filepath(board_id, days)
        
        # Add metadata
        cache_data = {
            "board_id": board_id,
            "days": days,
            "cached_at": datetime.now().isoformat(),
            "tickets": tickets_data
        }
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        return str(filepath)
    
    def load_tickets(self, board_id: str, days: str) -> Optional[Dict[str, Any]]:
        """
        Load tickets data from cache file
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            
        Returns:
            Dictionary containing tickets data, or None if cache doesn't exist
        """
        if not self.cache_exists(board_id, days):
            return None
        
        filepath = self.get_cache_filepath(board_id, days)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return cache_data
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None
    
    def get_all_assignees(self, board_id: str, days: str) -> list:
        """
        Get list of all unique assignees from cached tickets
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            
        Returns:
            List of unique assignee names
        """
        cache_data = self.load_tickets(board_id, days)
        if not cache_data:
            return []
        
        assignees = set()
        tickets = cache_data.get("tickets", {})
        
        # Extract assignees from tickets
        if isinstance(tickets, dict):
            for ticket in tickets.values():
                if isinstance(ticket, dict) and "assignee" in ticket:
                    assignee = ticket["assignee"]
                    if assignee and assignee != "Unassigned":
                        assignees.add(assignee)
        elif isinstance(tickets, list):
            for ticket in tickets:
                if isinstance(ticket, dict) and "assignee" in ticket:
                    assignee = ticket["assignee"]
                    if assignee and assignee != "Unassigned":
                        assignees.add(assignee)
        
        return sorted(list(assignees))
    
    def get_tickets_for_assignee(self, board_id: str, days: str, assignee_name: str) -> list:
        """
        Get all tickets for a specific assignee
        
        Args:
            board_id: Jira board ID
            days: Number of days to look back
            assignee_name: Name of the assignee
            
        Returns:
            List of tickets assigned to the specified assignee
        """
        cache_data = self.load_tickets(board_id, days)
        if not cache_data:
            return []
        
        tickets = cache_data.get("tickets", {})
        assignee_tickets = []
        
        # Filter tickets by assignee
        if isinstance(tickets, dict):
            for ticket in tickets.values():
                if isinstance(ticket, dict) and ticket.get("assignee", "").lower() == assignee_name.lower():
                    assignee_tickets.append(ticket)
        elif isinstance(tickets, list):
            for ticket in tickets:
                if isinstance(ticket, dict) and ticket.get("assignee", "").lower() == assignee_name.lower():
                    assignee_tickets.append(ticket)
        
        return assignee_tickets
    
    def clean_old_caches(self, keep_days: int = 7):
        """
        Remove cache files older than specified days
        
        Args:
            keep_days: Number of days to keep cache files
        """
        today = datetime.now()
        
        for filepath in self.cache_dir.glob("*.json"):
            # Extract date from filename
            parts = filepath.stem.split("_")
            if len(parts) >= 3:
                try:
                    file_date_str = parts[-1]
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                    days_old = (today - file_date).days
                    
                    if days_old > keep_days:
                        filepath.unlink()
                        print(f"Removed old cache: {filepath.name}")
                except Exception as e:
                    print(f"Error processing {filepath.name}: {e}")

