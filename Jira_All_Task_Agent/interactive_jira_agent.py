#!/usr/bin/env python
"""
Interactive Jira Read Agent - Conversational Interface
"""
from jira_read_agent.src.jira_read_agent.crew import JiraReadAgent

def interactive_jira_agent():
    """Interactive conversation with Jira agent"""
    
    print("="*80)
    print("🤖 INTERACTIVE JIRA ASSISTANT")
    print("="*80)
    print()
    
    # Get initial search parameters
    board_id = input("Enter board ID (default: 356): ").strip() or "356"
    days = input("Enter days to look back (default: 30): ").strip() or "30"
    
    print("\n" + "="*80)
    print(f"📋 Searching in board ID: {board_id} | Last {days} days")
    print("="*80)
    print()
    
    # Initial query
    user_query = input("What would you like to know about Jira tickets? ").strip()
    
    if not user_query:
        print("No query provided. Exiting...")
        return
    
    # Store conversation context
    conversation_history = []
    tickets_data = None
    
    while True:
        print("\n" + "-"*80)
        print("🔍 Processing your request...")
        print("-"*80 + "\n")
        
        try:
            # Prepare inputs
            inputs = {
                'board_key': board_id,
                'days': days,
                'user_query': user_query,
                'conversation_history': '\n'.join(conversation_history) if conversation_history else 'First query'
            }
            
            # Run the crew
            crew = JiraReadAgent().crew()
            result = crew.kickoff(inputs=inputs)
            
            # Display result
            print("\n" + "="*80)
            print("🤖 ASSISTANT RESPONSE:")
            print("="*80)
            print(result)
            print("="*80 + "\n")
            
            # Store in conversation history
            conversation_history.append(f"User: {user_query}")
            conversation_history.append(f"Assistant: {result}")
            
            # Ask for continuation
            continue_chat = input("\n💬 Do you have any follow-up questions? (yes/no): ").strip().lower()
            
            if continue_chat in ['no', 'n', 'exit', 'quit', 'bye']:
                print("\n" + "="*80)
                print("👋 Thank you for using the Jira Assistant! Goodbye!")
                print("="*80)
                break
            
            # Get next query
            user_query = input("\n❓ What else would you like to know? ").strip()
            
            if not user_query:
                print("\n" + "="*80)
                print("👋 No query provided. Goodbye!")
                print("="*80)
                break
                
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("👋 Session interrupted. Goodbye!")
            print("="*80)
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            retry = input("\nWould you like to try again? (yes/no): ").strip().lower()
            if retry not in ['yes', 'y']:
                break
            user_query = input("\n❓ What would you like to know? ").strip()

if __name__ == "__main__":
    interactive_jira_agent()

