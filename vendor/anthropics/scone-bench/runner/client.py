# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
import os
import subprocess
from contextlib import AsyncExitStack
from inspect import cleandoc
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import ToolBash20250124Param, ToolParam, ToolUnionParam
from anthropic.types.beta import BetaToolTextEditor20250429Param
from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI


class MCPClient:
    def __init__(
        self,
        problem_id: str,
        container_id: str,
        model: str | None = None,
    ):
        # Initialize session and client objects
        self.session: ClientSession | None = None
        self.exit_stack = AsyncExitStack()

        # Initialize Anthropic client
        self.anthropic = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Initialize OpenAI or OpenRouter client based on model
        if model and self.is_openrouter_model(model):
            self.openai = AsyncOpenAI(
                api_key=os.environ.get("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1"
            )
        else:
            self.openai = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        self.problem_id = problem_id
        self.container_id: str = container_id
        self.model = model

    def is_openrouter_model(self, model: str) -> bool:
        """Check if the model is an OpenRouter model (format: provider/model-name)."""
        return "/" in model

    def is_openai_model(self, model: str) -> bool:
        """Check if the model uses OpenAI-compatible API (includes OpenRouter)."""
        return (
            model.startswith(("gpt-3.5", "gpt-4", "gpt-5", "o1", "o1-", "o3", "o3-", "o4", "o4-", "chatgpt-"))
            or "/" in model
        )

    async def connect_to_server(self):
        """Connect to an MCP server running in a Docker container."""
        _ALLOWED_DOCKER_ENV_KEYS = frozenset(
            ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
        )
        _docker_env = {k: v for k, v in os.environ.items() if k in _ALLOWED_DOCKER_ENV_KEYS}
        server_params = StdioServerParameters(
            command="docker", args=["attach", self.container_id], env=_docker_env or None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params),
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

    async def get_prompt(self):
        setup_result = await self.session.call_tool("setup_problem", {"problem_id": self.problem_id})
        return setup_result.content

    async def get_tools(self):
        # convert from MCP Tool to API Tool
        def to_api_tool(tool: Tool) -> ToolUnionParam | BetaToolTextEditor20250429Param | dict[str, Any]:
            if tool.name == "str_replace_editor":
                # Claude 3.x (Sonnet 3.7) uses text_editor_20250124, Claude 4.x uses text_editor_20250728
                if self.model and self.model.startswith("claude-3"):
                    return BetaToolTextEditor20250429Param(type="text_editor_20250124", name="str_replace_editor")
                else:
                    return BetaToolTextEditor20250429Param(
                        type="text_editor_20250728", name="str_replace_based_edit_tool"
                    )
            if tool.name == "bash":
                return ToolBash20250124Param(type="bash_20250124", name="bash")
            if tool.name == "computer":
                if not os.environ.get("COMPUTER_WIDTH_PX") or not os.environ.get("COMPUTER_HEIGHT_PX"):
                    raise ValueError(
                        "COMPUTER_WIDTH_PX and COMPUTER_HEIGHT_PX environment variables must be set to use computer tool"
                    )
                # computer tool is in beta, so we can't directly use a param from the API. But this is how to follow the spec.
                return {
                    "name": "computer",
                    "type": "computer_20250124",
                    "display_number": 1,
                    "display_width_px": int(os.environ["COMPUTER_WIDTH_PX"]),
                    "display_height_px": int(os.environ["COMPUTER_HEIGHT_PX"]),
                }

            if not tool.description or not tool.inputSchema:
                raise ValueError(
                    cleandoc(f"""Custom MCP tool {tool.name} requires both a description and inputSchema.
                
                Add these by:
                1. Adding a docstring to your @mcp.tool decorated function for the description
                2. Using pydantic Field() annotations on function parameters for the schema
                
                Example:
                @mcp.tool()
                def search_files(
                    query: str = Field(description="Search term to look for"),
                    max_results: int = Field(default=10, description="Maximum number of results to return")
                ):
                    '''Search for files matching the given query.''' <-- this is processed as the description
                    # implementation here
                """)
                )
            """Convert a tool to the API format"""
            return ToolParam(
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema,
            )

        if not self.session:
            raise ValueError("Session not initialized. Call connect_to_server() first.")
        mcp_tools = await self.session.list_tools()
        return [
            to_api_tool(tool)
            for tool in mcp_tools.tools
            if tool.name != "setup_problem" and tool.name != "grade_problem"
        ]

    async def execute_tool(self, tool_name: str, tool_args: dict[str, Any]):
        """Execute a tool on the MCP server"""
        if not self.session:
            await self.connect_to_server()

        # Handle transcript conversion for grade_problem if needed
        if tool_name == "grade_problem" and "transcript" in tool_args:
            if isinstance(tool_args["transcript"], list):
                import json

                tool_args = dict(tool_args)  # Make a copy
                tool_args["transcript"] = json.dumps(tool_args["transcript"])

        # Backwards compatibility: the str_replace_editor tool is now called str_replace_based_edit_tool in the API
        if tool_name == "str_replace_based_edit_tool":
            tool_name = "str_replace_editor"

        result = await self.session.call_tool(tool_name, tool_args)
        return result

    async def cleanup(self):
        """Clean up MCP client resources"""
        try:
            if self.container_id:
                subprocess.run(["docker", "kill", self.container_id], check=False)
            await self.exit_stack.aclose()

        except Exception as e:
            print(f"Error during cleanup: {e}")
