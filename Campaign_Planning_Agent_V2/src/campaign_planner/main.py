#!/usr/bin/env python
import sys
import warnings
import yaml
import os
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from campaign_planner.crew import CampaignPlanner, CampaignOutlineTable, CampaignPlan, save_content_to_file

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# Load environment variables
load_dotenv()


def collect_user_inputs():
    """Collect campaign inputs from user as a single paragraph only.
    
    Agent 1 will extract all required details from the paragraph.
    No parsing or field-by-field input - just one paragraph input.
    """
    print("\n" + "=" * 70)
    print("CAMPAIGN PLANNER - Let's Create Your Campaign!")
    print("=" * 70)
    
    print("\nPlease describe your campaign in a paragraph.")
    print("   Include details like:")
    print("   • What occasion/theme is this campaign for?")
    print("   • When should it start and end? (dates)")
    print("   • Who is your target audience?")
    print("   • What is your campaign goal?")
    
    print("-" * 70)
    paragraph = input("Your campaign description:\n\n").strip()
    print("-" * 70)
    
    if not paragraph:
        print("\n Please provide a campaign description.")
        paragraph = input("Your campaign description:\n\n").strip()
    
    print("\n Got your campaign description! Agent will now extract the details...\n")
    
    return {'user_paragraph': paragraph}



def load_requirements():
    """Load campaign requirements from yaml file"""
    requirements_path = Path(__file__).parent / "requirements" / "campaign_requirements.yaml"
    
    if requirements_path.exists():
        with open(requirements_path, 'r') as f:
            data = yaml.safe_load(f)
            return data.get('requirements', {})
    return {}



def save_final_output(content: str, occasion: str, platform: str) -> str:
    """Save the final content to a markdown file"""
    # Ensure output directory exists
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Create filename
    today = datetime.now().strftime("%Y-%m-%d")
    clean_occasion = "".join(c if c.isalnum() else "_" for c in occasion)[:30]
    clean_platform = "".join(c if c.isalnum() else "_" for c in platform)[:20]
    filename = f"{clean_occasion}_{clean_platform}_{today}.md"
    
    file_path = output_dir / filename
    
    # Write content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return str(file_path)




def ask_platform_selection(available_platforms: list = None):
    """
    Ask user to select a platform for content generation in a user-friendly way.
    Called AFTER Agent 2 completes (after campaign table is generated) and BEFORE Agent 3 starts.
    
    Args:
        available_platforms: List of platforms from Agent 2's campaign table output.
                           If None, uses default list.
    """
    if available_platforms is None or len(available_platforms) == 0:
        available_platforms = [
            "Email",
            "Facebook", 
            "Instagram",
            "LinkedIn",
            "Twitter",
            "WhatsApp",
            "SMS",
            "Slack"
        ]
    
    print("\n" + "=" * 70)
    print("PLATFORM SELECTION FOR CONTENT GENERATION")
    print("=" * 70)
    print("\nBased on your campaign table, choose which platform you'd like")
    print("   detailed content for:\n")
    
    for i, platform in enumerate(available_platforms, 1):
        print(f"   {i}. {platform}")
    
    print("\n" + "-" * 70)
    
    while True:
        user_input = input("\n Enter platform name or number (e.g., '1' or 'Email'): ").strip()
        
        if not user_input:
            print("---- Please select a platform. ----")
            continue
        
        # Check if input is a number
        if user_input.isdigit():
            idx = int(user_input)
            if 1 <= idx <= len(available_platforms):
                selected = available_platforms[idx - 1]
                print(f"\n Great choice! Generating content for {selected}...")
                return selected
            else:
                print(f"Please enter a number between 1 and {len(available_platforms)}.")
                continue
        
        # Check if input matches a platform name (case-insensitive)
        for platform in available_platforms:
            if platform.lower() == user_input.lower():
                print(f"\n Great choice! Generating content for {platform}...")
                return platform
        
        print(f" '{user_input}' is not a valid platform. Please choose from the list above.")





