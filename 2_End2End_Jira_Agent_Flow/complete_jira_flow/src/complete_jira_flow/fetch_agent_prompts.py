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

# Fields we ALLOW to be updated from Langfuse
MERGE_KEYS = {"role", "goal", "backstory"}

# Path to agents.yaml in config directory
CONFIG_DIR = Path(__file__).parent / "config"
AGENTS_FILE = CONFIG_DIR / "agents.yaml"


def fetch_prompt_from_langfuse(agent_name: str) -> str:
    """Fetch prompt from Langfuse for a given agent name."""
    langfuse_prompt = langfuse_client.get_prompt(
        name=agent_name,
        label="jira_agent"
    )
    return langfuse_prompt.prompt


def parse_agent_prompt(prompt_text: str) -> dict:
    """Parse agent prompt text separated by <EOD> into a dictionary."""
    parts = {}
    for line in prompt_text.split("<EOD>"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            parts[key.strip()] = value.strip()
    return parts


def load_existing_agents() -> dict:
    """Return empty dict to start fresh with agents from Langfuse."""
    return {}


def format_yaml_value(value: str, indent: str = "    ") -> str:
    """Format a value for YAML with proper indentation on all lines."""
    lines = value.split('\n')
    # Indent every line with 4 spaces
    formatted_lines = []
    for line in lines:
        if line.strip():
            formatted_lines.append(indent + line.strip())
        else:
            formatted_lines.append('')
    return '\n'.join(formatted_lines)


def save_agents_yaml(agents_yaml: dict) -> None:
    """Save agents dictionary to agents.yaml file with clean formatting."""
    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Define the order of fields
    field_order = ["role", "goal", "backstory"]
    
    # Build YAML content manually
    yaml_blocks = []
    
    for agent_name, agent_config in agents_yaml.items():
        lines = [f"{agent_name}:"]
        
        # Add fields in order: role, goal, backstory
        for field in field_order:
            if field in agent_config:
                value = agent_config[field]
                lines.append(f"  {field}: >")
                # Indent the content with 4 spaces
                formatted_value = format_yaml_value(value, "    ")
                lines.append(formatted_value)
        
        yaml_blocks.append('\n'.join(lines))
    
    # Join blocks with two blank lines
    yaml_content = "\n\n\n".join(yaml_blocks) + "\n"
    
    with open(AGENTS_FILE, "w") as f:
        f.write(yaml_content)


def process_agent(agent_name: str, agents_yaml: dict) -> dict:
    """Fetch, parse, and merge agent prompt into agents_yaml."""
    print(f"Fetching prompt for agent: {agent_name}")
    
    # Fetch prompt from Langfuse
    prompt_text = fetch_prompt_from_langfuse(agent_name)
    
    # Parse the prompt
    agent_fields = parse_agent_prompt(prompt_text)
    
    # Create agent config with only role, goal, backstory
    agent_config = {}
    for key in MERGE_KEYS:
        if key in agent_fields:
            agent_config[key] = agent_fields[key]
    
    # Update the agents_yaml dict
    agents_yaml[agent_name] = agent_config
    
    print(f"Successfully processed agent: {agent_name}")
    return agents_yaml


def get_agent_names_from_user() -> list:
    """Get agent names from user input."""
    agent_names = ["Query_Parser_Prompt", "Ticket_Fetcher_Prompt", "Workload_Analyzer_Prompt", "Report_Publisher_Prompt"]
    
    if not agent_names:
        print("No agent names provided. Exiting.")
        return []
    
    return agent_names


def main():
    """Main function to fetch agent prompts and create agents.yaml."""
    # Get agent names from user
    agent_names = get_agent_names_from_user()
    
    if not agent_names:
        return
    
    print(f"\nProcessing {len(agent_names)} agent(s): {', '.join(agent_names)}\n")
    
    # Load existing agents.yaml
    agents_yaml = load_existing_agents()
    
    # Process each agent
    for agent_name in agent_names:
        try:
            agents_yaml = process_agent(agent_name, agents_yaml)
        except Exception as e:
            print(f"Error processing agent '{agent_name}': {e}")
            continue
    
    # Save to agents.yaml
    save_agents_yaml(agents_yaml)
    
    print(f"\nAgents saved to: {AGENTS_FILE}")


if __name__ == "__main__":
    main()
