from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
import requests
import json
import datetime
import os


class GoogleCalendarOAuthRequest(BaseModel):
    """Input schema for Google Calendar OAuth Tool."""
    attendee_email: str = Field(..., description="Email address of the attendee to filter events for")
    days: int = Field(default=7, description="Number of days to look ahead from today (default: 7). Use negative values to look back in time")


class GoogleCalendarOAuthTool(BaseTool):
    """Tool for retrieving Google Calendar events for a specific attendee starting from today."""

    name: str = "google_calendar_oauth_tool"
    description: str = (
        "Retrieves events for a specific attendee starting from today. "
        "Matches the exact behavior of get_events_by_attendee function. "
        "Supports both forward (positive days) and backward (negative days) time range lookups."
    )
    args_schema: Type[BaseModel] = GoogleCalendarOAuthRequest

    def get_event_attendees(self, event: Dict) -> List[str]:
        """Extract attendee email addresses from an event - exact same as user's code"""
        attendees = event.get("attendees", [])
        emails = []
        for attendee in attendees:
            email = attendee.get("email", "")
            if email:
                emails.append(email)
        return emails

    def _run(self, attendee_email: str, days: int = 7) -> str:
        """
        Retrieves events for a specific attendee starting from today.
        Matches the exact behavior of get_events_by_attendee function.
        
        Args:
            attendee_email: Email address of the attendee to filter events for
            days: Number of days to look ahead from today (default: 7)
                  Use negative values to look back in time
        
        Returns:
            JSON string with events data matching user's exact format plus daily breakdown
        """
        try:
            # Get credentials from environment variables - FIXED: use os.getenv() not self.get_env()
            access_token = os.getenv('GOOGLE_OAUTH_ACCESS_TKN')
            refresh_token = os.getenv('GOOGLE_OAUTH_REFRESH_TKN')
            client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
            client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_KEY')
            
            if not all([access_token, refresh_token, client_id, client_secret]):
                return json.dumps({
                    "error": "Missing required environment variables",
                    "required": ["GOOGLE_OAUTH_ACCESS_TKN", "GOOGLE_OAUTH_REFRESH_TKN", "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_KEY"],
                    "attendee_email": attendee_email,
                    "days_searched": days,
                    "events_found": 0,
                    "events": [],
                    "daily_breakdown": {}
                })
            
            # Test token validity and refresh if needed
            headers = {"Authorization": f"Bearer {access_token}"}
            test_response = requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary",
                headers=headers
            )
            
            # If token expired (401), refresh it
            if test_response.status_code == 401:
                refresh_data = {
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                    'client_secret': client_secret
                }
                
                refresh_response = requests.post(
                    'https://oauth2.googleapis.com/token',
                    data=refresh_data
                )
                
                if refresh_response.status_code == 200:
                    token_data = refresh_response.json()
                    access_token = token_data.get('access_token')
                    headers = {"Authorization": f"Bearer {access_token}"}
                else:
                    return json.dumps({
                        "error": "Failed to refresh OAuth token",
                        "attendee_email": attendee_email,
                        "days_searched": days, 
                        "events_found": 0,
                        "events": [],
                        "daily_breakdown": {}
                    })
            
            # Calculate date range - FIXED logic
            today = datetime.datetime.now()
            
            if days >= 0:
                # Looking forward from today
                start_datetime = datetime.datetime.combine(today.date(), datetime.time.min)
                end_date = today + datetime.timedelta(days=days)  # This was the issue - should be days, not days+1
                end_datetime = datetime.datetime.combine(end_date.date(), datetime.time.max)
            else:
                # Looking backward  
                start_date = today + datetime.timedelta(days=days)
                start_datetime = datetime.datetime.combine(start_date.date(), datetime.time.min)
                end_datetime = datetime.datetime.combine(today.date(), datetime.time.max)
            
            # Add timezone info (assuming local timezone)
            try:
                start_datetime = start_datetime.astimezone()
                end_datetime = end_datetime.astimezone()
            except:
                # Fallback if astimezone() fails
                start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
                end_datetime = end_datetime.replace(tzinfo=datetime.timezone.utc)
            
            # Fetch events from Google Calendar API
            params = {
                'timeMin': start_datetime.isoformat(),
                'timeMax': end_datetime.isoformat(),
                'singleEvents': 'true',
                'orderBy': 'startTime'
            }
            
            response = requests.get(
                'https://www.googleapis.com/calendar/v3/calendars/primary/events',
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                return json.dumps({
                    "error": f"Google Calendar API error: {response.status_code} - {response.text}",
                    "attendee_email": attendee_email,
                    "days_searched": days,
                    "events_found": 0, 
                    "events": [],
                    "daily_breakdown": {}
                })
            
            data = response.json()
            events = data.get('items', [])
            
            # Filter events by attendee - same logic as user's code
            filtered_events = []
            daily_breakdown = {}
            
            for event in events:
                attendees = self.get_event_attendees(event)
                if attendee_email.lower() in [email.lower() for email in attendees]:
                    # Format event exactly like user's code
                    event_data = {
                        "id": event.get("id", ""),
                        "summary": event.get("summary", "No Title"),
                        "start": event["start"].get("dateTime", event["start"].get("date")),
                        "end": event["end"].get("dateTime", event["end"].get("date")) if "end" in event else None,
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                        "attendees": attendees
                    }
                    filtered_events.append(event_data)
                    
                    # Add to daily breakdown
                    start_time = event_data["start"]
                    if start_time:
                        # Extract date part for grouping
                        if 'T' in start_time:
                            # DateTime format
                            event_date = start_time.split('T')[0]
                        else:
                            # Date-only format
                            event_date = start_time
                        
                        if event_date not in daily_breakdown:
                            daily_breakdown[event_date] = []
                        daily_breakdown[event_date].append(event_data)
            
            return json.dumps({
                "attendee_email": attendee_email,
                "days_searched": days,
                "events_found": len(filtered_events),
                "events": filtered_events,
                "daily_breakdown": daily_breakdown
            })
            
        except Exception as error:
            return json.dumps({
                "error": f"Unexpected error: {str(error)}",
                "attendee_email": attendee_email,
                "days_searched": days,
                "events_found": 0,
                "events": [],
                "daily_breakdown": {}
            })