def display_token_usage(result):
    """
    Display token usage statistics at the end for user knowledge.
    Shows thinking (reasoning) tokens and completion tokens separately.
    """
    print("\n" + "=" * 70)
    print("TOKEN USAGE SUMMARY")
    print("=" * 70)
    
    if hasattr(result, 'token_usage') and result.token_usage:
        usage = result.token_usage
        
        prompt_tokens = getattr(usage, 'prompt_tokens', 0) or 0
        completion_tokens = getattr(usage, 'completion_tokens', 0) or 0
        total_tokens = getattr(usage, 'total_tokens', 0) or 0
        cached_tokens = getattr(usage, 'cached_prompt_tokens', 0) or 0
        successful_requests = getattr(usage, 'successful_requests', 0) or 0
        
        print(f"\n  Input Tokens (Prompt):      {prompt_tokens:,}")
        if cached_tokens > 0:
            print(f"  Cached Prompt Tokens:       {cached_tokens:,}")
        print(f"   Output Tokens (Completion): {completion_tokens:,}")
        print(f"   ─────────────────────────────────")
        print(f"   Total Tokens:               {total_tokens:,}")
        print(f"   Successful Requests:        {successful_requests}")
        
        # Note about reasoning tokens
        print(f"\n   Note: For models with reasoning/thinking capabilities, reasoning tokens are included in the completion tokens count.")
    else:
        print("\n  Token usage information not available.")
    
    print("\n" + "=" * 70)





def extract_platforms_from_table(result_text: str) -> list:
    """
    Extract platform names from the campaign table output of Agent 2.
    """
    platforms = []
    
    # Common platform names to look for
    known_platforms = ["Email", "Facebook", "Instagram", "LinkedIn", "Twitter", "WhatsApp", "SMS", "Slack"]
    
    # Try to find platforms mentioned in the result
    for platform in known_platforms:
        if platform.lower() in result_text.lower():
            if platform not in platforms:
                platforms.append(platform)
    
    return platforms if platforms else known_platforms





def display_campaign_table(campaigns):
    """Display campaigns in a nicely formatted table."""
    if not campaigns:
        return
    
    # Define column widths
    col_widths = {
        'name': 20,
        'platform': 12,
        'type': 14,
        'summary': 30,
        'start': 12,
        'end': 12
    }
    
    # Print header
    header = (
        f"| {'Campaign Name':<{col_widths['name']}} | "
        f"{'Platform':<{col_widths['platform']}} | "
        f"{'Type':<{col_widths['type']}} | "
        f"{'Summary':<{col_widths['summary']}} | "
        f"{'Start':<{col_widths['start']}} | "
        f"{'End':<{col_widths['end']}} |"
    )
    separator = "-" * len(header)
    
    print(f"\n{separator}")
    print(header)
    print(separator)
    
    # Print each campaign row
    for campaign in campaigns:
        name = str(getattr(campaign, 'campaign_name', ''))[:col_widths['name']]
        platform = str(getattr(campaign, 'platform', ''))[:col_widths['platform']]
        c_type = str(getattr(campaign, 'campaign_type', ''))[:col_widths['type']]
        summary = str(getattr(campaign, 'summary', ''))[:col_widths['summary']]
        start = str(getattr(campaign, 'start_date', ''))[:col_widths['start']]
        end = str(getattr(campaign, 'end_date', ''))[:col_widths['end']]
        
        row = (
            f"| {name:<{col_widths['name']}} | "
            f"{platform:<{col_widths['platform']}} | "
            f"{c_type:<{col_widths['type']}} | "
            f"{summary:<{col_widths['summary']}} | "
            f"{start:<{col_widths['start']}} | "
            f"{end:<{col_widths['end']}} |"
        )
        print(row)
    
    print(separator)


