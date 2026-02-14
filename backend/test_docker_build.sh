#!/bin/bash
# Test Docker build locally before deploying

echo "═══════════════════════════════════════════════════════════"
echo "🐳 Testing Docker Build"
echo "═══════════════════════════════════════════════════════════"

# Build the image
echo ""
echo "📦 Building Docker image..."
docker build -f Dockerfile.worker -t worker-test .

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "🧪 Testing container..."
    
    # Test run (will fail without DB, but should start)
    docker run --rm worker-test python -c "print('✅ Python works'); import psycopg2; print('✅ psycopg2 works'); from app.jobs.audio_transcription_job import run_audio_transcription_job; print('✅ Jobs import works')"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ All tests passed!"
        echo "🚀 Ready for Railway deployment"
    else
        echo ""
        echo "⚠️  Container test failed"
        echo "Check the error above"
    fi
else
    echo ""
    echo "❌ Build failed!"
    echo "Check the error above"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
