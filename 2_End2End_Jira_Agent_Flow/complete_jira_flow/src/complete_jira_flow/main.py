#!/usr/bin/env python
import sys
import warnings
import uuid

from datetime import datetime
from pathlib import Path
import os

from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing langfuse
load_dotenv()

from azure_content_safety import GuardrailPipeline

from langfuse import get_client
from langfuse import propagate_attributes

from complete_jira_flow.crew import JiraForresterAgent

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


# Set Langfuse environment variables - use LANGFUSE_HOST for the SDK
os.environ["LANGFUSE_PUBLIC_KEY"] = os.getenv("LANGFUSE_PUBLIC_KEY")
os.environ["LANGFUSE_SECRET_KEY"] = os.getenv("LANGFUSE_SECRET_KEY")
os.environ["LANGFUSE_HOST"] = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

# Debug: Print to verify env vars are loaded correctly
print(f"DEBUG: LANGFUSE_PUBLIC_KEY loaded: {os.environ.get('LANGFUSE_PUBLIC_KEY', 'NOT SET')[:20]}...")
print(f"DEBUG: LANGFUSE_HOST: {os.environ.get('LANGFUSE_HOST', 'NOT SET')}")

# Initialize Langfuse client
langfuse = get_client()

# Initialize Guardrail Pipeline
guardrail_pipeline = GuardrailPipeline()
GUARDRAIL_CONFIG_PATH = Path(__file__).parent / "config" / "config.json"
GUARDRAIL_LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"


def limit_10_words(text: str) -> str:
    """Limit text to first 10 words for Langfuse observation."""
    return " ".join(text.split()[:10]) if text else ""


def check_input_guardrail(user_query: str, username: str = "jira_agent_user") -> tuple[bool, str, dict]:
    """
    Check user input against guardrails before processing.
    
    Args:
        user_query: The user's input query
        username: Username for logging purposes
    
    Returns:
        Tuple of (passed: bool, error_message: str, result: dict)
    """
    try:
        input_result = guardrail_pipeline.run(config_path=str(GUARDRAIL_CONFIG_PATH), user_query=user_query, username=username)
        
        user_data = input_result.get(username, {})
        input_summary = user_data.get('input_results', {}).get('query_timestamp', {}).get('summary', {})
        input_passed = input_summary.get('all_passed', False)
        
        if input_passed:
            return True, "", input_result
        else:
            failed_checks = input_summary.get('failed_functions', [])
            error_msg = f"Input blocked due to: {', '.join(failed_checks)}"
            # Log the blocked attempt
            guardrail_pipeline.save_or_append_log(input_result, log_directory=str(GUARDRAIL_LOG_DIR))
            return False, error_msg, input_result
            
    except Exception as e:
        # Handle guardrail errors gracefully - log but don't block
        print(f"⚠️ Guardrail check warning: {e}")
        return True, "", {}


def check_output_guardrail(generated_text: str, username: str = "jira_agent_user", input_result: dict = None) -> tuple[bool, str]:
    """
    Check model output against guardrails.
    
    Args:
        generated_text: The generated output text
        username: Username for logging purposes
        input_result: Previous input check result for logging
    
    Returns:
        Tuple of (passed: bool, error_message: str)
    """
    try:
        output_result = guardrail_pipeline.run(config_path=str(GUARDRAIL_CONFIG_PATH), generated_text=generated_text, username=username)
        
        user_data = output_result.get(username, {})
        output_summary = user_data.get('output_results', {}).get('query_timestamp', {}).get('summary', {})
        output_passed = output_summary.get('all_passed', True)  # Default to True if not present
        
        # Save complete logs
        if input_result:
            guardrail_pipeline.save_or_append_log(input_result, log_directory=str(GUARDRAIL_LOG_DIR))
        guardrail_pipeline.save_or_append_log(output_result, log_directory=str(GUARDRAIL_LOG_DIR))
        
        if output_passed:
            return True, ""
        else:
            failed_checks = output_summary.get('failed_functions', [])
            return False, f"Output blocked due to: {', '.join(failed_checks)}"
            
    except Exception as e:
        # Handle guardrail errors gracefully - log but don't block
        print(f"⚠️ Output guardrail check warning: {e}")
        return True, ""

    


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
        user_query = input("🔍 Query: ").strip()
    
    if not user_query:
        print("\n❌ Error: Please provide a query.")
        return None
    
    print(f"\n📋 Processing: '{user_query}'")
    print("-" * 60)
    
    # Step 1: Check input against guardrails
    print("\n🛡️ Running input guardrail check...")
    input_passed, error_msg, input_result = check_input_guardrail(user_query)
    
    if not input_passed:
        print(f"\n❌ {error_msg}")
        print("Your query could not be processed due to content safety policies.")
        return None
    
    print("✅ Input guardrail check passed")
    
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
                user_id="jira_agent_user",
                session_id="session_testing_jira_agent",
                tags=["jira-agent-crewai"]
            ):
                crew = JiraForresterAgent().crew()
                result = crew.kickoff(inputs=inputs)
            
            root_obs.update(
                output=limit_10_words(str(result)),
            )
        
        
        
        # Step 2: Check output against guardrails
        print("\n🛡️ Running output guardrail check...")
        output_passed, output_error = check_output_guardrail(str(result), input_result=input_result)
        
        if not output_passed:
            print(f"\n⚠️ {output_error}")
            print("The response was filtered due to content safety policies.")
            return None
        
        print("✅ Output guardrail check passed")
        
        print("\n" + "=" * 80)
        print("📊 RESULT")
        print("=" * 80)
        print(result)
        
       # Flush to ensure traces are sent to Langfuse
        langfuse.flush()
        
        return result
    except Exception as e:
        langfuse.flush()
        raise Exception(f"An error occurred while running the crew: {e}")

