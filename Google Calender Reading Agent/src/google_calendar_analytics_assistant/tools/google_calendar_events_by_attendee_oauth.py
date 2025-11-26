from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any
import requests
import json
import os
from datetime import datetime, timedelta

class GoogleCalendarEventsByAttendeeOAuthInput(BaseModel):
    """Input schema for Google Calendar Events By Attendee OAuth Tool."""
    attendee_email: str = Field(..., description="Email address to filter events by")
    days: int = Field(default=7, description="Number of days from today to fetch events for")

class GoogleCalendarEventsByAttendeeOAuth(BaseTool):
    """Tool for fetching Google Calendar events filtered by attendee email using OAuth authentication."""

    name: str = "google_calendar_events_by_attendee_oauth"
    description: str = (
        "Fetch Google Calendar events filtered by attendee email using OAuth authentication. "
        "Automatically handles token refresh and returns structured event data including "
        "event details like summary, start time, end time, attendees, location, and description."
    )
    args_schema: Type[BaseModel] = GoogleCalendarEventsByAttendeeOAuthInput

    def _refresh_access_token(self, client_credentials: Dict[str, Any], refresh_token: str) -> str:
        """Refresh the OAuth access token using the refresh token."""
        try:
            refresh_url = "https://oauth2.googleapis.com/token"
            
            refresh_data = {
                "client_id": client_credentials.get("client_id"),
                "client_secret": client_credentials.get("client_secret"),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(refresh_url, data=refresh_data)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get("access_token")
            
        except Exception as e:
            raise Exception(f"Failed to refresh access token: {str(e)}")

    def _is_token_valid(self, access_token: str) -> bool:
        """Check if the access token is valid by making a test API call."""
        try:
            test_url = "https://www.googleapis.com/calendar/v3/calendars/primary"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = requests.get(test_url, headers=headers)
            return response.status_code == 200
            
        except Exception:
            return False

    def _get_valid_access_token(self, client_credentials: Dict[str, Any], access_token: str, refresh_token: str) -> str:
        """Get a valid access token, refreshing if necessary."""
        if self._is_token_valid(access_token):
            return access_token
        else:
            return self._refresh_access_token(client_credentials, refresh_token)

    def _fetch_calendar_events(self, access_token: str, days: int) -> List[Dict[str, Any]]:
        """Fetch calendar events from Google Calendar API."""
        try:
            # Calculate date range
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days)).isoformat() + 'Z'
            
            # Build API URL
            events_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime"
            }
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = requests.get(events_url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json().get("items", [])
            
        except Exception as e:
            raise Exception(f"Failed to fetch calendar events: {str(e)}")

    def _filter_events_by_attendee(self, events: List[Dict[str, Any]], attendee_email: str) -> List[Dict[str, Any]]:
        """Filter events by attendee email."""
        filtered_events = []
        
        for event in events:
            attendees = event.get("attendees", [])
            if any(attendee.get("email", "").lower() == attendee_email.lower() for attendee in attendees):
                # Structure the event data
                structured_event = {
                    "id": event.get("id"),
                    "summary": event.get("summary", "No title"),
                    "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                    "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                    "attendees": [{"email": att.get("email"), "responseStatus": att.get("responseStatus")} 
                                for att in attendees],
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                    "htmlLink": event.get("htmlLink", "")
                }
                filtered_events.append(structured_event)
        
        return filtered_events

    def _run(self, attendee_email: str, days: int = 7) -> str:
        """Execute the Google Calendar events fetch by attendee email."""
        try:
            # Get environment variables
            google_client_credentials = os.getenv("GOOGLE_CLIENT_CREDENTIALS")
            google_access_credential = os.getenv("GOOGLE_ACCESS_CREDENTIAL")  # Renamed from GOOGLE_ACCESS_TOKEN
            google_refresh_credential = os.getenv("GOOGLE_REFRESH_CREDENTIAL")  # Renamed from GOOGLE_REFRESH_TOKEN
            
            if not google_client_credentials:
                return "Error: GOOGLE_CLIENT_CREDENTIALS environment variable is not set."
            
            if not google_access_credential:
                return "Error: GOOGLE_ACCESS_CREDENTIAL environment variable is not set."
            
            if not google_refresh_credential:
                return "Error: GOOGLE_REFRESH_CREDENTIAL environment variable is not set."
            
            # Parse client credentials
            try:
                client_credentials = json.loads(google_client_credentials)
            except json.JSONDecodeError:
                return "Error: GOOGLE_CLIENT_CREDENTIALS is not valid JSON."
            
            # Validate required credentials
            required_fields = ["client_id", "client_secret"]
            for field in required_fields:
                if field not in client_credentials:
                    return f"Error: Missing '{field}' in GOOGLE_CLIENT_CREDENTIALS."
            
            # Get valid access token (refresh if needed)
            try:
                valid_access_token = self._get_valid_access_token(
                    client_credentials, 
                    google_access_credential, 
                    google_refresh_credential
                )
            except Exception as e:
                return f"Error getting valid access token: {str(e)}"
            
            # Fetch calendar events
            try:
                events = self._fetch_calendar_events(valid_access_token, days)
            except Exception as e:
                return f"Error fetching calendar events: {str(e)}"
            
            # Filter events by attendee email
            filtered_events = self._filter_events_by_attendee(events, attendee_email)
            
            if not filtered_events:
                return f"No events found with attendee '{attendee_email}' in the next {days} days."
            
            # Return structured results
            result = {
                "attendee_email": attendee_email,
                "days_searched": days,
                "events_found": len(filtered_events),
                "events": filtered_events
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Error: An unexpected error occurred: {str(e)}"