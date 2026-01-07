#!/bin/bash
# ============================================
# TIME TRACKER - LOCAL TEST RUNNER
# Phase 7: Testing - Run all tests locally
# ============================================

set -e

echo "============================================"
echo "TIME TRACKER - Test Suite"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILURES=0

# Backend Tests
echo -e "${YELLOW}Running Backend Tests...${NC}"
echo "----------------------------------------"
cd backend

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run pytest
if python -m pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓ Backend tests passed${NC}"
else
    echo -e "${RED}✗ Backend tests failed${NC}"
    FAILURES=$((FAILURES + 1))
fi

cd ..

# Frontend Unit Tests
echo ""
echo -e "${YELLOW}Running Frontend Unit Tests...${NC}"
echo "----------------------------------------"
cd frontend

if npm test -- --run; then
    echo -e "${GREEN}✓ Frontend unit tests passed${NC}"
else
    echo -e "${RED}✗ Frontend unit tests failed${NC}"
    FAILURES=$((FAILURES + 1))
fi

# Frontend Build Check
echo ""
echo -e "${YELLOW}Running Frontend Build...${NC}"
echo "----------------------------------------"
if npm run build; then
    echo -e "${GREEN}✓ Frontend build successful${NC}"
else
    echo -e "${RED}✗ Frontend build failed${NC}"
    FAILURES=$((FAILURES + 1))
fi

cd ..

# Summary
echo ""
echo "============================================"
echo "Test Summary"
echo "============================================"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILURES test suite(s) failed${NC}"
    exit 1
fi
