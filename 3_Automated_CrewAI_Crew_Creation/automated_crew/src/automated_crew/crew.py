from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List



@CrewBase
class AutomatedCrew():
    """AutomatedCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]


    @agent
    def hr_summary_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['hr_summary_agent'],  # type: ignore[index]
            verbose=True
        )

    @task
    def hr_summary_task(self) -> Task:
        return Task(
            config=self.tasks_config['hr_summary_task'],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the AutomatedCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
