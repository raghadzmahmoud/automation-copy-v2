@echo off
REM Test Docker build locally before deploying (Windows)

echo ═══════════════════════════════════════════════════════════
echo 🐳 Testing Docker Build
echo ═══════════════════════════════════════════════════════════

echo.
echo 📦 Building Docker image...
docker build -f Dockerfile.worker -t worker-test .

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Build successful!
    echo.
    echo 🧪 Testing container...
    
    docker run --rm worker-test python -c "print('✅ Python works'); import psycopg2; print('✅ psycopg2 works'); from app.jobs.audio_transcription_job import run_audio_transcription_job; print('✅ Jobs import works')"
    
    if %ERRORLEVEL% EQU 0 (
        echo.
        echo ✅ All tests passed!
        echo 🚀 Ready for Railway deployment
    ) else (
        echo.
        echo ⚠️  Container test failed
        echo Check the error above
    )
) else (
    echo.
    echo ❌ Build failed!
    echo Check the error above
)

echo.
echo ═══════════════════════════════════════════════════════════
pause
