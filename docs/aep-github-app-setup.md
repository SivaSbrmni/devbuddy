# AEP GitHub App Setup

This document describes how to configure a GitHub App for use with the
DevBuddy Autonomous Engineering Platform (AEP). The GitHub App
integration provides the highest rate limits (5,000+ req/hr) and
fine-grained permissions.

## Prerequisites

- A GitHub account with admin access to the target organization or
  repository.
- DevBuddy backend running (docker-compose or direct).

## 1. Create the GitHub App

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**
   (or use `https://github.com/settings/apps/new`).
2. Fill in:
   - **App name:** `devbuddy-aep` (or your preferred name)
   - **Homepage URL:** Your DevBuddy instance URL
   - **Webhook URL:** `https://<your-domain>/api/v1/aep/webhooks/github`
   - **Webhook secret:** Generate a strong secret (store it — you'll
     need it for `GITHUB_WEBHOOK_SECRET`)
3. **Permissions** (Repository):
   - Contents: **Read & Write**
   - Pull requests: **Read & Write**
   - Actions: **Read-only**
   - Checks: **Read-only**
   - Metadata: **Read-only** (automatically granted)
4. **Subscribe to events:**
   - `push`
   - `pull_request`
   - `workflow_run`
   - `check_run`
   - `issue_comment`
   - `pull_request_review`
   - `installation`
   - `installation_repositories`
5. **Where can this GitHub App be installed?** — Choose based on your
   needs (only this account, or any account).
6. Click **Create GitHub App**.

## 2. Generate a Private Key

1. On the App settings page, scroll to **Private keys**.
2. Click **Generate a private key**.
3. A `.pem` file downloads — store it securely.

## 3. Install the App

1. Go to your App's page → **Install App**.
2. Select the organization/account and choose repositories.
3. Note the **Installation ID** from the URL after installation
   (e.g., `https://github.com/settings/installations/12345678` →
   ID is `12345678`).

## 4. Configure DevBuddy Environment

Set the following environment variables:

```bash
# GitHub App credentials
GITHUB_APP_ID=<your-app-id>
GITHUB_APP_PRIVATE_KEY=<contents-of-the-pem-file>
GITHUB_APP_INSTALLATION_ID=<installation-id>

# Webhook verification
GITHUB_WEBHOOK_SECRET=<the-secret-from-step-1>
```

For Docker deployments, add these to your `.env` file or pass them via
`docker-compose.yml` environment section.

**Note:** `GITHUB_APP_PRIVATE_KEY` should be the full PEM content
including `-----BEGIN RSA PRIVATE KEY-----` headers. In Docker, you can
use multi-line env vars or mount the key as a file and read it at
startup.

## 5. Alternative: Personal Access Token (PAT)

For local development or simple setups, use a PAT instead:

```bash
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Required PAT scopes: `repo`, `workflow`, `read:org`.

The system auto-detects which credentials are available:
1. If `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` +
   `GITHUB_APP_INSTALLATION_ID` are all set → uses GitHub App auth.
2. If `GITHUB_TOKEN` (or `GH_TOKEN`) is set → uses PAT auth.
3. Otherwise → raises an error at startup.

## 6. Alternative: OAuth (per-user)

For acting on behalf of a logged-in user, the `OAuthClient` uses the
access token obtained through the OAuth callback. This is handled
automatically by the frontend login flow and stored in the user session.

## 7. Verify the Setup

```bash
# Check webhook connectivity
curl -X POST https://<your-domain>/api/v1/aep/webhooks/github \
  -H "X-GitHub-Event: ping" \
  -H "X-GitHub-Delivery: test-123" \
  -d '{}'

# Check GitHub client (requires the backend to be running)
# The /api/v1/aep/status endpoint reports GitHub client status
curl https://<your-domain>/api/v1/aep/status
```

## 8. Feature Flag

The webhook receiver is gated behind the `webhook_receiver_enabled`
feature flag. Enable it via the admin API:

```bash
curl -X PUT https://<your-domain>/api/v1/aep/flags/webhook_receiver_enabled \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

## Rate Limits

| Auth Method  | Rate Limit         | Best For                |
|-------------|-------------------|-------------------------|
| GitHub App  | 5,000 req/hr/inst | Production              |
| PAT         | 5,000 req/hr      | Development, single-user |
| OAuth       | 5,000 req/hr/user | User-scoped actions     |

## Troubleshooting

- **401 on webhooks**: Check `GITHUB_WEBHOOK_SECRET` matches the App
  configuration.
- **Token refresh failures**: Verify `GITHUB_APP_PRIVATE_KEY` is
  correctly formatted (full PEM content, no extra whitespace).
- **Rate limiting**: Monitor via `GET /rate_limit` through the GitHub
  client. The App auth has per-installation limits which scale with
  the number of repositories.
