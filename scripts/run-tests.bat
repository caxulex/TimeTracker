@echo off
REM ============================================
REM TIME TRACKER - LOCAL TEST RUNNER (Windows)
REM Phase 7: Testing - Run all tests locally
REM ============================================

echo ============================================
echo TIME TRACKER - Test Suite
echo ============================================
echo.

set FAILURES=0

REM Backend Tests
echo Running Backend Tests...
echo ----------------------------------------
cd backend

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python -m pytest tests/ -v --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] Backend tests failed
    set /a FAILURES+=1
) else (
    echo [PASSED] Backend tests passed
)

cd ..

REM Frontend Unit Tests
echo.
echo Running Frontend Unit Tests...
echo ----------------------------------------
cd frontend

call npm test -- --run
if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] Frontend unit tests failed
    set /a FAILURES+=1
) else (
    echo [PASSED] Frontend unit tests passed
)

REM Frontend Build Check
echo.
echo Running Frontend Build...
echo ----------------------------------------
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] Frontend build failed
    set /a FAILURES+=1
) else (
    echo [PASSED] Frontend build successful
)

cd ..

REM Summary
echo.
echo ============================================
echo Test Summary
echo ============================================
if %FAILURES% EQU 0 (
    echo All tests passed!
    exit /b 0
) else (
    echo %FAILURES% test suite(s) failed
    exit /b 1
)
