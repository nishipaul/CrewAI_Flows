from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.llm import BaseLLM
from typing import List, Optional, Union, Dict, Any
import requests
import os

from dotenv import load_dotenv
load_dotenv()

from complete_jira_flow.tools.custom_tool import (
    FetchJiraTicketsTool,
    CalculateWorkloadTool
)



class CustomLLM(BaseLLM):
    """Custom LLM class that uses the internal chat completions API endpoint."""
    def __init__(self, model: str, Authorization: str, endpoint: str, smtip_tid: str, smtip_feature: str, temperature: Optional[float] = None):

        # IMPORTANT: Call super().__init__() with required parameters
        super().__init__(model=model, temperature=temperature)
        self.Authorization = Authorization
        self.endpoint = endpoint
        self.smtip_tid = smtip_tid
        self.smtip_feature = smtip_feature


    def call(self, messages: Union[str, List[Dict[str, str]]], tools: Optional[List[dict]] = None, callbacks: Optional[List[Any]] = None,
             available_functions: Optional[Dict[str, Any]] = None, **kwargs  # Accept any additional keyword arguments (e.g., from_task)
             ) -> Union[str, Any]:
        """Call the LLM with the given messages."""
        # Convert string to message format if needed
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        # Prepare request
        payload = {
            "model": self.model,
            "messages": messages,
            "api_key": "DDCeMgyCu9L8m7ol5UTfYilRDnUVRmW6Rory9afiaWWOUvIeO3fZJQQJ99BIACHYHv6XJ3w3AAABACOGvD0E",
            "api_base": "https://us-east-2-ai-platform.openai.azure.com/",
            "api_version": "2025-03-01-preview",
            "max_tokens": 100,
        }
        # Add temperature if set
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        # Add tools if provided and supported
        if tools and self.supports_function_calling():
            payload["tools"] = tools


        # Prepare headers (matching test_chat_completions.py)
        headers = {
            "Authorization": f"Bearer {self.Authorization}",
            "Content-Type": "application/json",
            "x-smtip-cid": "langfuse-test-1111",
        }
        # Add custom headers if provided
        if self.smtip_tid:
            headers["x-smtip-tid"] = self.smtip_tid
        if self.smtip_feature:
            headers["x-smtip-feature"] = self.smtip_feature
       

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                verify=False,  # Equivalent to curl -k
                timeout=360
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as e:
            # Print more details about the error
            print(f"DEBUG: HTTP Error - Status Code: {response.status_code}")
            print(f"DEBUG: Response Headers: {dict(response.headers)}")
            print(f"DEBUG: Response Body: {response.text[:500] if response.text else 'No response body'}")
            print(f"DEBUG: Request Headers: {headers}")
            print(f"DEBUG: Request Payload: {payload}")
            raise
    def supports_function_calling(self) -> bool:
        """Override if your LLM supports function calling."""
        return True  # Change to False if your LLM doesn't support tools
    def get_context_window_size(self) -> int:
        """Return the context window size of your LLM."""
        return 8192  # Adjust based on your model's actual context window


# Initialize CustomLLM instance
custom_llm = CustomLLM(
    model="azure/gpt-4o-mini",
    Authorization=os.getenv("CUSTOM_LLM_AUTH_TOKEN", ""),
    endpoint=os.getenv("CUSTOM_LLM_ENDPOINT", ""),
    smtip_tid=os.getenv("CUSTOM_LLM_SMTIP_TID", ""),
    smtip_feature=os.getenv("CUSTOM_LLM_SMTIP_FEATURE", ""),
    temperature=0.7
)


@CrewBase
class JiraForresterAgent():
    """JiraForresterAgent crew for Jira workload management"""

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
            api_version=api_version,
            max_tokens=100
        )

    @agent
    def query_parser_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['Query_Parser_Prompt'],
            tools=[],
            verbose=True,
            max_iter=2,
            llm=self.llm
            )

    @agent
    def ticket_fetcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['Ticket_Fetcher_Prompt'],
            tools=[FetchJiraTicketsTool()],
            verbose=True,
            max_iter=2,
            llm=self.llm
        )

    @agent
    def workload_analyzer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['Workload_Analyzer_Prompt'],
            tools=[CalculateWorkloadTool()],
            verbose=True,
            max_iter=2,
            llm=self.llm
        )

    @agent
    def report_publisher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['Report_Publisher_Prompt'],
            tools=[],
            verbose=True,
            max_iter=2,
            llm=self.llm
        )

    @task
    def parse_query_task(self) -> Task:
        return Task(
            config=self.tasks_config['parse_query_task']
        )

    @task
    def fetch_tickets_task(self) -> Task:
        return Task(
            config=self.tasks_config['fetch_tickets_task']
        )

    @task
    def analyze_workload_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_workload_task']
        )

    @task
    def publish_results_task(self) -> Task:
        return Task(
            config=self.tasks_config['publish_results_task']
        )

    @crew
    def crew(self) -> Crew:
        """Creates the JiraForresterAgent crew with sequential processing"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
