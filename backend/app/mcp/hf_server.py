"""Simple Hugging Face MCP server using the official MCP SDK and huggingface_hub."""

import os
from typing import AsyncIterator

from huggingface_hub import HfApi, InferenceClient, list_models, model_info
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

HF_TOKEN = os.getenv("HF_TOKEN")

api = HfApi(token=HF_TOKEN)
infer = InferenceClient(token=HF_TOKEN) if HF_TOKEN else InferenceClient()

app = Server("huggingface-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hf_search_models",
            description="Search Hugging Face models by query string",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="hf_get_model_info",
            description="Get detailed info about a Hugging Face model by repo_id",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {"type": "string", "description": "Model repo ID, e.g. meta-llama/Llama-2-7b"},
                },
                "required": ["repo_id"],
            },
        ),
        Tool(
            name="hf_text_generation",
            description="Run text generation via Hugging Face Inference API",
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Model ID for inference"},
                    "prompt": {"type": "string", "description": "Input prompt"},
                    "max_new_tokens": {"type": "integer", "default": 128},
                    "temperature": {"type": "number", "default": 0.7},
                },
                "required": ["model", "prompt"],
            },
        ),
        Tool(
            name="hf_download_file",
            description="Download a file from a Hugging Face repo",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_id": {"type": "string"},
                    "filename": {"type": "string"},
                    "local_dir": {"type": "string", "description": "Optional local directory to save to"},
                },
                "required": ["repo_id", "filename"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> AsyncIterator[TextContent]:
    if name == "hf_search_models":
        query = arguments["query"]
        limit = arguments.get("limit", 10)
        models = list(list_models(search=query, limit=limit))
        lines = [f"- {m.id}  (downloads: {m.downloads}, likes: {m.likes})" for m in models]
        yield TextContent(type="text", text="\n".join(lines) if lines else "No models found.")

    elif name == "hf_get_model_info":
        repo_id = arguments["repo_id"]
        info = model_info(repo_id, token=HF_TOKEN)
        text = (
            f"ID: {info.id}\n"
            f"Tags: {', '.join(info.tags)}\n"
            f"Downloads: {info.downloads}\n"
            f"Likes: {info.likes}\n"
            f"Pipeline tag: {info.pipeline_tag or 'N/A'}\n"
            f"Description: {info.card_data.get('text', 'N/A') if info.card_data else 'N/A'}"
        )
        yield TextContent(type="text", text=text)

    elif name == "hf_text_generation":
        model = arguments["model"]
        prompt = arguments["prompt"]
        max_new = arguments.get("max_new_tokens", 128)
        temp = arguments.get("temperature", 0.7)
        response = infer.text_generation(
            model=model,
            prompt=prompt,
            max_new_tokens=max_new,
            temperature=temp,
        )
        yield TextContent(type="text", text=response)

    elif name == "hf_download_file":
        repo_id = arguments["repo_id"]
        filename = arguments["filename"]
        local_dir = arguments.get("local_dir")
        path = api.hf_hub_download(repo_id=repo_id, filename=filename, local_dir=local_dir, token=HF_TOKEN)
        yield TextContent(type="text", text=f"Downloaded to: {path}")

    else:
        yield TextContent(type="text", text=f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
