"""Simple Hugging Face MCP server using the official MCP SDK and huggingface_hub."""

import os

import httpx
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
        Tool(
            name="hf_get_space_run_logs",
            description="Fetch run logs for a Hugging Face Space",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {
                        "type": "string",
                        "description": "Hugging Face Space ID, e.g. Sivasbrmni/devbuddy",
                    },
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="hf_get_space_build_logs",
            description="Fetch build logs for a Hugging Face Space",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {
                        "type": "string",
                        "description": "Hugging Face Space ID, e.g. Sivasbrmni/devbuddy",
                    },
                },
                "required": ["space_id"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "hf_search_models":
        query = arguments["query"]
        limit = arguments.get("limit", 10)
        models = list(list_models(search=query, limit=limit))
        lines = [f"- {m.id}  (downloads: {m.downloads}, likes: {m.likes})" for m in models]
        return [TextContent(type="text", text="\n".join(lines) if lines else "No models found.")]

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
        return [TextContent(type="text", text=text)]

    elif name == "hf_text_generation":
        model = arguments["model"]
        prompt = arguments["prompt"]
        max_new = arguments.get("max_new_tokens", 128)
        temp = arguments.get("temperature", 0.7)
        try:
            response = infer.text_generation(
                model=model,
                prompt=prompt,
                max_new_tokens=max_new,
                temperature=temp,
            )
            return [TextContent(type="text", text=response)]
        except (RuntimeError, StopIteration) as e:
            err = str(e) or "empty response"
            if "StopIteration" in err or isinstance(e, StopIteration):
                return [TextContent(type="text", text=f"Inference API returned empty response for model '{model}'. The model may not be available on the free inference API.")]
            return [TextContent(type="text", text=f"RuntimeError during inference: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Inference failed: {type(e).__name__}: {e}")]

    elif name == "hf_download_file":
        repo_id = arguments["repo_id"]
        filename = arguments["filename"]
        local_dir = arguments.get("local_dir")
        path = api.hf_hub_download(repo_id=repo_id, filename=filename, local_dir=local_dir, token=HF_TOKEN)
        return [TextContent(type="text", text=f"Downloaded to: {path}")]

    elif name == "hf_get_space_run_logs":
        space_id = arguments["space_id"]
        url = f"https://huggingface.co/api/spaces/{space_id}/logs/run"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=60.0)
                response.raise_for_status()
                return [TextContent(type="text", text=response.text)]
        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"HTTP error fetching run logs: {e.response.status_code}\n{e.response.text}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching run logs: {type(e).__name__}: {e}")]

    elif name == "hf_get_space_build_logs":
        space_id = arguments["space_id"]
        url = f"https://huggingface.co/api/spaces/{space_id}/logs/build"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=60.0)
                response.raise_for_status()
                return [TextContent(type="text", text=response.text)]
        except httpx.HTTPStatusError as e:
            return [TextContent(type="text", text=f"HTTP error fetching build logs: {e.response.status_code}\n{e.response.text}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Error fetching build logs: {type(e).__name__}: {e}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
