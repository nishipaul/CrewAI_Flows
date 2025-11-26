"""
Custom Slack Tool for sending messages to Slack channels
Uses slack_sdk to send messages via Slack Bot
"""

import os
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SlackMessageInput(BaseModel):
    """Input schema for SendSlackMessage tool"""
    message: str = Field(
        description="The message text to send to Slack"
    )
    channel: str = Field(
        default="",
        description="Optional: Slack channel name. If empty, uses SLACK_CHANNEL from .env (all-agent-testing-workspace)"
    )


class SendSlackMessage(BaseTool):
    """Tool to send messages to Slack channels using Slack Bot Token"""
    
    name: str = "send_slack_message"
    description: str = (
        "Sends a text message to Slack using the Slack Bot. "
        "Requires 'message' (text content to send). "
        "The channel is automatically set to SLACK_CHANNEL from .env (all-agent-testing-workspace). "
        "Use this tool to post messages to Slack on behalf of the user."
    )
    args_schema: Type[BaseModel] = SlackMessageInput

    def _get_slack_credentials(self) -> tuple:
        """Get Slack credentials from environment variables"""
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        slack_channel = os.getenv("SLACK_CHANNEL")
        
        if not slack_bot_token:
            raise ValueError(
                "SLACK_BOT_TOKEN environment variable not set in .env file. "
                "Please add: SLACK_BOT_TOKEN=xoxb-your-token"
            )
        
        if not slack_channel:
            raise ValueError(
                "SLACK_CHANNEL environment variable not set in .env file. "
                "Please add: SLACK_CHANNEL=all-agent-testing-workspace"
            )
        
        return slack_bot_token, slack_channel

    def _normalize_channel_name(self, channel: str, default_channel: str = None) -> str:
        """
        Normalize channel name to ensure it starts with #
        If no channel provided, use default from env
        """
        if not channel and default_channel:
            channel = default_channel
        
        if not channel:
            raise ValueError("No channel specified and no default SLACK_CHANNEL set in .env")
        
        # Remove # if present, then add it back
        channel = channel.strip()
        if channel.startswith('#'):
            channel = channel[1:]
        
        return channel

    def _run(self, message: str, channel: str = "") -> str:
        """
        Send a message to Slack channel
        
        Args:
            message: Message text to send
            channel: Optional Slack channel name. If empty, uses SLACK_CHANNEL from .env
            
        Returns:
            Success or error message
        """
        try:
            # Import slack_sdk here to avoid import errors if not installed
            try:
                from slack_sdk import WebClient
                from slack_sdk.errors import SlackApiError
            except ImportError:
                return (
                    "❌ Error: slack_sdk not installed. "
                    "Please install it with: pip install slack-sdk"
                )
            
            # Get credentials
            slack_bot_token, default_channel = self._get_slack_credentials()
            
            # Use default channel if not provided or empty
            if not channel or channel.strip() == "":
                channel = default_channel
            
            # Normalize channel name
            channel_name = self._normalize_channel_name(channel, default_channel)
            
            # Use Slack SDK WebClient (standard approach)
            client = WebClient(token=slack_bot_token)
            
            # Send message
            response = client.chat_postMessage(
                channel=channel_name,
                text=message
            )
            
            if response["ok"]:
                return "Message delivered to Slack successfully!"
            else:
                error_msg = response.get("error", "Unknown error")
                return f"❌ Failed to send message to #{channel_name}. Error: {error_msg}"
        
        except SlackApiError as e:
            error_message = e.response.get("error", str(e))
            
            # Provide helpful error messages
            if error_message == "channel_not_found":
                return (
                    f"❌ Channel '#{channel_name}' not found in Slack workspace.\n"
                    f"Please check:\n"
                    f"1. The channel name is correct\n"
                    f"2. The bot has been added to the channel\n"
                    f"3. The channel exists in your workspace"
                )
            elif error_message == "not_in_channel":
                return (
                    f"❌ The Slack bot is not a member of #{channel_name}.\n"
                    f"Please invite the bot to the channel first:\n"
                    f"1. Go to #{channel_name} in Slack\n"
                    f"2. Type: /invite @[your-bot-name]\n"
                    f"3. Try sending the message again"
                )
            elif error_message == "invalid_auth":
                return (
                    f"❌ Slack authentication failed.\n"
                    f"Please check that SLACK_BOT_TOKEN in .env is valid and starts with 'xoxb-'"
                )
            elif error_message == "missing_scope":
                return (
                    f"❌ Slack bot is missing required permissions.\n"
                    f"Please add these scopes to your Slack App:\n"
                    f"1. Go to https://api.slack.com/apps\n"
                    f"2. Select your app\n"
                    f"3. Go to 'OAuth & Permissions'\n"
                    f"4. Add these Bot Token Scopes:\n"
                    f"   - chat:write\n"
                    f"   - chat:write.public\n"
                    f"5. Reinstall the app to your workspace\n"
                    f"6. Copy the new Bot Token to .env"
                )
            else:
                return f"❌ Slack API error: {error_message}"
        
        except ValueError as e:
            return f"❌ Configuration error: {str(e)}"
        
        except Exception as e:
            return f"❌ Unexpected error sending message to Slack: {str(e)}"

