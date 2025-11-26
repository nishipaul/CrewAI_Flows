from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
import os
from datetime import datetime, timedelta
from .tools.custom_jira_tool import CustomJiraTool
from .tools.cached_ticket_tools import (
    GetAllAssignees,
    GetAssigneeTickets,
    LoadCachedTickets,
    CheckCacheExists
)
from .tools.jira_create_tool import CreateJiraTicket, ValidateBoard
from .tools.jira_update_tool import GetJiraTicket, UpdateJiraTicket
from .tools.slack_tool import SendSlackMessage

@CrewBase
class JiraReadAgent():
    """JiraReadAgent crew for reading and filtering Jira tickets"""

    agents: List[BaseAgent]
    tasks: List[Task]

    def __init__(self):
        # Initialize Azure OpenAI LLM using credentials from .env
        model = os.getenv("MODEL", "azure/gpt-4o-mini")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
        
        self.llm = LLM(
            model=model,
            api_key=api_key,
            base_url=endpoint,
            api_version=api_version
        )

    @agent
    def jira_search_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['jira_search_agent'],
            tools=[CustomJiraTool()],  # Use custom Jira tool
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to analyst
        )
    
    @agent
    def ticket_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['ticket_analyst_agent'],
            llm=self.llm,
            verbose=False,
            allow_delegation=False
        )
    
    @agent
    def bandwidth_analyzer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['bandwidth_analyzer_agent'],
            tools=[LoadCachedTickets(), GetAllAssignees(), GetAssigneeTickets()],  # Tools to access cached data
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to ticket_analyst for specific assignee queries
        )
    
    @agent
    def master_orchestrator_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['master_orchestrator_agent'],
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Always delegates to specialized agents
        )
    
    @agent
    def error_handler_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['error_handler_agent'],
            tools=[GetAllAssignees(), GetAssigneeTickets()],  # Can validate and get assignee data
            llm=self.llm,
            verbose=False,
            allow_delegation=False
        )
    
    @agent
    def task_allocation_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['task_allocation_agent'],
            tools=[
                LoadCachedTickets(), 
                GetAllAssignees(), 
                GetAssigneeTickets(),
                GetJiraTicket(),
                UpdateJiraTicket()
            ],  # Full access including update capability
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to update agent for ticket reassignment
        )
    
    @agent
    def jira_creation_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['jira_creation_agent'],
            tools=[CreateJiraTicket(), ValidateBoard(), GetAllAssignees()],  # Tools for ticket creation and validation
            llm=self.llm,
            verbose=False,
            allow_delegation=False  # Should NOT delegate - handles creation independently
        )
    
    @agent
    def jira_update_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['jira_update_agent'],
            tools=[GetJiraTicket(), UpdateJiraTicket(), GetAllAssignees()],  # Tools for ticket update and validation
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to creation agent if ticket not found
        )
    
    @agent
    def communication_assistant_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['communication_assistant_agent'],
            tools=[LoadCachedTickets(), GetAllAssignees(), GetAssigneeTickets()],  # Tools to get workload context
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to bandwidth analyzer and search agents for context
        )
    
    @agent
    def skill_matching_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['skill_matching_agent'],
            tools=[LoadCachedTickets(), GetAllAssignees(), GetAssigneeTickets()],  # Tools to analyze ticket history
            llm=self.llm,
            verbose=False,
            allow_delegation=True  # Can delegate to allocation and update agents
        )
    
    @agent
    def slack_message_sender_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['slack_message_sender_agent'],
            tools=[SendSlackMessage()],  # Use custom Slack tool with credentials from .env
            llm=self.llm,
            verbose=False,
            allow_delegation=False  # Standalone agent for sending messages
        )

    @task
    def search_tickets_task(self) -> Task:
        return Task(
            config=self.tasks_config['search_tickets_task'],
        )
    
    @task
    def analyze_tickets_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_tickets_task'],
        )
    
    @task
    def analyze_bandwidth_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_bandwidth_task'],
        )
    
    @task
    def allocate_task_task(self) -> Task:
        return Task(
            config=self.tasks_config['allocate_task_task'],
        )
    
    @task
    def create_jira_ticket_task(self) -> Task:
        return Task(
            config=self.tasks_config['create_jira_ticket_task'],
        )
    
    @task
    def update_jira_ticket_task(self) -> Task:
        return Task(
            config=self.tasks_config['update_jira_ticket_task'],
        )
    
    @task
    def draft_communication_task(self) -> Task:
        return Task(
            config=self.tasks_config['draft_communication_task'],
        )
    
    @task
    def analyze_skill_overlap_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_skill_overlap_task'],
        )
    
    @task
    def send_slack_message_task(self) -> Task:
        return Task(
            config=self.tasks_config['send_slack_message_task'],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the JiraReadAgent crew with dynamic task routing"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
    
    def crew_for_query(self, user_query: str, board_id: str, days: str) -> Crew:
        """
        Creates a crew with appropriate tasks based on the user query using Master Orchestrator.
        The master orchestrator analyzes the query and routes to the appropriate agent.
        """
        query_lower = user_query.lower()
        
        # Detect query type for routing
        # 0. Jira Update queries (HIGHEST PRIORITY - NEW)
        update_keywords = [
            'update jira', 'update ticket', 'update a jira', 'update a ticket',
            'modify jira', 'modify ticket', 'modify a jira', 'modify a ticket',
            'change jira', 'change ticket', 'change a jira', 'change a ticket',
            'edit jira', 'edit ticket', 'edit a jira', 'edit a ticket',
            'update ds-', 'modify ds-', 'change ds-', 'edit ds-',
            'i want to update', 'need to update', 'want to modify', 'need to modify'
        ]
        is_update_query = any(keyword in query_lower for keyword in update_keywords)
        
        # 1. Jira Creation queries (HIGH PRIORITY)
        creation_keywords = [
            'create jira', 'create ticket', 'create new jira', 'create new ticket',
            'new jira', 'new ticket', 'make a jira', 'make a ticket',
            'add jira', 'add ticket', 'i want to create', 'create a jira'
        ]
        
        # Exclude if user is asking about assignment/allocation (even if they mention "created")
        is_asking_assignment = any(word in query_lower for word in [
            'whom should i assign', 'who should i assign', 'whom to assign', 'who to assign',
            'based on availability', 'based on bandwidth', 'whom should', 'who should'
        ])
        
        is_creation_query = (
            any(keyword in query_lower for keyword in creation_keywords) and 
            not is_update_query and 
            not is_asking_assignment  # Don't treat as creation if asking for assignment
        )
        
        # 2. Task Allocation queries (HIGH priority)
        allocation_keywords = [
            'whom should i assign', 'who should i assign', 'whom to assign', 'who to assign',
            'who should do', 'who should work on', 'assign to', 'allocate', 
            'who can take', 'recommend assignee', 'suggest assignee',
            'whom should', 'who should handle', 'who can handle',
            'assign ticket from', 'reassign from', 'move ticket from', 'transfer from',
            'assign ticket ds-', 'assign ds-', 'reassign ds-', 'reassign ticket ds-',
            'based on availability', 'based on bandwidth', 'based on workload',
            'who is available', 'who has capacity', 'suggest allocation'
        ]
        allocation_patterns = [
            'is important', 'should be assigned', 'needs to be done',
            'high priority', 'urgent', 'critical', 'whom should',
            'from .* to', 'ticket from .* to', 'ds-\\d+ to',
            'have.*ticket.*whom', 'created.*ticket.*whom', 'have.*task.*who'
        ]
        
        # Check if it's a direct ticket assignment (DS-XXX to Person)
        import re
        has_ticket_id = bool(re.search(r'ds-\d+', query_lower))
        has_assign_keyword = 'assign' in query_lower or 'reassign' in query_lower
        has_to_keyword = ' to ' in query_lower
        is_direct_assignment = has_ticket_id and has_assign_keyword and has_to_keyword
        
        # Check if it's an allocation query
        is_allocation_query = (
            is_direct_assignment or
            any(keyword in query_lower for keyword in allocation_keywords) or 
            any(pattern in query_lower for pattern in allocation_patterns) or
            ('assign' in query_lower and ('whom' in query_lower or 'who' in query_lower)) or
            ('assign' in query_lower and 'from' in query_lower and 'to' in query_lower)
        ) and not is_creation_query  # Don't confuse creation with allocation
        
        # 3. Slack Message queries (HIGHEST priority for explicit Slack sends)
        slack_keywords = [
            'send to slack', 'send slack message', 'message to slack',
            'send message to slack', 'slack send', 'post to slack',
            'send to #', 'message #', 'slack #', 'send on slack',
            'send the above message on slack', 'send the message on slack',
            'send above message to slack', 'send this message on slack',
            'send this to slack', 'send that to slack', 'send it to slack'
        ]
        is_slack_query = any(keyword in query_lower for keyword in slack_keywords)
        
        # 4. Communication/Messaging queries (HIGH priority)
        communication_keywords = [
            'message', 'send message', 'draft message', 'communicate with',
            'talk to', 'reach out to', 'contact', 'email',
            'schedule meeting', 'schedule 1:1', 'set up meeting', 'arrange meeting',
            'check in with', 'follow up with', 'ping', 'notify'
        ]
        communication_patterns = [
            'understand why', 'ask about', 'discuss with', 'sync with',
            'why is', 'why are', 'how come', 'reason for',
            'overloaded', 'too much work', 'overwhelmed', 'too busy'
        ]
        is_communication_query = (
            any(keyword in query_lower for keyword in communication_keywords) or
            any(pattern in query_lower for pattern in communication_patterns)
        ) and not is_creation_query and not is_update_query and not is_slack_query  # Don't confuse with creation/update/slack
        
        # 5. Skill Matching queries (explicit request for skill analysis or task allocation)
        skill_matching_keywords = [
            'skill match', 'similar skills', 'overlapping skills', 'who has similar',
            'who can do', 'who else can', 'skill overlap', 'skill analysis',
            'whom can i allocate', 'who can take', 'reallocate', 'reassign',
            'find someone with', 'who knows', 'skill comparison'
        ]
        is_skill_matching_query = any(keyword in query_lower for keyword in skill_matching_keywords)
        
        # 6. Bandwidth/Workload queries (both general and specific)
        bandwidth_keywords = ['bandwidth', 'workload', 'capacity', 'hours busy', 'hours free', 'team load']
        is_bandwidth_query = any(keyword in query_lower for keyword in bandwidth_keywords) and not is_allocation_query and not is_communication_query and not is_skill_matching_query and not is_slack_query
        
        # 6a. Check if it's a specific assignee bandwidth query
        # Patterns: "bandwidth of Alice", "bandwidth for Bob", "Alice's bandwidth"
        specific_bandwidth_patterns = ['bandwidth of', 'bandwidth for', "'s bandwidth", 'workload of', 'workload for']
        is_specific_bandwidth = is_bandwidth_query and any(pattern in query_lower for pattern in specific_bandwidth_patterns)
        
        # 6b. Check if it's a general bandwidth query
        general_bandwidth_patterns = ['all assignees', 'team bandwidth', 'show bandwidth', 'everyone', 'all', 'my team', 'the team']
        is_general_bandwidth = is_bandwidth_query and (
            any(pattern in query_lower for pattern in general_bandwidth_patterns) or
            not is_specific_bandwidth
        )
        
        # 7. Specific assignee task queries (show me X's tasks, what is X working on)
        assignee_task_keywords = ['show me', 'tasks for', 'what is', 'working on', 'assigned to']
        is_assignee_task_query = any(keyword in query_lower for keyword in assignee_task_keywords) and not is_bandwidth_query and not is_allocation_query and not is_communication_query and not is_slack_query
        
        # 8. Search/content queries (who is working on content safety, find tickets about X)
        search_keywords = ['who is working on', 'find', 'search', 'tickets about', 'related to']
        is_search_query = any(keyword in query_lower for keyword in search_keywords) and not is_allocation_query and not is_communication_query and not is_slack_query
        
        # Route based on query type
        if is_update_query:
            # Route to Jira Update Agent (HIGHEST PRIORITY - NEW)
            # Can delegate to creation agent if ticket not found
            return Crew(
                agents=[self.jira_update_agent(), self.jira_creation_agent()],
                tasks=[self.update_jira_ticket_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_creation_query:
            # Route to Jira Creation Agent ONLY
            # No other agents needed - creation is standalone
            return Crew(
                agents=[self.jira_creation_agent()],
                tasks=[self.create_jira_ticket_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_slack_query:
            # Route to Slack Message Sender Agent (HIGHEST priority for Slack)
            # Standalone agent for sending messages to Slack
            return Crew(
                agents=[self.slack_message_sender_agent()],
                tasks=[self.send_slack_message_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_communication_query:
            # Route to Communication Assistant Agent
            # Can delegate to bandwidth analyzer and search agents for context
            return Crew(
                agents=[self.communication_assistant_agent(), self.bandwidth_analyzer_agent(), self.jira_search_agent()],
                tasks=[self.draft_communication_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_skill_matching_query:
            # Route to Skill Matching Agent (explicit request for skill analysis)
            # Includes allocation and update agents for potential reallocation
            return Crew(
                agents=[
                    self.jira_search_agent(),
                    self.bandwidth_analyzer_agent(),
                    self.skill_matching_agent(),
                    self.task_allocation_agent(),
                    self.jira_update_agent(),
                    self.error_handler_agent()
                ],
                tasks=[
                    self.search_tickets_task(),
                    self.analyze_bandwidth_task(),
                    self.analyze_skill_overlap_task()
                ],
                process=Process.sequential,
                verbose=False
            )
        elif is_allocation_query:
            # Route to Task Allocation Agent
            # Includes bandwidth analyzer for workload check and update agent for reassignment
            return Crew(
                agents=[
                    self.jira_search_agent(), 
                    self.bandwidth_analyzer_agent(),
                    self.task_allocation_agent(), 
                    self.jira_update_agent(),
                    self.jira_creation_agent()
                ],
                tasks=[self.search_tickets_task(), self.allocate_task_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_bandwidth_query:
            # Route to Bandwidth Analyzer ONLY (no automatic skill matching)
            # Both specific and general bandwidth queries just show bandwidth
            return Crew(
                agents=[self.jira_search_agent(), self.bandwidth_analyzer_agent(), self.error_handler_agent()],
                tasks=[self.search_tickets_task(), self.analyze_bandwidth_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_assignee_task_query:
            # Route to Error Handler (validates assignee) then Jira Search
            return Crew(
                agents=[self.error_handler_agent(), self.jira_search_agent(), self.ticket_analyst_agent()],
                tasks=[self.search_tickets_task(), self.analyze_tickets_task()],
                process=Process.sequential,
                verbose=False
            )
        elif is_search_query:
            # Route to Jira Search then Ticket Analyst
            return Crew(
                agents=[self.jira_search_agent(), self.ticket_analyst_agent(), self.error_handler_agent()],
                tasks=[self.search_tickets_task(), self.analyze_tickets_task()],
                process=Process.sequential,
                verbose=False
            )
        else:
            # Default: Route to Ticket Analyst (for questions about already fetched tickets)
            return Crew(
                agents=[self.jira_search_agent(), self.ticket_analyst_agent()],
                tasks=[self.search_tickets_task(), self.analyze_tickets_task()],
                process=Process.sequential,
                verbose=False
            )