def display_pydantic_handover(title: str, pydantic_output, agent_from: str, agent_to: str):
    """Display Pydantic model output as JSON for agent handover visibility."""
    print("\n" + "=" * 70)
    print(f"{title}")
    print(f"   From: {agent_from} → To: {agent_to}")
    print("=" * 70)
    
    if pydantic_output:
        if hasattr(pydantic_output, 'model_dump_json'):
            # It's a Pydantic model
            json_str = pydantic_output.model_dump_json(indent=2)
            print(f"\n Pydantic JSON Output:\n{json_str}")
            
            # If it's a campaign table (has 'campaigns'), also show as table
            if hasattr(pydantic_output, 'campaigns') and pydantic_output.campaigns:
                print("\n Table View:")
                display_campaign_table(pydantic_output.campaigns)
                
        elif hasattr(pydantic_output, 'json_dict'):
            # Alternative method
            print(f"\n Pydantic JSON Output:\n{json.dumps(pydantic_output.json_dict, indent=2)}")
        elif isinstance(pydantic_output, dict):
            print(f"\n Pydantic JSON Output:\n{json.dumps(pydantic_output, indent=2)}")
        else:
            print(f"\n Output:\n{pydantic_output}")
    else:
        print("\n No Pydantic output available")
    
    print("=" * 70)






