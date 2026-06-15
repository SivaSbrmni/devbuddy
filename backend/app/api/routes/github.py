"""GitHub OAuth2 + Repository management API."""

from __future__ import annotations

import time
from typing import Optional, Any

import httpx
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import RedirectResponse
from jose import jwt
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/github", tags=["github"])

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"

# Scopes: repo (full repo access), read:org, read:user, user:email
GITHUB_SCOPES = "repo read:org read:user user:email"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _decode_devbuddy_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _make_jwt_with_github(email: str, name: str, picture: str, github_token: str) -> str:
    payload = {
        "sub": email,
        "email": email,
        "name": name,
        "picture": picture,
        "github_token": github_token,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


async def _github_get(path: str, github_token: str, params: dict | None = None) -> Any:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=params,
            timeout=20,
        )
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="GitHub token expired or revoked")
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def _github_post(path: str, github_token: str, body: dict) -> Any:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=body,
            timeout=20,
        )
        if not resp.is_success:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


def _get_github_token(devbuddy_token: str) -> str:
    payload = _decode_devbuddy_token(devbuddy_token)
    gh = payload.get("github_token")
    if not gh:
        raise HTTPException(status_code=401, detail="GitHub not connected. Please connect GitHub first.")
    return gh


# ── OAuth ─────────────────────────────────────────────────────────────────────

@router.get("/login")
async def github_login(token: Optional[str] = Query(None)) -> RedirectResponse:
    """Redirect to GitHub OAuth consent screen. Passes devbuddy token as state."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GitHub OAuth not configured")
    state = token or ""
    params = (
        f"client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
        f"&scope={GITHUB_SCOPES.replace(' ', '%20')}"
        f"&state={state}"
    )
    return RedirectResponse(url=f"{GITHUB_AUTH_URL}?{params}")


@router.get("/callback")
async def github_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> RedirectResponse:
    """Exchange GitHub code for access token, embed in JWT, redirect to app."""
    if error or not code:
        return RedirectResponse(url=f"{settings.frontend_url}/app?github_error={error or 'missing_code'}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        token_data = token_resp.json()

    github_access_token = token_data.get("access_token")
    if not github_access_token:
        return RedirectResponse(url=f"{settings.frontend_url}/app?github_error=no_token")

    # Fetch GitHub user info
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            f"{GITHUB_API_BASE}/user",
            headers={
                "Authorization": f"Bearer {github_access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        github_user = user_resp.json()

    # If devbuddy token in state, re-issue it with github_token embedded
    if state:
        try:
            existing = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
            new_token = _make_jwt_with_github(
                existing["email"],
                existing.get("name", github_user.get("name", "")),
                existing.get("picture", github_user.get("avatar_url", "")),
                github_access_token,
            )
            return RedirectResponse(url=f"{settings.frontend_url}/app?token={new_token}&github_connected=1")
        except Exception:
            pass

    # Fallback: standalone GitHub login (no Google session)
    email = github_user.get("email") or f"{github_user.get('login')}@github.local"
    new_token = _make_jwt_with_github(
        email,
        github_user.get("name") or github_user.get("login", ""),
        github_user.get("avatar_url", ""),
        github_access_token,
    )
    return RedirectResponse(url=f"{settings.frontend_url}/app?token={new_token}&github_connected=1")


@router.get("/status")
async def github_status(token: Optional[str] = Query(None)) -> dict:
    """Check if GitHub is connected for this session."""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _decode_devbuddy_token(token)
    connected = bool(payload.get("github_token"))
    github_login_val = None
    if connected:
        try:
            user = await _github_get("/user", payload["github_token"])
            github_login_val = user.get("login")
        except Exception:
            connected = False
    return {"connected": connected, "login": github_login_val}


# ── Repositories ──────────────────────────────────────────────────────────────

@router.get("/repos")
async def list_repos(
    token: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    sort: str = Query("pushed"),
    affiliation: str = Query("owner,collaborator,organization_member"),
) -> list[dict]:
    """List all repositories the user has access to."""
    gh = _get_github_token(token or "")
    data = await _github_get("/user/repos", gh, params={
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "affiliation": affiliation,
    })
    return [_format_repo(r) for r in data]


@router.get("/repos/search")
async def search_repos(
    token: Optional[str] = Query(None),
    q: str = Query(...),
) -> list[dict]:
    """Search across user's repos."""
    gh = _get_github_token(token or "")
    payload = _decode_devbuddy_token(token or "")
    # Search within user's repos
    user = await _github_get("/user", gh)
    login = user.get("login", "")
    data = await _github_get("/search/repositories", gh, params={
        "q": f"{q} user:{login}",
        "per_page": 20,
        "sort": "updated",
    })
    return [_format_repo(r) for r in data.get("items", [])]


