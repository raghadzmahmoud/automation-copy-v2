# 🚀 Render Deployment Guide

## Arabic Text Support Optimizations

### Changes Made for Render Compatibility

#### 1. **Enhanced Font Loading**
- **Multiple fallback paths** for Arabic fonts
- **Automatic font installation** on Render containers
- **Font download fallback** from Google Fonts
- **Render-specific font paths** prioritized

#### 2. **Improved Arabic Text Processing**
- **Graceful fallback** when Arabic libraries unavailable
- **Enhanced error handling** for RTL text processing
- **Mobile-optimized** text wrapping (3 words per line)
- **Render container** specific optimizations

#### 3. **Docker Improvements**
- **Arabic fonts pre-installed** (`fonts-noto`, `fonts-noto-arabic`)
- **Font cache refresh** (`fc-cache -fv`)
- **Bundled fonts copied** to container

#### 4. **Reduced Processing Load**
- **Reel generation limit** reduced from 10 to 4 reports
- **Optimized text rendering** for mobile screens
- **Better resource management** for Render containers

---

## Deployment Steps

### 1. Pre-deployment Testing
```bash
# Test Render compatibility
python test_render_compatibility.py

# Test Arabic text processing
python test_arabic_fix.py

# Test reel generation
python test_reel_arabic.py
```

### 2. Environment Variables for Render
Ensure these are set in your Render dashboard:

```env
# Database
DATABASE_URL=postgresql://...

# S3 Configuration
S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Google Services
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
GEMINI_API_KEY=your-gemini-key

# Worker Configuration
CYCLE_INTERVAL=120
BROADCAST_TIMEOUT=600
MAX_PARALLEL_JOBS=3
JOB_TIMEOUT=300
```

### 3. Build Configuration
Your `render.yaml` should include:

```yaml
services:
  - type: worker
    name: media-automation-worker
    env: python
    buildCommand: |
      pip install --upgrade pip
      pip install -r requirements.txt
    startCommand: python start_worker_improved.py
    envVars:
      - key: PYTHONPATH
        value: /opt/render/project/src
      - key: PYTHONUNBUFFERED
        value: "1"
```

---

## Font Support Strategy

### Priority Order:
1. **Bundled fonts** (`backend/fonts/NotoSansArabic-Regular.ttf`)
2. **System fonts** (installed via Dockerfile)
3. **Downloaded fonts** (Google Fonts fallback)
4. **Default font** (with warning)

### Render-Specific Paths:
- `/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf`
- `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
- `/usr/share/fonts/truetype/ubuntu/Ubuntu-Regular.ttf`

---

## Arabic Text Processing

### Libraries Used:
- `arabic-reshaper==3.0.0` - Connects Arabic letters properly
- `python-bidi==0.4.2` - Handles RTL text direction

### Processing Steps:
1. **Text cleaning** and sentence splitting
2. **Word grouping** (3 words per line for mobile)
3. **Arabic reshaping** (letter connection)
4. **BiDi algorithm** (RTL direction)
5. **Fallback handling** if libraries fail

---

## Performance Optimizations

### Reduced Batch Sizes:
- **Reel generation**: 4 reports (was 10)
- **Image generation**: Configurable limit
- **Text processing**: Mobile-optimized

### Resource Management:
- **Timeout protection** for long-running jobs
- **Parallel execution** with limits
- **Memory-efficient** font loading

---

## Troubleshooting

### Common Issues:

#### 1. Arabic Text Appears Reversed
```bash
# Check if libraries are installed
python -c "import arabic_reshaper, bidi; print('OK')"

# Test text processing
python test_arabic_fix.py
```

#### 2. Fonts Not Loading
```bash
# Check font availability
ls -la /usr/share/fonts/truetype/noto/

# Test font loading
python test_render_compatibility.py
```

#### 3. Memory Issues on Render
- Reduce batch sizes in job configurations
- Monitor resource usage in Render dashboard
- Consider upgrading Render plan if needed

### Debug Commands:
```bash
# Check system fonts
fc-list | grep -i arabic

# Test image generation
python -c "from app.services.generators.social_media_image_generator import SocialImageGenerator; print('OK')"

# Test reel generation
python -c "from app.services.generators.reel_generator import ReelGenerator; print('OK')"
```

---

## Monitoring

### Key Metrics to Watch:
- **Memory usage** during image/video generation
- **Font loading success rate**
- **Arabic text processing errors**
- **Job completion times**

### Log Patterns to Monitor:
- `✅ Using Arabic font:` - Font loading success
- `⚠️ Using default font` - Font fallback
- `✅ Processed X lines with Arabic RTL` - Text processing success
- `❌ Arabic processing failed` - Text processing errors

---

## Updates Made

### Files Modified:
- `app/services/generators/reel_generator.py` - Enhanced Arabic support
- `app/services/generators/social_media_image_generator.py` - Improved font loading
- `app/jobs/reel_generation_job.py` - Reduced batch size to 4
- `Dockerfile` - Added Arabic font support
- `requirements.txt` - Already had Arabic libraries

### New Files:
- `test_render_compatibility.py` - Render deployment testing
- `test_arabic_fix.py` - Arabic text fix testing
- `test_reel_arabic.py` - Reel Arabic text testing
- `RENDER_DEPLOYMENT.md` - This documentation

---

## Success Indicators

After deployment, you should see:
- ✅ Arabic text in correct RTL direction
- ✅ Connected Arabic letters in images/videos
- ✅ 4 reports processed per reel generation cycle
- ✅ Proper font loading on Render containers
- ✅ No encoding errors in logs

---

*Last updated: January 2026*