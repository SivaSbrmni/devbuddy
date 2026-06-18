#!/bin/bash
# Pre-Launch Verification Script
# Run this before deploying to production

set -e

echo "🚀 DevBuddy Pre-Launch Verification"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

# Function to check
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1"
        ERRORS=$((ERRORS + 1))
    fi
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

# 1. Check frontend build
echo "📦 Checking frontend build..."
cd frontend
npm run build > /dev/null 2>&1
check "Frontend builds successfully"

# Check for TypeScript errors
npx tsc --noEmit > /dev/null 2>&1
check "No TypeScript errors"

cd ..

# 2. Check backend dependencies
echo ""
echo "🐍 Checking backend dependencies..."
if [ -f "backend/.venv/bin/python" ]; then
    source backend/.venv/bin/activate
    check "Virtual environment exists"
else
    warn "Virtual environment not found (optional for production)"
fi

# 3. Check environment variables
echo ""
echo "🔐 Checking environment configuration..."

if [ -f "backend/.env" ]; then
    check ".env file exists"
    
    # Check critical variables
    SECRET_KEY_VALUE=$(grep "^SECRET_KEY=" backend/.env | cut -d'=' -f2)
    if [ "$SECRET_KEY_VALUE" = "change-me-in-production-32-chars!" ] || [ "$SECRET_KEY_VALUE" = "change-me" ]; then
        warn "SECRET_KEY is using default value - change for production!"
    elif [ -n "$SECRET_KEY_VALUE" ]; then
        check "SECRET_KEY is customized"
    else
        warn "SECRET_KEY not set"
    fi
    
    if grep -q "GOOGLE_CLIENT_ID=" backend/.env; then
        check "GOOGLE_CLIENT_ID is set"
    else
        warn "GOOGLE_CLIENT_ID not set"
    fi
    
    if grep -q "GOOGLE_CLIENT_SECRET=" backend/.env; then
        check "GOOGLE_CLIENT_SECRET is set"
    else
        warn "GOOGLE_CLIENT_SECRET not set"
    fi
else
    warn ".env file not found (will use defaults)"
fi

# 4. Check deployment files
echo ""
echo "🚢 Checking deployment configuration..."

if [ -f "deploy/Dockerfile" ]; then
    check "HuggingFace Dockerfile exists"
else
    echo -e "${RED}✗${NC} HuggingFace Dockerfile missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "deploy/start.sh" ]; then
    check "HuggingFace start.sh exists"
else
    echo -e "${RED}✗${NC} HuggingFace start.sh missing"
    ERRORS=$((ERRORS + 1))
fi

if [ -f ".github/workflows/deploy-pages.yml" ]; then
    check "GitHub Pages workflow exists"
else
    echo -e "${RED}✗${NC} GitHub Pages workflow missing"
    ERRORS=$((ERRORS + 1))
fi

# 5. Check critical files
echo ""
echo "📄 Checking critical files..."

if [ -f "PRODUCTION_READINESS_REPORT.md" ]; then
    check "Production readiness report exists"
else
    warn "Production readiness report not found"
fi

if [ -f "DEBUG_LOG.md" ]; then
    check "Debug log exists (for reference)"
else
    warn "Debug log not found"
fi

# 6. Check git status
echo ""
echo "📝 Checking git status..."

if [ -z "$(git status --porcelain)" ]; then
    check "Working directory is clean"
else
    warn "Uncommitted changes exist"
    git status --short
fi

# 7. Summary
echo ""
echo "===================================="
echo "📊 Summary"
echo "===================================="

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "🚀 Ready for production deployment!"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warning(s)${NC}"
    echo ""
    echo "⚠️  Review warnings before deploying"
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s), $WARNINGS warning(s)${NC}"
    echo ""
    echo "❌ Fix errors before deploying"
    exit 1
fi