@router.get("/repos/{owner}/{repo}")
async def get_repo(
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
) -> dict:
    """Get a single repository with full details."""
    gh = _get_github_token(token or "")
    data = await _github_get(f"/repos/{owner}/{repo}", gh)
    return _format_repo(data, full=True)


@router.get("/repos/{owner}/{repo}/branches")
async def list_branches(
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
) -> list[dict]:
    gh = _get_github_token(token or "")
    data = await _github_get(f"/repos/{owner}/{repo}/branches", gh, params={"per_page": 50})
    return [{"name": b["name"], "protected": b.get("protected", False)} for b in data]


@router.get("/repos/{owner}/{repo}/issues")
async def list_issues(
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
    state: str = Query("open"),
    page: int = Query(1),
) -> list[dict]:
    gh = _get_github_token(token or "")
    data = await _github_get(f"/repos/{owner}/{repo}/issues", gh, params={
        "state": state,
        "per_page": 20,
        "page": page,
    })
    return [_format_issue(i) for i in data if "pull_request" not in i]


@router.get("/repos/{owner}/{repo}/pulls")
async def list_prs(
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
    state: str = Query("open"),
) -> list[dict]:
    gh = _get_github_token(token or "")
    data = await _github_get(f"/repos/{owner}/{repo}/pulls", gh, params={
        "state": state,
        "per_page": 20,
    })
    return [_format_pr(p) for p in data]


@router.get("/repos/{owner}/{repo}/languages")
async def get_languages(
    owner: str,
    repo: str,
    token: Optional[str] = Query(None),
) -> dict:
    gh = _get_github_token(token or "")
    return await _github_get(f"/repos/{owner}/{repo}/languages", gh)


@router.get("/repos/{owner}/{repo}/contents")
async def get_contents(
    owner: str,
    repo: str,
    path: str = Query(""),
    ref: str = Query("HEAD"),
    token: Optional[str] = Query(None),
) -> Any:
    gh = _get_github_token(token or "")
    return await _github_get(f"/repos/{owner}/{repo}/contents/{path}", gh, params={"ref": ref})


# ── Create Repository ─────────────────────────────────────────────────────────

class CreateRepoRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True
    auto_init: bool = True
    gitignore_template: str = ""
    license_template: str = ""


@router.post("/repos")
async def create_repo(
    body: CreateRepoRequest,
    token: Optional[str] = Query(None),
) -> dict:
    gh = _get_github_token(token or "")
    payload: dict = {
        "name": body.name,
        "description": body.description,
        "private": body.private,
        "auto_init": body.auto_init,
    }
    if body.gitignore_template:
        payload["gitignore_template"] = body.gitignore_template
    if body.license_template:
        payload["license_template"] = body.license_template
    data = await _github_post("/user/repos", gh, payload)
    return _format_repo(data, full=True)


# ── Issues / PRs actions ──────────────────────────────────────────────────────

class CreateIssueRequest(BaseModel):
    title: str
    body: str = ""
    labels: list[str] = []


@router.post("/repos/{owner}/{repo}/issues")
async def create_issue(
    owner: str,
    repo: str,
    body: CreateIssueRequest,
    token: Optional[str] = Query(None),
) -> dict:
    gh = _get_github_token(token or "")
    data = await _github_post(f"/repos/{owner}/{repo}/issues", gh, {
        "title": body.title,
        "body": body.body,
        "labels": body.labels,
    })
    return _format_issue(data)


