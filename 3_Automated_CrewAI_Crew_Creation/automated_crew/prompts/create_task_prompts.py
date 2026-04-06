import os
from langfuse import Langfuse
import yaml
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Initialize Langfuse client
langfuse_client = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)



technical_document_summary_task_prompt = """
description: Summarize the given technical document content.
    Focus on extracting the document’s purpose, core technical concepts,
    system architecture, workflows, APIs, configurations, and dependencies.
    Highlight assumptions, limitations, and prerequisites where applicable <EOD>

expected_output: Clear, structured technical summary in plain text <EOD>

agent: technical_summary_agent <EOD>
"""




medical_document_summary_task_prompt = """
description: Summarize the provided medical document content.
    Identify the document type and extract key clinical findings,
    diagnoses, treatments, procedures, results, and conclusions.
    Highlight risks, contraindications, and limitations if mentioned <EOD>

expected_output: Accurate, factual, and neutral medical summary in plain text <EOD>

agent: medical_summary_agent <EOD>
"""




product_document_summary_task_prompt = """
description: Summarize the given product document content.
    Identify the product, target users, and problem statement.
    Extract key features, differentiators, benefits, and use cases.
    Note constraints, dependencies, or requirements if present <EOD>

expected_output: Concise, product-focused summary in plain text <EOD>

agent: product_summary_agent <EOD>
"""




legal_document_summary_task_prompt = """
description: Summarize the provided legal document content.
    Identify document type, involved parties, and key clauses.
    Extract obligations, rights, deadlines, penalties, and termination conditions.
    Highlight risks and liabilities without interpretation <EOD>

expected_output: Accurate and neutral legal summary in plain text <EOD>

agent: legal_summary_agent <EOD>
"""




financial_document_summary_task_prompt = """
description: Summarize the given financial document content.
    Identify the document type and extract key financial metrics,
    trends, performance indicators, risks, and assumptions.
    Highlight conclusions and outlook where applicable <EOD>

expected_output: Structured and objective financial summary in plain text <EOD>

agent: financial_summary_agent <EOD>
"""




hr_document_summary_task_prompt = """
description: Summarize the provided HR document content.
    Identify document type and extract key policies, processes,
    responsibilities, eligibility criteria, and compliance requirements.
    Highlight changes, exceptions, and required actions <EOD>

expected_output: Clear and employee-friendly HR summary in plain text <EOD>

agent: hr_summary_agent <EOD>
"""



langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=technical_document_summary_task_prompt,
    labels=["technical_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)

langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=medical_document_summary_task_prompt,
    labels=["medical_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)

langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=product_document_summary_task_prompt,
    labels=["product_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)

langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=legal_document_summary_task_prompt,
    labels=["legal_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)

langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=financial_document_summary_task_prompt,
    labels=["financial_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)

langfuse_client.create_prompt(
    name="Summary_Prompt_Task_CrewAI",
    type="text",
    prompt=hr_document_summary_task_prompt,
    labels=["hr_summary_task"],
    tags=["summary_prompts", "crewai", "tasks"],
)