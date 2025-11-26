from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import json
import csv
import re
from io import StringIO

class ServiceNowDataFormatterInput(BaseModel):
    """Input schema for ServiceNow Data Formatter Tool."""
    raw_data: str = Field(..., description="Raw ServiceNow ticket data as text, JSON string, or structured data")
    data_type: str = Field(default="auto", description="Type of input data: 'json', 'text', or 'auto' for automatic detection")

class ServiceNowDataFormatterTool(BaseTool):
    """Tool for formatting raw ServiceNow ticket data into CSV-ready structure."""

    name: str = "ServiceNow Data Formatter Tool"
    description: str = (
        "Formats raw ServiceNow ticket data into CSV-ready structure. "
        "Extracts ticket information including Ticket ID, Incident ID, Task ID, "
        "Summary/Description, Assigned To, Priority, State, Creation Date, Updated Date. "
        "Returns clean CSV text content with proper headers."
    )
    args_schema: Type[BaseModel] = ServiceNowDataFormatterInput

    def _run(self, raw_data: str, data_type: str = "auto") -> str:
        try:
            # Field mappings
            field_mappings = {
                'Ticket_ID': ['ticket_id', 'number', 'ticket_number', 'sys_id', 'id'],
                'Incident_ID': ['incident_id', 'incident_number', 'inc_number'],
                'Task_ID': ['task_id', 'task_number', 'task', 'ritm_number'],
                'Summary_Description': ['summary', 'description', 'short_description', 'brief_description', 'title'],
                'Assigned_To': ['assigned_to', 'assignee', 'assigned_user', 'owner'],
                'Priority': ['priority', 'urgency', 'impact'],
                'State': ['state', 'status', 'incident_state', 'task_state'],
                'Creation_Date': ['created_on', 'creation_date', 'created', 'opened_at', 'sys_created_on'],
                'Updated_Date': ['updated_on', 'last_updated', 'updated', 'modified', 'sys_updated_on']
            }

            csv_headers = list(field_mappings.keys())
            
            # Auto-detect data type if needed
            if data_type == "auto":
                data_type = self._detect_data_type(raw_data)
            
            # Parse data based on type
            if data_type == "json":
                parsed_data = self._parse_json_data(raw_data)
            else:
                parsed_data = self._parse_text_data(raw_data)
            
            # Ensure parsed_data is a list
            if not isinstance(parsed_data, list):
                parsed_data = [parsed_data] if parsed_data else []
            
            # Format data for CSV
            csv_rows = []
            for item in parsed_data:
                if isinstance(item, dict):
                    row = self._extract_fields(item, field_mappings)
                    csv_rows.append(row)
            
            # Generate CSV content
            csv_content = self._generate_csv(csv_headers, csv_rows)
            
            return csv_content
            
        except Exception as e:
            return f"Error formatting ServiceNow data: {str(e)}"

    def _detect_data_type(self, data: str) -> str:
        """Auto-detect if data is JSON or text format."""
        try:
            data_stripped = data.strip()
            if (data_stripped.startswith('{') and data_stripped.endswith('}')) or \
               (data_stripped.startswith('[') and data_stripped.endswith(']')):
                json.loads(data_stripped)
                return "json"
        except (json.JSONDecodeError, ValueError):
            pass
        return "text"

    def _parse_json_data(self, json_data: str) -> List[Dict[str, Any]]:
        """Parse JSON data and return list of dictionaries."""
        try:
            parsed = json.loads(json_data)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
            else:
                return []
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    def _parse_text_data(self, text_data: str) -> List[Dict[str, Any]]:
        """Parse text data using regex patterns."""
        tickets = []
        
        # Split text into potential ticket blocks
        ticket_blocks = self._split_ticket_blocks(text_data)
        
        for block in ticket_blocks:
            ticket_info = self._extract_from_text_block(block)
            if ticket_info:
                tickets.append(ticket_info)
        
        return tickets if tickets else [self._extract_from_text_block(text_data)]

    def _split_ticket_blocks(self, text: str) -> List[str]:
        """Split text into individual ticket blocks."""
        # Look for ticket number patterns to split blocks
        ticket_pattern = r'(?:INC|RITM|TASK|PRB|CHG)\d{7,}'
        
        # Find all ticket numbers
        matches = list(re.finditer(ticket_pattern, text, re.IGNORECASE))
        
        if len(matches) <= 1:
            return [text]
        
        blocks = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            blocks.append(text[start:end])
        
        return blocks

    def _extract_from_text_block(self, text: str) -> Dict[str, Any]:
        """Extract ticket information from a text block."""
        ticket_info = {}
        
        # Regex patterns for different field formats
        patterns = {
            'ticket_number': r'(?:ticket|number|id)[\s:=-]*([A-Z]{3,4}\d{7,})',
            'incident_number': r'(?:incident|inc)[\s:=-]*([A-Z]{3,4}\d{7,})',
            'task_number': r'(?:task|ritm)[\s:=-]*([A-Z]{3,4}\d{7,})',
            'summary': r'(?:summary|title|description|brief)[\s:=-]*(.*?)(?:\n|$)',
            'assigned_to': r'(?:assigned[\s_]to|assignee|owner)[\s:=-]*(.*?)(?:\n|$)',
            'priority': r'(?:priority|urgency|impact)[\s:=-]*(.*?)(?:\n|$)',
            'state': r'(?:state|status)[\s:=-]*(.*?)(?:\n|$)',
            'created': r'(?:created|opened)[\s:=-]*(.*?)(?:\n|$)',
            'updated': r'(?:updated|modified)[\s:=-]*(.*?)(?:\n|$)'
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Clean up the value
                value = re.sub(r'\s+', ' ', value)
                ticket_info[field] = value
        
        # Try to extract any ticket number as fallback
        if not any(key in ticket_info for key in ['ticket_number', 'incident_number', 'task_number']):
            ticket_match = re.search(r'([A-Z]{3,4}\d{7,})', text, re.IGNORECASE)
            if ticket_match:
                ticket_info['ticket_number'] = ticket_match.group(1)
        
        return ticket_info

    def _extract_fields(self, data: Dict[str, Any], field_mappings: Dict[str, List[str]]) -> List[str]:
        """Extract and map fields according to field mappings."""
        row = []
        
        for csv_field, possible_keys in field_mappings.items():
            value = ""
            
            # Try to find value using possible keys
            for key in possible_keys:
                if key in data:
                    value = str(data[key])
                    break
                # Try case-insensitive match
                for data_key in data.keys():
                    if isinstance(data_key, str) and data_key.lower() == key.lower():
                        value = str(data[data_key])
                        break
                if value:
                    break
            
            # Clean and truncate the value
            value = self._clean_value(value)
            row.append(value)
        
        return row

    def _clean_value(self, value: str) -> str:
        """Clean and format field values."""
        if not value:
            return ""
        
        # Remove line breaks and extra whitespace
        cleaned = re.sub(r'\s+', ' ', str(value).strip())
        
        # Remove special characters that might break CSV
        cleaned = re.sub(r'["\r\n]', ' ', cleaned)
        
        # Truncate very long values
        if len(cleaned) > 500:
            cleaned = cleaned[:497] + "..."
        
        return cleaned

    def _generate_csv(self, headers: List[str], rows: List[List[str]]) -> str:
        """Generate CSV content with headers and data rows."""
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # Write headers
        writer.writerow(headers)
        
        # Write data rows
        for row in rows:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content