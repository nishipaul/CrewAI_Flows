#!/usr/bin/env python
import sys
import warnings
import uuid

from datetime import datetime
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic_core.core_schema import tagged_union_schema

# Load environment variables from .env file BEFORE importing langfuse
load_dotenv()

# ============================================================================
# OTEL Trace Context Propagation Setup (MUST be done before CrewAI imports)
# This enables unified traces instead of separate traces for each LLM call
# ============================================================================
from opentelemetry import trace
from opentelemetry.propagate import set_global_textmap
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Enable OTEL trace context propagation
set_global_textmap(TraceContextTextMapPropagator())

# Instrument HTTP clients to inject traceparent headers
RequestsInstrumentor().instrument()
HTTPXClientInstrumentor().instrument()

print("✅ OTEL trace context propagation enabled")
# ============================================================================

from langfuse import get_client
from langfuse import propagate_attributes

from jira_forrester_agent.crew import JiraForresterAgent

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("LANGFUSE_PUBLIC_KEY")
os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("LANGFUSE_SECRET_KEY")
os.environ["LANGFUSE_BASE_URL"] = os.getenv("LANGFUSE_BASE_URL")

# Initialize Langfuse client
langfuse = get_client()


def limit_10_words(text: str) -> str:
    """Limit text to first 10 words for Langfuse observation."""
    return " ".join(text.split()[:10]) if text else ""


def get_output_dir() -> Path:
    """Get the output directory for markdown reports."""
    output_dir = Path(__file__).parent.parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir


def save_to_markdown(result: str, user_query: str):
    """Save the result to a markdown file named with today's date."""
    output_dir = get_output_dir()
    today = datetime.now()
    filename = f"{today}.md"
    filepath = output_dir / filename
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    content_parts = []
    
    if filepath.exists():
        content_parts.append("\n\n---\n")
    else:
        content_parts.append(f"# Jira Workload Report - {today.strftime('%Y-%m-%d')}\n\n")
    
    content_parts.append(f"## Query: {user_query}\n")
    content_parts.append(f"**Timestamp:** {timestamp}\n\n")
    content_parts.append(str(result))
    content_parts.append("\n")
    
    full_content = "".join(content_parts)
    
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(full_content)
    
    print(f"\n📄 Report saved to: {filepath}")
    return filepath


def run(user_query: str = None):
    """
    Run the Jira Forrester Agent crew.
    
    Args:
        user_query: Query with board ID (e.g., "show board 6088", "rebalance 6088")
    
    Returns:
        The crew execution result
    """
    print("\n" + "=" * 60)
    print("JIRA WORKLOAD AGENT")
    print("=" * 60)
    
    if user_query is None:
        print("\nEnter your query with board ID:")
        print("  Examples:")
        print("    - 'show board 6088'")
        print("    - 'rebalance 6088'")
        print("    - 'display current workload for board 6088'")
        print("")
        user_query = input("🔍 Query: ").strip()
    
    if not user_query:
        print("\n❌ Error: Please provide a query.")
        return None
    
    print(f"\n📋 Processing: '{user_query}'")
    print("-" * 60)
    
    inputs = {
        'user_query': user_query,
        'sprint_name': '26.01 Sprint 2',
        'current_year': str(datetime.now().year)
    }
    
    try:
        # Generate trace metadata
        trace_id = str(uuid.uuid4())
        session_id = "session_testing_jira_agent"
        correlation_id = str(uuid.uuid4())
        
        metadata = {
            "name": "jira-crew-kickoff",
            "userId": "jira_agent_user",
            "sessionId": session_id,
            "correlationId": correlation_id,
            "traceId": trace_id,
            "parentTraceId": None,
            "schema_version": "2.0",
        }
        
        with langfuse.start_as_current_observation(
            as_type="span",
            name="jira-crew-kickoff",
            input=limit_10_words(f"Query: {user_query}"),
            metadata=metadata,
        ) as root_obs:
            
            with propagate_attributes(
                user_id="jira_agent_user",  # not needed
                session_id="session_testing_jira_agent", # not needed
                tags=["jira-agent-crewai"]
            ):
                crew = JiraForresterAgent().crew()
                result = crew.kickoff(inputs=inputs)
            
            root_obs.update(
                output=limit_10_words(str(result)),
            )
        
        # Flush to ensure traces are sent to Langfuse
        langfuse.flush()
        
        print("\n" + "=" * 80)
        print("📊 RESULT")
        print("=" * 80)
        print(result)
        
        save_to_markdown(result, user_query)
        
        return result
    except Exception as e:
        langfuse.flush()
        raise Exception(f"An error occurred while running the crew: {e}")

