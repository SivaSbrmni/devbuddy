# Hugging Face MCP Server

A minimal MCP (Model Context Protocol) server wrapping `huggingface_hub`.

## Tools

| Tool | Description |
|------|-------------|
| `hf_search_models` | Search HF models by query |
| `hf_get_model_info` | Fetch metadata for a given model ID |
| `hf_text_generation` | Run text generation via HF Inference API |
| `hf_download_file` | Download a file from a HF repo |

## Setup

1. Install deps (from repo root):
   ```bash
   pip install -r backend/requirements.txt
   ```

2. Set your Hugging Face token (optional but recommended):
   ```bash
   export HF_TOKEN=hf_xxx
   ```

## Run

Start the MCP server over stdio:

```bash
python backend/app/mcp/hf_server.py
```

To connect from an MCP client (e.g., Claude Desktop), add to your client config:

```json
{
  "mcpServers": {
    "huggingface": {
      "command": "python",
      "args": ["/absolute/path/to/backend/app/mcp/hf_server.py"]
    }
  }
}
```
