"""
Unified server: serves the FastAPI backend API + the frontend SPA from a
single origin.  This avoids cross-origin issues when the tunnel URL uses
HTTP Basic Auth (which conflicts with the app's Bearer-token auth if they
are on different origins).

Usage:
    python serve.py          # or: uvicorn serve:combined --host 0.0.0.0 --port 8000
"""
import os, sys

# Make sure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.main import app as backend_app  # the real FastAPI app

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend", "dist")


# --- SPA fallback: serve index.html for any path that doesn't match an
#     API route or a real static file. Must be added *after* all API
#     routes so it only catches unmatched paths.
@backend_app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(request: Request, full_path: str):
    # First check if the path matches a real static file
    file_path = os.path.join(FRONTEND_DIR, full_path)
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Otherwise serve index.html (SPA client-side routing)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


combined = backend_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("serve:combined", host="0.0.0.0", port=8000, log_level="info")
