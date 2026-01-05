#!/bin/bash
# 🧪 Media Testing Script
# ═══════════════════════════════════════════════════════════════
# سكريپت لاختبار مكونات الميديا بسهولة
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}$1${NC}"
    echo "═══════════════════════════════════════════════════════════════"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to run quick test
run_quick_test() {
    print_header "⚡ Running Quick Test"
    
    if python quick_test.py; then
        print_success "Quick test passed"
        return 0
    else
        print_error "Quick test failed"
        return 1
    fi
}

# Function to run media worker test
run_media_test() {
    print_header "🎯 Running Media Worker Test"
    
    if python test_media_worker.py; then
        print_success "Media worker test passed"
        return 0
    else
        print_error "Media worker test failed"
        return 1
    fi
}

# Function to test specific report
test_report() {
    local report_id=$1
    print_header "🎯 Testing Report #$report_id"
    
    if python test_media_worker.py --report-id "$report_id"; then
        print_success "Report #$report_id test passed"
        return 0
    else
        print_error "Report #$report_id test failed"
        return 1
    fi
}

# Function to test images only
test_images() {
    print_header "🖼️  Testing Images Only"
    
    if python test_media_worker.py --images-only; then
        print_success "Images test passed"
        return 0
    else
        print_error "Images test failed"
        return 1
    fi
}

# Function to test reels only
test_reels() {
    print_header "🎬 Testing Reels Only"
    
    if python test_media_worker.py --reels-only; then
        print_success "Reels test passed"
        return 0
    else
        print_error "Reels test failed"
        return 1
    fi
}

# Function to test publishing only
test_publishing() {
    print_header "📤 Testing Publishing Only"
    
    if python test_media_worker.py --publishing-only; then
        print_success "Publishing test passed"
        return 0
    else
        print_error "Publishing test failed"
        return 1
    fi
}

# Function to run continuous mode
run_continuous() {
    print_header "🔄 Running Continuous Mode"
    print_warning "Press Ctrl+C to stop"
    
    python test_media_worker.py --continuous
}

# Function to show help
show_help() {
    echo "🧪 Media Testing Script"
    echo "═══════════════════════════════════════════════════════════════"
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  quick         Run quick test (fastest)"
    echo "  media         Run full media worker test"
    echo "  images        Test images only"
    echo "  reels         Test reels only"
    echo "  publishing    Test publishing only"
    echo "  continuous    Run in continuous mode"
    echo "  report <ID>   Test specific report ID"
    echo "  all           Run all tests"
    echo "  help          Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 quick                # Quick test"
    echo "  $0 media                # Full media test"
    echo "  $0 report 123           # Test report #123"
    echo "  $0 images               # Test images only"
    echo "  $0 all                  # Run all tests"
    echo ""
    echo "Features:"
    echo "  ✅ Arabic text support testing"
    echo "  ✅ Font loading verification"
    echo "  ✅ Reduced batch sizes (4 reports)"
    echo "  ✅ Render deployment ready"
}

# Main script logic
case "${1:-help}" in
    quick)
        run_quick_test
        ;;
    media)
        run_media_test
        ;;
    images)
        test_images
        ;;
    reels)
        test_reels
        ;;
    publishing)
        test_publishing
        ;;
    continuous)
        run_continuous
        ;;
    report)
        if [ -z "$2" ]; then
            print_error "Report ID required"
            echo "Usage: $0 report <ID>"
            exit 1
        fi
        test_report "$2"
        ;;
    all)
        print_header "🚀 Running All Tests"
        
        tests_passed=0
        total_tests=4
        
        echo "Test 1/4: Quick Test"
        if run_quick_test; then
            ((tests_passed++))
        fi
        
        echo -e "\nTest 2/4: Images Test"
        if test_images; then
            ((tests_passed++))
        fi
        
        echo -e "\nTest 3/4: Reels Test"
        if test_reels; then
            ((tests_passed++))
        fi
        
        echo -e "\nTest 4/4: Publishing Test"
        if test_publishing; then
            ((tests_passed++))
        fi
        
        echo ""
        print_header "📊 All Tests Summary"
        echo "Tests passed: $tests_passed/$total_tests"
        
        if [ $tests_passed -eq $total_tests ]; then
            print_success "All tests passed! 🎉"
            exit 0
        elif [ $tests_passed -gt 0 ]; then
            print_warning "Some tests passed - check logs for issues"
            exit 1
        else
            print_error "All tests failed - check configuration"
            exit 1
        fi
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