def run():
    """
    Run the crew in two phases:
    1. Phase 1: Agent 1 (input extraction) + Agent 2 (outline) - generates campaign table
       - Agent 1 extracts campaign details from user paragraph → outputs CampaignPlan (Pydantic)
       - Agent 2 creates campaign outline → outputs CampaignOutlineTable (Pydantic)
    2. User selects platform based on the table
    3. Phase 2: Agent 3 (content) - generates content for selected platform
    """
    # Collect user paragraph input only (no parsing - Agent 1 will extract details)
    user_inputs = collect_user_inputs()
    
    # Pass the raw paragraph to Agent 1 for extraction
    inputs = {
        'user_paragraph': user_inputs.get('user_paragraph', ''),
    }

    try:
        planner = CampaignPlanner()
        
        # ============ PHASE 1: Agent 1 + Agent 2 ============
        print("\n" + "=" * 70)
        print("PHASE 1: Extracting Details & Generating Campaign Outline...")
        print("=" * 70 + "\n")
        
        phase1_result = planner.phase1_crew().kickoff(inputs=inputs)
        
        # Get the campaign table output
        phase1_output = str(phase1_result.raw) if hasattr(phase1_result, 'raw') else str(phase1_result)
        
        # Try to get Pydantic outputs from tasks for handover visibility
        campaign_plan_output = None
        campaign_table_output = None
        
        if hasattr(phase1_result, 'tasks_output') and phase1_result.tasks_output:
            for task_output in phase1_result.tasks_output:
                if hasattr(task_output, 'pydantic') and task_output.pydantic:
                    pydantic_obj = task_output.pydantic
                    # Check if it's CampaignPlan (from Agent 1)
                    if hasattr(pydantic_obj, 'campaign_occasion'):
                        campaign_plan_output = pydantic_obj
                    # Check if it's CampaignOutlineTable (from Agent 2)
                    elif hasattr(pydantic_obj, 'campaigns'):
                        campaign_table_output = pydantic_obj
        
        # Display Agent 1 → Agent 2 handover (CampaignPlan)
        if campaign_plan_output:
            display_pydantic_handover(
                "AGENT HANDOVER: Campaign Details Extracted",
                campaign_plan_output,
                "Agent 1 (Input Extractor)",
                "Agent 2 (Outline Generator)"
            )
            # Store extracted values for later use
            occasion = campaign_plan_output.campaign_occasion
        else:
            occasion = "Campaign"
        
        # Display the campaign table
        print("\n" + "=" * 70)
        print(" CAMPAIGN TABLE GENERATED!")
        print("=" * 70)
        print(phase1_output)
        print("=" * 70)
        
        # Display Agent 2 → Agent 3 handover (CampaignOutlineTable)
        if campaign_table_output:
            display_pydantic_handover(
                "AGENT HANDOVER: Campaign Table Ready",
                campaign_table_output,
                "Agent 2 (Outline Generator)",
                "Agent 3 (Content Creator)"
            )
        
        # Extract available platforms from the table
        available_platforms = extract_platforms_from_table(phase1_output)
        
        # ============ PLATFORM SELECTION (between Phase 1 and Phase 2) ============
        selected_platform = ask_platform_selection(available_platforms)
        
        # ============ PHASE 2: Agent 3 ============
        print("\n" + "=" * 70)
        print(f" PHASE 2: Generating {selected_platform} Content...")
        print("=" * 70 + "\n")
        
        # Build phase2 inputs from extracted campaign plan
        phase2_inputs = {
            'user_paragraph': user_inputs.get('user_paragraph', ''),
            'selected_platform': selected_platform,
            'campaign_table_context': phase1_output,
        }
        
        # If we have the campaign plan output, add those details
        if campaign_plan_output:
            phase2_inputs.update({
                'campaign_occasion': campaign_plan_output.campaign_occasion,
                'start_date': campaign_plan_output.start_date,
                'end_date': campaign_plan_output.end_date,
                'target_audience': campaign_plan_output.target_audience,
                'campaign_goal': campaign_plan_output.campaign_goal,
            })
        
        phase2_result = planner.phase2_crew(phase1_output).kickoff(inputs=phase2_inputs)
        
        # Get the final content output
        result_text = str(phase2_result.raw) if hasattr(phase2_result, 'raw') else str(phase2_result)
        
        # Save the final output to a file
        file_path = save_final_output(result_text, occasion, selected_platform)
        
        print("\n" + "=" * 80)
        print(" CAMPAIGN CONTENT GENERATED SUCCESSFULLY!")
        print("=" * 80)
        print(f"\n Output saved to: {file_path}")
        print("\n" + "-" * 80)
        print("GENERATED CONTENT:")
        print("-" * 80)
        print(result_text)
        print("=" * 80)
        
        # Display token usage at the end (combine both phases)
        print("\n" + "=" * 70)
        print("TOKEN USAGE SUMMARY")
        print("=" * 70)
        
        # Calculate combined token usage from both phases
        total_prompt = 0
        total_completion = 0
        total_reasoning = 0
        total_output = 0
        total_tokens = 0
        total_requests = 0
        
        # Try to get reasoning tokens from the LLM if it's our custom GPT-5 class
        llm = planner.llm
        if hasattr(llm, 'get_total_usage'):
            # Custom AzureGPT5Completion class with reasoning token tracking
            usage = llm.get_total_usage()
            total_prompt = usage.get('prompt_tokens', 0)
            total_completion = usage.get('completion_tokens', 0)
            total_reasoning = usage.get('reasoning_tokens', 0)
            total_output = usage.get('output_tokens', 0)
            total_tokens = total_prompt + total_completion
        else:
            # Standard LLM - get from phase results
            for phase_result, phase_name in [(phase1_result, "Phase 1"), (phase2_result, "Phase 2")]:
                if hasattr(phase_result, 'token_usage') and phase_result.token_usage:
                    usage = phase_result.token_usage
                    total_prompt += getattr(usage, 'prompt_tokens', 0) or 0
                    total_completion += getattr(usage, 'completion_tokens', 0) or 0
                    total_tokens += getattr(usage, 'total_tokens', 0) or 0
                    total_requests += getattr(usage, 'successful_requests', 0) or 0
            total_output = total_completion  # No reasoning breakdown available
        
        print(f"\n   Input Tokens:               {total_prompt:,}")
        print(f"   Reasoning Tokens:           {total_reasoning:,}")
        print(f"   Output Tokens:              {total_output:,}")
        print(f"   ─────────────────────────────────")
        print(f"   Total Tokens:               {total_tokens:,}")
        
        if total_reasoning > 0:
            print(f"\n   Note: Reasoning tokens are the 'thinking' tokens used by the model.")
            print(f"         Output tokens are the actual response tokens.")
        
        print("\n" + "=" * 70)
        
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    run()
