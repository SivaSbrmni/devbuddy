#!/bin/bash
# Build script for production deployment
# This builds the frontend and copies it to backend/static for HuggingFace Space deployment

set -e

echo "🏗️  Building DevBuddy for Production Deployment"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Build frontend
echo -e "${BLUE}📦 Building frontend...${NC}"
cd frontend
npm install
VITE_API_URL=https://sivasbrmni-devbuddy.hf.space npm run build
cd ..
echo -e "${GREEN}✓ Frontend built${NC}"
echo ""

# 2. Copy to backend/static
echo -e "${BLUE}📋 Copying frontend to backend/static...${NC}"
rm -rf backend/static/*
cp -r frontend/dist/* backend/static/
echo -e "${GREEN}✓ Frontend copied to backend/static${NC}"
echo ""

# 3. Verify
echo -e "${BLUE}🔍 Verifying build...${NC}"
if [ -f "backend/static/index.html" ]; then
    echo -e "${GREEN}✓ index.html exists${NC}"
else
    echo -e "${RED}✗ index.html missing!${NC}"
    exit 1
fi

if [ -d "backend/static/assets" ]; then
    ASSET_COUNT=$(ls backend/static/assets | wc -l)
    echo -e "${GREEN}✓ assets directory exists ($ASSET_COUNT files)${NC}"
else
    echo -e "${RED}✗ assets directory missing!${NC}"
    exit 1
fi

echo ""
echo "================================================"
echo -e "${GREEN}✅ Build complete! Ready for deployment.${NC}"
echo ""
echo "Next steps:"
echo "  1. Commit changes: git add backend/static && git commit -m 'build: update frontend'"
echo "  2. Push to trigger deployment: git push"
echo ""
