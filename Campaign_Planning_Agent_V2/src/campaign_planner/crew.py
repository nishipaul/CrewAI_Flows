import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Any

from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from crewai.llms.base_llm import BaseLLM
from pydantic import BaseModel

from openai import AzureOpenAI


class AzureGPT5Completion(BaseLLM):
    """Simple custom LLM for Azure GPT-5 models with reasoning token tracking."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        azure_endpoint: str | None = None,
        api_version: str = "2025-01-01-preview",
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model=model, provider="azure", **kwargs)
        
        self.api_key = api_key or os.getenv("AZURE_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_API_BASE")
        self.api_version = api_version
        self.reasoning_effort = reasoning_effort
        self.max_completion_tokens = max_completion_tokens
        self.deployment_name = model.replace("azure/", "") if model.startswith("azure/") else model
        
        # Token tracking for reasoning
        self.reasoning_tokens = 0
        self.completion_tokens = 0
        self.prompt_tokens = 0
        
        # Initialize client
        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version,
        )

    def call(self, messages: str | list, **kwargs) -> str:
        """Call Azure GPT-5 API and track reasoning tokens separately."""
        # Format messages
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        else:
            formatted_messages = messages
        
        # Build params
        params = {
            "model": self.deployment_name,
            "messages": formatted_messages,
        }
        if self.reasoning_effort:
            params["reasoning_effort"] = self.reasoning_effort
        if self.max_completion_tokens:
            params["max_completion_tokens"] = self.max_completion_tokens
        
        # Make API call
        response = self.client.chat.completions.create(**params)
        
        # Track token usage with reasoning tokens
        if response.usage:
            self.prompt_tokens += response.usage.prompt_tokens or 0
            self.completion_tokens += response.usage.completion_tokens or 0
            
            # Extract reasoning tokens (GPT-5 specific)
            if hasattr(response.usage, 'completion_tokens_details') and response.usage.completion_tokens_details:
                details = response.usage.completion_tokens_details
                self.reasoning_tokens += getattr(details, 'reasoning_tokens', 0) or 0
            
            # Log token usage
            self._log_token_usage(response.usage)
        
        return response.choices[0].message.content or ""

    def _log_token_usage(self, usage):
        """Log token usage with reasoning tokens shown separately."""
        reasoning = 0
        if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
            reasoning = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0) or 0
        
        output_tokens = (usage.completion_tokens or 0) - reasoning
        
        print(f"\n   Token Usage:")
        print(f"      Input:     {usage.prompt_tokens or 0:,}")
        print(f"      Reasoning: {reasoning:,}")
        print(f"      Output:    {output_tokens:,}")
        print(f"      Total:     {usage.total_tokens or 0:,}")

    def get_total_usage(self) -> dict:
        """Get cumulative token usage."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "output_tokens": self.completion_tokens - self.reasoning_tokens,
        }


def is_gpt5_model(model_name: str) -> bool:
    """Check if the model is a GPT-5 variant."""
    model_lower = model_name.lower()
    return "gpt-5" in model_lower or "gpt5" in model_lower


class CampaignPlan(BaseModel):
    """Pydantic model for campaign plan output from input agent"""
    campaign_occasion: str
    start_date: str
    end_date: str
    target_audience: str
    campaign_goal: str


class CampaignItem(BaseModel):
    """Pydantic model for individual campaign item"""
    campaign_name: str
    platform: str
    campaign_type: str
    summary: str
    start_date: str
    end_date: str


class CampaignOutlineTable(BaseModel):
    """Pydantic model for the final campaign outline table"""
    campaigns: List[CampaignItem]