class CreatePRRequest(BaseModel):
    title: str
    body: str = ""
    head: str
    base: str = "main"
    draft: bool = False


@router.post("/repos/{owner}/{repo}/pulls")
async def create_pr(
    owner: str,
    repo: str,
    body: CreatePRRequest,
    token: Optional[str] = Query(None),
) -> dict:
    gh = _get_github_token(token or "")
    data = await _github_post(f"/repos/{owner}/{repo}/pulls", gh, {
        "title": body.title,
        "body": body.body,
        "head": body.head,
        "base": body.base,
        "draft": body.draft,
    })
    return _format_pr(data)


# ── Orgs ──────────────────────────────────────────────────────────────────────

@router.get("/orgs")
async def list_orgs(token: Optional[str] = Query(None)) -> list[dict]:
    gh = _get_github_token(token or "")
    data = await _github_get("/user/orgs", gh, params={"per_page": 50})
    return [{"login": o["login"], "avatar_url": o.get("avatar_url", ""), "description": o.get("description", "")} for o in data]


# ── Formatters ────────────────────────────────────────────────────────────────

def _format_repo(r: dict, full: bool = False) -> dict:
    out: dict = {
        "id": r.get("id"),
        "full_name": r.get("full_name", ""),
        "name": r.get("name", ""),
        "owner": r.get("owner", {}).get("login", ""),
        "owner_avatar": r.get("owner", {}).get("avatar_url", ""),
        "description": r.get("description") or "",
        "private": r.get("private", False),
        "language": r.get("language") or "",
        "stargazers_count": r.get("stargazers_count", 0),
        "forks_count": r.get("forks_count", 0),
        "open_issues_count": r.get("open_issues_count", 0),
        "default_branch": r.get("default_branch", "main"),
        "updated_at": r.get("updated_at", ""),
        "pushed_at": r.get("pushed_at", ""),
        "html_url": r.get("html_url", ""),
        "clone_url": r.get("clone_url", ""),
        "size": r.get("size", 0),
        "topics": r.get("topics", []),
        "visibility": r.get("visibility", "public"),
        "fork": r.get("fork", False),
        "archived": r.get("archived", False),
    }
    if full:
        out.update({
            "subscribers_count": r.get("subscribers_count", 0),
            "network_count": r.get("network_count", 0),
            "homepage": r.get("homepage") or "",
            "license": (r.get("license") or {}).get("spdx_id", ""),
        })
    return out


def _format_issue(i: dict) -> dict:
    return {
        "number": i.get("number"),
        "title": i.get("title", ""),
        "state": i.get("state", ""),
        "body": (i.get("body") or "")[:500],
        "labels": [l["name"] for l in i.get("labels", [])],
        "assignees": [a["login"] for a in i.get("assignees", [])],
        "created_at": i.get("created_at", ""),
        "updated_at": i.get("updated_at", ""),
        "html_url": i.get("html_url", ""),
        "user": i.get("user", {}).get("login", ""),
        "comments": i.get("comments", 0),
    }


def _format_pr(p: dict) -> dict:
    return {
        "number": p.get("number"),
        "title": p.get("title", ""),
        "state": p.get("state", ""),
        "body": (p.get("body") or "")[:500],
        "head": p.get("head", {}).get("ref", ""),
        "base": p.get("base", {}).get("ref", ""),
        "draft": p.get("draft", False),
        "created_at": p.get("created_at", ""),
        "updated_at": p.get("updated_at", ""),
        "html_url": p.get("html_url", ""),
        "user": p.get("user", {}).get("login", ""),
        "mergeable": p.get("mergeable"),
        "comments": p.get("comments", 0),
        "review_comments": p.get("review_comments", 0),
        "changed_files": p.get("changed_files", 0),
        "additions": p.get("additions", 0),
        "deletions": p.get("deletions", 0),
    }
