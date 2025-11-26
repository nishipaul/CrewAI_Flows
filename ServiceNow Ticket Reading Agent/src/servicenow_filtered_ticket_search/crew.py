import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from servicenow_filtered_ticket_search.tools.servicenow_connection_tool import ServiceNowConnectionTool
from servicenow_filtered_ticket_search.tools.servicenow_all_tickets_dynamic_days_tool import ServiceNowAllTicketsDynamicDaysTool
from servicenow_filtered_ticket_search.tools.servicenow_data_formatter import ServiceNowDataFormatterTool
from servicenow_filtered_ticket_search.tools.servicenow_filtered_query import ServiceNowFilteredQueryTool




@CrewBase
class ServicenowFilteredTicketSearchCrew:
    """ServicenowFilteredTicketSearch crew"""

    
    @agent
    def servicenow_connection_manager(self) -> Agent:
        
        return Agent(
            config=self.agents_config["servicenow_connection_manager"],
            
            
            tools=[				ServiceNowConnectionTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=5,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.2,
            ),
            
        )
    
    @agent
    def servicenow_all_tickets_analyst(self) -> Agent:
        
        return Agent(
            config=self.agents_config["servicenow_all_tickets_analyst"],
            
            
            tools=[				ServiceNowAllTicketsDynamicDaysTool(),
				ServiceNowDataFormatterTool(),
				ServiceNowFilteredQueryTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=5,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.2,
            ),
            
        )
    

    
    @task
    def test_servicenow_connection(self) -> Task:
        return Task(
            config=self.tasks_config["test_servicenow_connection"],
            markdown=False,
            
            
        )
    
    @task
    def search_filtered_servicenow_tickets(self) -> Task:
        return Task(
            config=self.tasks_config["search_filtered_servicenow_tickets"],
            markdown=False,
            
            
        )
    
    @task
    def servicenow_operation_summary(self) -> Task:
        return Task(
            config=self.tasks_config["servicenow_operation_summary"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the ServicenowFilteredTicketSearch crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )

    def _load_response_format(self, name):
        with open(os.path.join(self.base_directory, "config", f"{name}.json")) as f:
            json_schema = json.loads(f.read())

        return SchemaConverter.build(json_schema)