def save_content_to_file(content: str, occasion: str, platform: str) -> str:
    """Save the generated content to a markdown file in the output folder"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    clean_occasion = "".join(c if c.isalnum() else "_" for c in occasion)[:30]
    clean_platform = "".join(c if c.isalnum() else "_" for c in platform)[:20]
    filename = f"{clean_occasion}_{clean_platform}_{today}.md"
    
    file_path = output_dir / filename
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(file_path)


def create_llm():
    """Create LLM instance.
    
    For GPT-5 models: Uses custom AzureGPT5Completion class with AsyncAzureOpenAI.
    For GPT-4 models: Uses the standard CrewAI LLM class with litellm.
    """
    model_name = os.getenv("MODEL", "azure/gpt-4o-mini")
    model_lower = model_name.lower()
    
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_API_VERSION", "2025-01-01-preview")
    
    # Check if this is a GPT-5 model
    if is_gpt5_model(model_name):
        # Use custom AzureGPT5Completion class with AsyncAzureOpenAI for GPT-5 models
        logging.info(f"Using custom AzureGPT5Completion for model: {model_name}")
        return AzureGPT5Completion(
            model=model_name,
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            temperature=0.7,
            reasoning_effort="medium",  # GPT-5 models support reasoning_effort
        )
    else:
        # Use standard CrewAI LLM for GPT-4 and other models
        config = {
            "model": model_name,
            "api_key": api_key,
            "endpoint": azure_endpoint,
            "api_version": api_version,
            "temperature": 0.7,
        }
        if "gpt-4" in model_lower or "gpt4" in model_lower:
            config["reasoning_effort"] = "medium"
        return LLM(**config)


# Create LLM at module level
_azure_llm = None


def get_llm():
    global _azure_llm
    if _azure_llm is None:
        _azure_llm = create_llm()
    return _azure_llm


@CrewBase
class CampaignPlanner():
    """CampaignPlanner crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        self.llm = get_llm()

    # ============ AGENTS ============
    
    @agent
    def campaign_input_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['campaign_input_agent'],
            llm=self.llm,
            verbose=True,
            max_iter=10,
            allow_delegation=False
        )

    @agent
    def campaign_outline_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['campaign_outline_agent'],
            llm=self.llm,
            verbose=True,
            max_iter=5,
            allow_delegation=False
        )

    @agent
    def plan_generation_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['plan_generation_agent'],
            llm=self.llm,
            verbose=True,
            max_iter=15,
            allow_delegation=False
        )

    # ============ TASKS ============
    
    @task
    def extract_campaign_details_task(self) -> Task:
        """Agent 1: Collect campaign details from user.
        
        The agent will keep asking the user for missing details until ALL 5 required 
        fields are explicitly provided. NO hallucination or inference allowed.
        
        Output: CampaignPlan Pydantic model (passed to Agent 2)
        """
        return Task(
            config=self.tasks_config['extract_campaign_details_task'],
            output_pydantic=CampaignPlan,
            human_input=True  # Enables the agent to keep asking user for missing details
        )

    @task
    def generate_campaign_outline_task(self) -> Task:
        """Agent 2: Generate campaign outline for multiple platforms.
        
        Input: CampaignPlan from Agent 1 (all details already collected)
        """
        return Task(
            config=self.tasks_config['generate_campaign_outline_task'],
            human_input=False,  # No human input needed - Agent 1 already collected all details
            context=[self.extract_campaign_details_task()]
        )

    @task
    def finalize_campaign_table_task(self) -> Task:
        """Agent 2: Create structured campaign table.
        
        Output: CampaignOutlineTable Pydantic model (passed to Agent 3)
        """
        return Task(
            config=self.tasks_config['finalize_campaign_table_task'],
            output_pydantic=CampaignOutlineTable,
            context=[self.generate_campaign_outline_task(), self.extract_campaign_details_task()]
        )

    @task
    def generate_platform_content_task(self) -> Task:
        """Agent 3: Generate platform-specific content.
        
        Input: CampaignOutlineTable from Agent 2
        """
        return Task(
            config=self.tasks_config['generate_platform_content_task'],
            human_input=False,
            context=[self.finalize_campaign_table_task(), self.extract_campaign_details_task()]
        )

    # ============ CREWS ============
    
    def phase1_crew(self) -> Crew:
        """Phase 1: Agent 1 (extraction) and Agent 2 (outline) - runs first.
        
        Flow:
        1. Agent 1 extracts campaign details from paragraph → CampaignPlan (Pydantic)
        2. Agent 2 generates outline based on CampaignPlan
        3. Agent 2 creates campaign table → CampaignOutlineTable (Pydantic)
        
        Both Pydantic outputs are displayed for handover visibility.
        """
        return Crew(
            agents=[self.campaign_input_agent(), self.campaign_outline_agent()],
            tasks=[
                self.extract_campaign_details_task(),
                self.generate_campaign_outline_task(),
                self.finalize_campaign_table_task()
            ],
            process=Process.sequential,
            verbose=True
        )
    
    def phase2_crew(self, phase1_context: str) -> Crew:
        """Phase 2: Agent 3 (content generation) - runs after platform selection.
        
        Input: CampaignOutlineTable from Phase 1
        Output: Ready-to-use platform content
        """
        content_task = Task(
            config=self.tasks_config['generate_platform_content_task'],
            human_input=False
        )
        
        return Crew(
            agents=[self.plan_generation_agent()],
            tasks=[content_task],
            process=Process.sequential,
            verbose=True
        )

    @crew
    def crew(self) -> Crew:
        """Full crew - kept for backwards compatibility"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )
