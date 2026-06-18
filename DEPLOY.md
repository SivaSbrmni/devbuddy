# DevBuddy Deployment Guide

## 🚀 Quick Deploy

### Prerequisites
- HuggingFace Space configured at `Sivasbrmni/devbuddy`
- GitHub Pages enabled for `devbuddy.org`
- Environment variables set in HuggingFace Space

### Deploy Steps

1. **Build Frontend**
   ```bash
   ./scripts/build-for-deploy.sh
   ```

2. **Commit & Push**
   ```bash
   git add backend/static
   git commit -m "build: update frontend for deployment"
   git push origin main
   ```

3. **Verify Deployment**
   - Frontend: https://devbuddy.org (auto-deploys from GitHub Pages)
   - Backend: https://sivasbrmni-devbuddy.hf.space (auto-deploys from HF Space)

---

## 🔐 Environment Variables (HuggingFace Space)

### Required
```bash
SECRET_KEY=<generate-32-char-random-string>
GOOGLE_CLIENT_ID=<from-google-cloud-console>
GOOGLE_CLIENT_SECRET=<from-google-cloud-console>
ALLOWED_EMAILS=user1@example.com,user2@example.com
```

### Optional (LLM Providers)
```bash
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_API_KEY=ollama-...
GITHUB_TOKEN=ghp_...
```

### Auto-Configured
```bash
GOOGLE_REDIRECT_URI=https://sivasbrmni-devbuddy.hf.space/api/v1/auth/google/callback
FRONTEND_URL=https://sivasbrmni-devbuddy.hf.space
DATABASE_URL=postgresql+asyncpg://devbuddy:devbuddy@localhost:5432/devbuddy
ENVIRONMENT=production
```

---

## 🧪 Pre-Deploy Verification

Run the pre-launch check:
```bash
./scripts/pre-launch-check.sh
```

Expected output:
```
✓ Frontend builds successfully
✓ No TypeScript errors
✓ Virtual environment exists
✓ SECRET_KEY is customized
✓ GOOGLE_CLIENT_ID is set
✓ GOOGLE_CLIENT_SECRET is set
✓ All deployment files exist
```

---

## 📊 Health Checks

### Backend Health
```bash
curl https://sivasbrmni-devbuddy.hf.space/health
```
Expected: `{"status":"healthy"}`

### Frontend Load
```bash
curl -I https://devbuddy.org
```
Expected: `200 OK`

### Database Migration Status
```bash
curl https://sivasbrmni-devbuddy.hf.space/api/v1/migration-status
```
Expected: `{"all_tables_exist": true, "missing_tables": []}`

---

## 🐛 Troubleshooting

### Frontend not updating
1. Clear GitHub Pages cache
2. Check workflow: https://github.com/SivaSbrmni/devbuddy/actions
3. Verify CNAME: `devbuddy.org`

### Backend errors
1. Check HF Space logs: https://huggingface.co/spaces/Sivasbrmni/devbuddy/logs
2. Verify environment variables are set
3. Check database initialization in logs

### Authentication issues
1. Verify Google OAuth redirect URIs in Console
2. Check ALLOWED_EMAILS includes user's email
3. Verify SECRET_KEY is set and consistent

### SSE connection fails
1. Check CORS configuration includes frontend domain
2. Verify token is being passed correctly
3. Check browser console for connection errors

---

## 🔄 Rollback Procedure

If deployment fails:

1. **Revert to previous commit**
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Or force push previous working commit**
   ```bash
   git reset --hard <previous-commit-hash>
   git push --force origin main
   ```

3. **Monitor HF Space rebuild**
   - Watch logs for successful startup
   - Verify health endpoint returns 200

---

## 📈 Post-Deploy Monitoring

### First 24 Hours
- [ ] Monitor error logs every 2 hours
- [ ] Check user authentication success rate
- [ ] Verify SSE connections are stable
- [ ] Monitor database connection pool

### First Week
- [ ] Review user feedback
- [ ] Check for any 500 errors
- [ ] Monitor LLM API costs
- [ ] Verify GitHub integration works

---

## 🎯 Success Criteria

✅ All tests pass (`pytest tests/`)  
✅ Frontend builds without errors  
✅ Pre-launch check passes  
✅ Health endpoint returns 200  
✅ User can login with Google  
✅ Chat messages send and receive  
✅ SSE real-time updates work  
✅ GitHub integration connects  

---

**Last Updated:** June 18, 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✅
