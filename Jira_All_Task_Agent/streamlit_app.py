import streamlit as st
import os
from dotenv import load_dotenv
from jira_read_agent.src.jira_read_agent.crew import JiraReadAgent

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Jira Ticket Search & Analysis",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stTextInput > label {
        font-weight: bold;
        color: #333;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
    }
    .agent-message {
        background-color: #f5f5f5;
        border-left: 4px solid #4caf50;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.jira_agent = None  # Store the JiraReadAgent instance
    st.session_state.board_id = "356"
    st.session_state.days = "30"
    st.session_state.conversation_history = []
    st.session_state.pending_query = None
    st.session_state.ticket_data = None  # Store ticket data for follow-up questions
    st.session_state.tickets_fetched = False  # Track if tickets have been fetched
    st.session_state.creation_mode = False  # Track if in ticket creation mode
    st.session_state.creation_crew = None  # Store the creation crew instance
    st.session_state.update_mode = False  # Track if in ticket update mode
    st.session_state.update_crew = None  # Store the update crew instance
    st.session_state.last_agent_response = None  # Store last agent response for Slack sending

# Header
st.markdown('<div class="main-header">🎯 Jira Ticket Search & Analysis Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Search tickets and ask follow-up questions in a conversational way</div>', unsafe_allow_html=True)

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Check environment variables
    st.subheader("Environment Status")
    jira_domain = os.getenv("JIRA_DOMAIN", "Not Set")
    jira_email = os.getenv("JIRA_EMAIL", "Not Set")
    jira_token = "✅ Set" if os.getenv("JIRA_API_TKN") else "❌ Not Set"
    azure_key = "✅ Set" if os.getenv("AZURE_OPENAI_API_KEY") else "❌ Not Set"
    
    st.text(f"JIRA Domain: {jira_domain}")
    st.text(f"JIRA Email: {jira_email}")
    st.text(f"JIRA Token: {jira_token}")
    st.text(f"Azure Key: {azure_key}")
    
    st.divider()
    
    # Search parameters
    st.subheader("Search Parameters")
    board_id = st.text_input(
        "Board ID",
        value=st.session_state.board_id,
        help="Enter the Jira board ID (numeric)"
    )
    
    days = st.text_input(
        "Days to Look Back",
        value=st.session_state.days,
        help="Number of days to search back"
    )
    
    # Initialize button
    if st.button("🚀 Initialize Agent", type="primary", use_container_width=True):
        with st.spinner("Initializing agent..."):
            try:
                st.session_state.jira_agent = JiraReadAgent()
                st.session_state.board_id = board_id
                st.session_state.days = days
                st.session_state.initialized = True
                st.session_state.tickets_fetched = False  # Reset on re-initialization
                st.success("✅ Agent initialized successfully!")
            except Exception as e:
                st.error(f"❌ Error initializing agent: {e}")
    
    # Clear conversation button
    if st.session_state.initialized:
        st.divider()
        if st.button("🗑️ Clear Conversation", use_container_width=True):
            st.session_state.conversation_history = []
            st.session_state.ticket_data = None
            st.session_state.pending_query = None
            st.session_state.tickets_fetched = False  # Allow re-fetching tickets
            st.session_state.creation_mode = False  # Exit creation mode
            st.session_state.creation_crew = None  # Clear creation crew
            st.rerun()
    
    st.divider()
    
    # Debug section (optional - can be removed in production)
    with st.expander("🔍 Debug Info"):
        st.text(f"Initialized: {st.session_state.initialized}")
        st.text(f"Board ID: {st.session_state.board_id}")
        st.text(f"Days: {st.session_state.days}")
        st.text(f"Tickets Fetched: {st.session_state.tickets_fetched}")
        st.text(f"Conversation Length: {len(st.session_state.conversation_history)}")
        st.text(f"Has Ticket Data: {st.session_state.ticket_data is not None}")
        st.text(f"Creation Mode: {st.session_state.creation_mode}")
    
    # Show creation or update mode indicator
    if st.session_state.creation_mode:
        st.info("🎫 CREATION MODE ACTIVE - Provide all ticket details in the requested format.")
    elif st.session_state.update_mode:
        st.info("🔄 UPDATE MODE ACTIVE - Provide ticket ID and update details as requested.")
    
    st.divider()
    
    # Help section
    with st.expander("💡 Example Questions"):
        st.markdown("""
        Create New Ticket:
        - "Create a new jira ticket"
        - "I want to create a ticket"
        - "Make a new jira"
        
        Initial Search:
        - "content safety"
        - "bug fixes"
        - "authentication issues"
        
        Bandwidth Analysis:
        - "Show me the bandwidth for all assignees"
        - "What's the team workload?"
        - "List all assignees with their hours"
        - "Who has capacity?"
        
        Follow-up Questions:
        - "Who is working on these?"
        - "Since when is she working on this?"
        - "What's the status?"
        - "When were these created?"
        - "Tell me about ticket DS-1234"
        - "What's the priority?"
        - "Show me Alice's tasks" (after bandwidth report)
        """)

# Main chat interface
if not st.session_state.initialized:
    st.info("👈 Please configure the search parameters and click Initialize Agent to start.")
else:
    # Display conversation history
    for message in st.session_state.conversation_history:
        if message["role"] == "user":
            st.markdown(f"""
            <div class="chat-message user-message">
                <strong>🧑 You:</strong><br>
                {message["content"]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="chat-message agent-message">
                <strong>🤖 Agent:</strong><br>
                {message["content"]}
            </div>
            """, unsafe_allow_html=True)
    
    # Check if there's a pending query from quick actions
    if st.session_state.pending_query:
        query_to_process = st.session_state.pending_query
        st.session_state.pending_query = None
    else:
        query_to_process = None
    
    # Chat input
    st.divider()
    
    # Use columns for better layout
    col1, col2 = st.columns([6, 1])
    
    with col1:
        user_query = st.text_input(
            "Your Question:",
            key="user_input",
            placeholder="Ask about Jira tickets...",
            label_visibility="collapsed"
        )
    
    with col2:
        send_button = st.button("Send 📤", type="primary", use_container_width=True)
    
    # Quick action buttons
    st.markdown("Quick Actions:")
    col_qa1, col_qa2, col_qa3 = st.columns(3)
    
    with col_qa1:
        if st.button("➕ Create Ticket", use_container_width=True):
            st.session_state.pending_query = "I want to create a new jira ticket"
            st.rerun()
    
    with col_qa2:
        if st.button("📊 Team Bandwidth", use_container_width=True):
            st.session_state.pending_query = "Show me the bandwidth for all assignees"
            st.rerun()
    
    with col_qa3:
        if st.button("🔍 Content Safety", use_container_width=True):
            st.session_state.pending_query = "who is working on content safety"
            st.rerun()
    
    # Determine which query to process
    if send_button and user_query:
        query_to_process = user_query
    
    # Process query (either from input or quick action)
    if query_to_process:
        # Add user message to history
        st.session_state.conversation_history.append({
            "role": "user",
            "content": query_to_process
        })
        
        # Convert query to lowercase for checking
        query_lower = query_to_process.lower()
        
        # Check if user wants to send previous message to Slack
        is_send_previous_to_slack = any(phrase in query_lower for phrase in [
            'send this message', 'send this to slack', 'send that to slack',
            'send the above', 'send previous message', 'post this to slack',
            'share this on slack', 'send it to slack'
        ])
        
        # Prepare inputs
        inputs = {
            'board_key': st.session_state.board_id,
            'days': st.session_state.days,
            'user_query': query_to_process
        }
        
        # If user wants to send previous message, append it to the query
        if is_send_previous_to_slack and st.session_state.last_agent_response:
            inputs['user_query'] = f"Send this message to slack:\n\n{st.session_state.last_agent_response}"
            # Update the displayed query to show what's being sent
            st.session_state.conversation_history[-1]["content"] = f"{query_to_process}\n\n[Sending previous response to Slack]"
        
        # Show processing message
        with st.spinner("🤖 Agent is thinking..."):
            try:
                # Check if we're in creation or update mode
                query_lower = query_to_process.lower()
                
                # Check for update trigger
                is_update_trigger = any(keyword in query_lower for keyword in [
                    'update jira', 'update ticket', 'update a jira', 'update a ticket',
                    'modify jira', 'modify ticket', 'edit jira', 'edit ticket',
                    'update ds-', 'modify ds-', 'change ds-', 'i want to update'
                ])
                
                # Check for creation trigger
                is_creation_trigger = any(keyword in query_lower for keyword in [
                    'create jira', 'create ticket', 'create new jira', 'create new ticket',
                    'new jira', 'new ticket', 'make a jira', 'make a ticket',
                    'add jira', 'add ticket', 'i want to create', 'create a jira'
                ])
                
                # Route based on mode
                if is_update_trigger:
                    st.session_state.update_mode = True
                    st.session_state.creation_mode = False  # Exit creation mode if active
                    crew = st.session_state.jira_agent.crew_for_query(
                        query_to_process, 
                        st.session_state.board_id, 
                        st.session_state.days
                    )
                    st.session_state.update_crew = crew
                elif st.session_state.update_mode and st.session_state.update_crew:
                    # Stay in update mode - reuse the same crew
                    crew = st.session_state.update_crew
                elif is_creation_trigger:
                    st.session_state.creation_mode = True
                    st.session_state.update_mode = False  # Exit update mode if active
                    crew = st.session_state.jira_agent.crew_for_query(
                        query_to_process, 
                        st.session_state.board_id, 
                        st.session_state.days
                    )
                    st.session_state.creation_crew = crew
                elif st.session_state.creation_mode and st.session_state.creation_crew:
                    # Stay in creation mode - reuse the same crew
                    crew = st.session_state.creation_crew
                else:
                    # Normal routing
                    crew = st.session_state.jira_agent.crew_for_query(
                        query_to_process, 
                        st.session_state.board_id, 
                        st.session_state.days
                    )
                
                # Run the crew
                result = crew.kickoff(inputs=inputs)
                
                # Mark tickets as fetched after first query
                if not st.session_state.tickets_fetched:
                    st.session_state.tickets_fetched = True
                
                # Extract the final output ONLY (no thought process)
                if hasattr(result, 'raw'):
                    result_text = result.raw
                elif hasattr(result, 'output'):
                    result_text = result.output
                else:
                    result_text = str(result)
                
                # Remove thought process and internal prompts
                # Look for "Final Output:" or similar markers
                if "Final Output:" in result_text:
                    result_text = result_text.split("Final Output:")[-1].strip()
                elif "Final Answer:" in result_text:
                    result_text = result_text.split("Final Answer:")[-1].strip()
                
                # Remove any "Thought:" sections
                if "Thought:" in result_text:
                    lines = result_text.split('\n')
                    filtered_lines = [line for line in lines if not line.strip().startswith("Thought:")]
                    result_text = '\n'.join(filtered_lines).strip()
                
                # Remove "Action:" and "Action Input:" sections
                if "Action:" in result_text or "Action Input:" in result_text:
                    lines = result_text.split('\n')
                    filtered_lines = []
                    skip_next = False
                    for line in lines:
                        if line.strip().startswith("Action:") or line.strip().startswith("Action Input:"):
                            skip_next = True
                            continue
                        if skip_next and line.strip() == "":
                            skip_next = False
                            continue
                        if not skip_next:
                            filtered_lines.append(line)
                    result_text = '\n'.join(filtered_lines).strip()
                
                # Check if ticket was created or updated (exit modes)
                if st.session_state.creation_mode:
                    if "✅ Ticket created successfully" in result_text or "Ticket Details:" in result_text:
                        st.session_state.creation_mode = False
                        st.session_state.creation_crew = None
                
                if st.session_state.update_mode:
                    if "✅ Ticket" in result_text and "updated successfully" in result_text:
                        st.session_state.update_mode = False
                        st.session_state.update_crew = None
                
                # Store the result for context
                st.session_state.ticket_data = result_text
                
                # Store last agent response for potential Slack sending
                st.session_state.last_agent_response = result_text
                
                # Add agent response to history
                st.session_state.conversation_history.append({
                    "role": "agent",
                    "content": result_text
                })
                
                # Rerun to update the display
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state.conversation_history.append({
                    "role": "agent",
                    "content": f"Sorry, I encountered an error: {e}"
                })
    
    # Quick action buttons
    if len(st.session_state.conversation_history) > 0:
        st.divider()
        st.markdown("Quick Actions:")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("📊 Team Bandwidth"):
                st.session_state.pending_query = "Show me the bandwidth for all assignees"
                st.rerun()
        
        with col2:
            if st.button("👥 Who's working?"):
                st.session_state.pending_query = "Who is working on these tickets?"
                st.rerun()
        
        with col3:
            if st.button("📅 When created?"):
                st.session_state.pending_query = "When were these tickets created?"
                st.rerun()
        
        with col4:
            if st.button("🔄 Status?"):
                st.session_state.pending_query = "What's the status of these tickets?"
                st.rerun()
        
        with col5:
            if st.button("⚡ Priority?"):
                st.session_state.pending_query = "What's the priority of these tickets?"
                st.rerun()

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    Powered by CrewAI & Azure OpenAI | Custom Jira Integration
</div>
""", unsafe_allow_html=True)

