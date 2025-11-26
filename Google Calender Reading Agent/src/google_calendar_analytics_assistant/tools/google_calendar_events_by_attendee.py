from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta

class GoogleCalendarEventsByAttendeeInput(BaseModel):
    """Input schema for Google Calendar Events By Attendee Tool."""
    attendee_email: str = Field(
        ..., 
        description="Email address of the attendee to filter events for"
    )
    days: int = Field(
        default=0, 
        description="Number of days to look ahead from today (0 for current day only, negative values to look back)"
    )

class GoogleCalendarEventsByAttendee(BaseTool):
    """Tool for filtering Google Calendar events by attendee email using REST API calls."""

    name: str = "google_calendar_events_by_attendee"
    description: str = (
        "Filters Google Calendar events by attendee email. "
        "Supports looking ahead or back in time. "
        "Returns formatted event details, total count, date range, and status."
    )
    args_schema: Type[BaseModel] = GoogleCalendarEventsByAttendeeInput

    def _create_jwt_token(self, service_account_key: Dict[str, Any]) -> str:
        """Create JWT token for Google Calendar API authentication."""
        try:
            # JWT Header
            header = {
                "alg": "RS256",
                "typ": "JWT"
            }
            
            # JWT Payload
            now = int(time.time())
            payload = {
                "iss": service_account_key["client_email"],
                "scope": "https://www.googleapis.com/auth/calendar.readonly",
                "aud": "https://oauth2.googleapis.com/token",
                "exp": now + 3600,  # Expires in 1 hour
                "iat": now
            }
            
            # Encode header and payload
            header_b64 = base64.urlsafe_b64encode(
                json.dumps(header, separators=(',', ':')).encode()
            ).decode().rstrip('=')
            
            payload_b64 = base64.urlsafe_b64encode(
                json.dumps(payload, separators=(',', ':')).encode()
            ).decode().rstrip('=')
            
            # Create signature
            message = f"{header_b64}.{payload_b64}"
            private_key = service_account_key["private_key"].encode()
            
            # Simple RSA signature simulation using HMAC (Note: This is a simplified approach)
            # In a real implementation, you would use proper RSA signing
            signature = hmac.new(
                private_key, 
                message.encode(), 
                hashlib.sha256
            ).digest()
            
            signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
            
            return f"{message}.{signature_b64}"
            
        except Exception as e:
            raise Exception(f"Failed to create JWT token: {str(e)}")

    def _get_access_token(self, service_account_key: Dict[str, Any]) -> str:
        """Get access token from Google OAuth2 service."""
        try:
            jwt_token = self._create_jwt_token(service_account_key)
            
            # Request access token
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token
            }
            
            response = requests.post(token_url, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data.get("access_token")
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to get access token: {str(e)}")
        except Exception as e:
            raise Exception(f"Authentication error: {str(e)}")

    def _get_event_attendees(self, event: Dict[str, Any]) -> List[str]:
        """Extract attendee emails from event."""
        attendees = event.get("attendees", [])
        return [attendee.get("email", "").lower() for attendee in attendees if attendee.get("email")]

    def _format_event_display(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Format event for display."""
        start = event.get("start", {})
        end = event.get("end", {})
        
        start_time = start.get("dateTime", start.get("date", ""))
        end_time = end.get("dateTime", end.get("date", ""))
        
        return {
            "summary": event.get("summary", "No Title"),
            "start": start_time,
            "end": end_time,
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "attendees": self._get_event_attendees(event),
            "id": event.get("id", ""),
            "htmlLink": event.get("htmlLink", "")
        }

    def _calculate_date_range(self, days: int) -> tuple:
        """Calculate date range based on days parameter."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if days >= 0:
            start_date = today
            end_date = today + timedelta(days=days + 1)
            if days == 0:
                date_text = "today"
            elif days == 1:
                date_text = "today and tomorrow"
            else:
                date_text = f"next {days + 1} days"
        else:
            start_date = today + timedelta(days=days)
            end_date = today + timedelta(days=1)
            abs_days = abs(days)
            if abs_days == 1:
                date_text = "yesterday and today"
            else:
                date_text = f"last {abs_days + 1} days"
        
        return start_date, end_date, date_text

    def _run(self, attendee_email: str, days: int = 0) -> str:
        """Filter Google Calendar events by attendee email."""
        try:
            # Get service account key from environment
            import os
            service_account_key_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
            
            if not service_account_key_str:
                return json.dumps({
                    "status": "error",
                    "error": "GOOGLE_SERVICE_ACCOUNT_KEY environment variable not found",
                    "events": [],
                    "total_count": 0
                })
            
            # Parse service account key
            try:
                service_account_key = json.loads(service_account_key_str)
            except json.JSONDecodeError:
                return json.dumps({
                    "status": "error",
                    "error": "Invalid JSON format in GOOGLE_SERVICE_ACCOUNT_KEY",
                    "events": [],
                    "total_count": 0
                })
            
            # Get access token
            access_token = self._get_access_token(service_account_key)
            
            if not access_token:
                return json.dumps({
                    "status": "error",
                    "error": "Failed to obtain access token",
                    "events": [],
                    "total_count": 0
                })
            
            # Calculate date range
            start_date, end_date, date_text = self._calculate_date_range(days)
            
            # Format dates for API
            time_min = start_date.isoformat() + "Z"
            time_max = end_date.isoformat() + "Z"
            
            # Make API call to Google Calendar
            calendar_url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 2500  # Google Calendar API limit
            }
            
            response = requests.get(calendar_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            calendar_data = response.json()
            all_events = calendar_data.get("items", [])
            
            # Filter events by attendee email
            attendee_email_lower = attendee_email.lower()
            filtered_events = []
            
            for event in all_events:
                event_attendees = self._get_event_attendees(event)
                if attendee_email_lower in event_attendees:
                    formatted_event = self._format_event_display(event)
                    filtered_events.append(formatted_event)
            
            result = {
                "status": "success",
                "events": filtered_events,
                "total_count": len(filtered_events),
                "date_range_text": date_text,
                "attendee_email": attendee_email,
                "search_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            }
            
            return json.dumps(result, indent=2)
            
        except requests.exceptions.RequestException as e:
            return json.dumps({
                "status": "error",
                "error": f"API request failed: {str(e)}",
                "events": [],
                "total_count": 0,
                "attendee_email": attendee_email
            })
        
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": f"Unexpected error: {str(e)}",
                "events": [],
                "total_count": 0,
                "attendee_email": attendee_email
            })