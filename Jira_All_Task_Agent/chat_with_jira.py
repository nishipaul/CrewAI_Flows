#!/usr/bin/env python
"""
Simple Interactive Jira Chat Agent
"""
from jira_read_agent.src.jira_read_agent.crew import JiraReadAgent

def main():
    print("\n" + "="*80)
    print("🤖 JIRA CHAT ASSISTANT")
    print("="*80)
    print("I can help you search and analyze Jira tickets!")
    print("="*80 + "\n")
    
    # Setup
    board_id = input("📋 Board ID (default: 356): ").strip() or "356"
    days = input("📅 Days to look back (default: 30): ").strip() or "30"
    
    print(f"\n✅ Connected to board ID: {board_id} | Searching last {days} days\n")
    print("="*80)
    
    # Main conversation loop
    while True:
        # Get user query
        print("\n💬 You can ask me:")
        print("   - Who is working on [topic]?")
        print("   - When were [tickets] created?")
        print("   - Show me tickets about [topic]")
        print("   - Tell me more about [ticket ID]")
        print("   - Or type 'exit' to quit")
        print()
        
        user_query = input("❓ Your question: ").strip()
        
        # Check for exit
        if user_query.lower() in ['exit', 'quit', 'bye', 'no', 'n']:
            print("\n" + "="*80)
            print("👋 Thanks for using Jira Chat Assistant! Goodbye!")
            print("="*80 + "\n")
            break
        
        if not user_query:
            continue
        
        # Process query
        print("\n" + "-"*80)
        print("🔍 Searching Jira...")
        print("-"*80 + "\n")
        
        try:
            inputs = {
                'board_key': board_id,
                'days': days,
                'user_query': user_query
            }
            
            # Run the agent
            crew = JiraReadAgent().crew()
            result = crew.kickoff(inputs=inputs)
            
            # Display response
            print("\n" + "="*80)
            print("🤖 ASSISTANT:")
            print("="*80)
            print(result)
            print("="*80)
            
        except KeyboardInterrupt:
            print("\n\n" + "="*80)
            print("👋 Session interrupted. Goodbye!")
            print("="*80 + "\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Let's try again...\n")

if __name__ == "__main__":
    main()

