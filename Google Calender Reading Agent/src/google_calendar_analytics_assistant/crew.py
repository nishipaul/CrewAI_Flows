import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from google_calendar_analytics_assistant.tools.google_calendar_oauth_tool import GoogleCalendarOAuthTool




@CrewBase
class GoogleCalendarAnalyticsAssistantCrew:
    """GoogleCalendarAnalyticsAssistant crew"""

    
    @agent
    def calendar_data_analyst(self) -> Agent:
        
        return Agent(
            config=self.agents_config["calendar_data_analyst"],
            
            
            tools=[				GoogleCalendarOAuthTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    
    @agent
    def calendar_report_generator(self) -> Agent:
        
        return Agent(
            config=self.agents_config["calendar_report_generator"],
            
            
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                temperature=0.7,
            ),
            
        )
    

    
    @task
    def fetch_calendar_events(self) -> Task:
        return Task(
            config=self.tasks_config["fetch_calendar_events"],
            markdown=False,
            
            
        )
    
    @task
    def generate_calendar_analysis_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_calendar_analysis_report"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the GoogleCalendarAnalyticsAssistant crew"""
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
