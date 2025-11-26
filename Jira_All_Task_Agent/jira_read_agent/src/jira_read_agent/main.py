#!/usr/bin/env python
import sys
import warnings

from datetime import datetime

from jira_read_agent.crew import JiraReadAgent

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew with Jira ticket search and conversational follow-up.
    """
    print("\n" + "="*80)
    print("🎯 JIRA TICKET SEARCH & ANALYSIS AGENT")
    print("="*80)
    
    # Get initial search parameters
    board_id = input("\n📋 Enter Jira board ID (default: 356): ").strip() or "356"
    days = input("📅 Enter days to look back (default: 30): ").strip() or "30"
    
    print("\n" + "-"*80)
    print("💡 You can now search for tickets and ask follow-up questions!")
    print("   Examples: 'content safety', 'who is working on X?', 'since when?'")
    print("   Type 'exit' or 'quit' to end the conversation.")
    print("-"*80 + "\n")
    
    # Initialize the crew once
    crew = JiraReadAgent().crew()
    
    # Conversational loop
    while True:
        user_query = input("🔍 Your question: ").strip()
        
        if not user_query:
            print("⚠️  Please enter a question.\n")
            continue
            
        if user_query.lower() in ['exit', 'quit', 'bye', 'end']:
            print("\n👋 Thank you for using the Jira Agent! Goodbye!\n")
            break
        
        inputs = {
            'board_key': board_id,
            'days': days,
            'user_query': user_query
        }

        try:
            print("\n🤖 Processing your request...\n")
            result = crew.kickoff(inputs=inputs)
            print("\n" + "="*80)
            print("📊 RESPONSE:")
            print("="*80)
            print(result)
            print("="*80 + "\n")
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            print("Please try again or type 'exit' to quit.\n")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        JiraReadAgent().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        JiraReadAgent().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }

    try:
        JiraReadAgent().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        result = JiraReadAgent().crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
