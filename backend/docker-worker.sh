#!/bin/bash
# 🐳 Docker Worker Management Script
# ═══════════════════════════════════════════════════════════════
# سكريپت لإدارة الـ Docker Worker مع دعم النص العربي
# ═══════════════════════════════════════════════════════════════

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to build the worker image
build_worker() {
    print_status "Building Docker Worker with Arabic support..."
    
    # Check if Dockerfile.worker exists
    if [ ! -f "Dockerfile.worker" ]; then
        print_error "Dockerfile.worker not found in current directory"
        exit 1
    fi
    
    # Build the image
    docker build -f Dockerfile.worker -t automation-worker:latest . \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --progress=plain
    
    print_success "Worker image built successfully"
}

# Function to run the worker
run_worker() {
    print_status "Starting Docker Worker..."
    
    # Stop existing container if running
    if docker ps -q -f name=automation-worker > /dev/null; then
        print_warning "Stopping existing worker container..."
        docker stop automation-worker > /dev/null
        docker rm automation-worker > /dev/null
    fi
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Creating template..."
        cp .env.example .env
        print_warning "Please edit .env file with your configuration"
    fi
    
    # Run the container
    docker run -d \
        --name automation-worker \
        --restart unless-stopped \
        --env-file .env \
        -e PYTHONPATH=/app \
        -e PYTHONUNBUFFERED=1 \
        -e CYCLE_INTERVAL=120 \
        -e BROADCAST_TIMEOUT=600 \
        -e REEL_BATCH_SIZE=4 \
        -v "$(pwd)/logs:/app/logs" \
        -v "$(pwd)/fonts:/app/fonts" \
        automation-worker:latest
    
    print_success "Worker container started"
    
    # Show container status
    docker ps -f name=automation-worker --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to show worker logs
show_logs() {
    print_status "Showing worker logs (press Ctrl+C to exit)..."
    docker logs -f automation-worker
}

# Function to stop the worker
stop_worker() {
    print_status "Stopping Docker Worker..."
    
    if docker ps -q -f name=automation-worker > /dev/null; then
        docker stop automation-worker
        docker rm automation-worker
        print_success "Worker stopped and removed"
    else
        print_warning "Worker container is not running"
    fi
}

# Function to restart the worker
restart_worker() {
    print_status "Restarting Docker Worker..."
    stop_worker
    sleep 2
    run_worker
}

# Function to show worker status
status_worker() {
    print_status "Docker Worker Status:"
    
    if docker ps -q -f name=automation-worker > /dev/null; then
        echo -e "${GREEN}✅ Worker is running${NC}"
        docker ps -f name=automation-worker --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
        
        # Show recent logs
        echo -e "\n${BLUE}Recent logs:${NC}"
        docker logs --tail 10 automation-worker
    else
        echo -e "${RED}❌ Worker is not running${NC}"
        
        # Check if container exists but stopped
        if docker ps -a -q -f name=automation-worker > /dev/null; then
            echo -e "${YELLOW}⚠️  Worker container exists but is stopped${NC}"
            docker ps -a -f name=automation-worker --format "table {{.Names}}\t{{.Status}}\t{{.CreatedAt}}"
        fi
    fi
}

# Function to test Arabic support
test_arabic() {
    print_status "Testing Arabic text support in worker..."
    
    if ! docker ps -q -f name=automation-worker > /dev/null; then
        print_error "Worker container is not running. Start it first with: $0 run"
        exit 1
    fi
    
    # Test Arabic libraries
    docker exec automation-worker python -c "
import sys
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    from PIL import ImageFont
    
    # Test Arabic text processing
    test_text = 'اختبار النص العربي في Docker'
    reshaped = arabic_reshaper.reshape(test_text)
    bidi_text = get_display(reshaped)
    
    print('✅ Arabic libraries working')
    print(f'Original: {test_text}')
    print(f'Processed: {bidi_text}')
    
    # Test font loading
    import os
    font_paths = [
        '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
        'fonts/NotoSansArabic-Regular.ttf'
    ]
    
    font_found = False
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, 48)
                print(f'✅ Font loaded: {font_path}')
                font_found = True
                break
            except Exception as e:
                print(f'⚠️  Font exists but failed to load: {font_path}')
    
    if not font_found:
        print('⚠️  No Arabic fonts found, using default')
    
    print('✅ Arabic support test completed successfully')
    
except ImportError as e:
    print(f'❌ Missing Arabic libraries: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Arabic test failed: {e}')
    sys.exit(1)
"
    
    if [ $? -eq 0 ]; then
        print_success "Arabic support test passed"
    else
        print_error "Arabic support test failed"
    fi
}

# Function to enter worker shell
shell_worker() {
    print_status "Opening shell in worker container..."
    
    if ! docker ps -q -f name=automation-worker > /dev/null; then
        print_error "Worker container is not running. Start it first with: $0 run"
        exit 1
    fi
    
    docker exec -it automation-worker /bin/bash
}

# Function to show help
show_help() {
    echo "🐳 Docker Worker Management Script"
    echo "═══════════════════════════════════════════════════════════════"
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build     Build the worker Docker image"
    echo "  run       Start the worker container"
    echo "  stop      Stop and remove the worker container"
    echo "  restart   Restart the worker container"
    echo "  logs      Show worker logs (follow mode)"
    echo "  status    Show worker status and recent logs"
    echo "  test      Test Arabic text support"
    echo "  shell     Open shell in worker container"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 build && $0 run    # Build and start worker"
    echo "  $0 logs               # Monitor worker logs"
    echo "  $0 test               # Test Arabic support"
    echo "  $0 restart            # Restart worker"
    echo ""
    echo "Features:"
    echo "  ✅ Arabic text support (RTL, font loading)"
    echo "  ✅ Reduced batch sizes (4 reports for reels)"
    echo "  ✅ Enhanced error handling"
    echo "  ✅ Optimized for production deployment"
}

# Main script logic
case "${1:-help}" in
    build)
        check_docker
        build_worker
        ;;
    run)
        check_docker
        run_worker
        ;;
    stop)
        check_docker
        stop_worker
        ;;
    restart)
        check_docker
        restart_worker
        ;;
    logs)
        check_docker
        show_logs
        ;;
    status)
        check_docker
        status_worker
        ;;
    test)
        check_docker
        test_arabic
        ;;
    shell)
        check_docker
        shell_worker
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac