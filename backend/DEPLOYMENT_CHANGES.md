# 🚀 Deployment Changes - Media Worker

## التغييرات المطبقة

### 1. **Dockerfile.worker** - مرونة في التشغيل
```dockerfile
# يشغل media worker إذا WORKER_TYPE=media، وإلا يشغل improved worker
CMD ["sh", "-c", "if [ \"$WORKER_TYPE\" = \"media\" ]; then python test_media_worker.py --continuous; else python start_worker_improved.py; fi"]
```

### 2. **render.yaml** - تحديث للـ media worker
```yaml
envVars:
  - key: WORKER_TYPE
    value: media  # يشغل media worker بدلاً من improved
  - key: REEL_BATCH_SIZE
    value: "4"    # 4 تقارير بدلاً من 10
  - key: IMAGE_BATCH_SIZE
    value: "4"    # 4 تقارير بدلاً من 10
```

### 3. **test_media_worker.py** - محسن للإنتاج
- ✅ Health check server على البورت المحدد
- ✅ إعادة تشغيل تلقائي عند الـ crash
- ✅ معالجة الأخطاء المتتالية
- ✅ تحديث حالة الصحة (healthy/degraded/unhealthy)

---

## كيفية التشغيل

### **على Render (الإنتاج):**
- ✅ `WORKER_TYPE=media` في render.yaml
- ✅ يشغل `test_media_worker.py --continuous`
- ✅ معالجة 4 تقارير فقط لكل نوع
- ✅ دورة كل دقيقتين

### **محلياً (التطوير):**
```bash
# تشغيل media worker
export WORKER_TYPE=media
docker build -f Dockerfile.worker -t worker .
docker run -e WORKER_TYPE=media worker

# تشغيل improved worker (الافتراضي)
docker build -f Dockerfile.worker -t worker .
docker run worker
```

---

## المميزات الجديدة

### **🎯 Media Worker فقط:**
- **الصور**: 4 تقارير بدلاً من 10
- **الريلز**: 4 تقارير بدلاً من 10  
- **النشر**: كل المحتوى المتاح
- **دورة**: كل 2 دقيقة

### **🏥 Health Check:**
- **Endpoint**: `/health`
- **Status**: healthy/degraded/unhealthy
- **Info**: آخر دورة، عدد الدورات، آخر خطأ

### **🔄 إعادة التشغيل الذكي:**
- إعادة تشغيل تلقائي عند الـ crash
- انتظار إضافي عند الأخطاء المتتالية
- تسجيل مفصل للأخطاء

---

## النشر

### **خطوات النشر على Render:**

1. **Push الكود:**
```bash
git add .
git commit -m "Media worker deployment ready"
git push origin main
```

2. **Render سيقوم بـ:**
   - بناء الـ Docker image
   - تشغيل `test_media_worker.py --continuous`
   - معالجة 4 تقارير فقط
   - دورة كل 2 دقيقة

3. **مراقبة:**
   - تحقق من اللوجز
   - تأكد من النص العربي
   - راقب الـ health check

---

## الفرق بين الـ Workers

| Feature | Media Worker | Improved Worker |
|---------|-------------|-----------------|
| **المهام** | صور + ريلز + نشر | كل المهام |
| **الصور** | 4 تقارير | 10 تقارير |
| **الريلز** | 4 تقارير | 10 تقارير |
| **الدورة** | 2 دقيقة | 2 دقيقة |
| **Health Check** | ✅ | ❌ |
| **إعادة تشغيل** | ✅ تلقائي | ❌ |

---

## استكشاف الأخطاء

### **تحقق من نوع الـ Worker:**
```bash
# في Render logs
echo $WORKER_TYPE  # يجب أن يكون "media"
```

### **تحقق من الـ Health:**
```bash
curl http://your-app.onrender.com/health
```

### **مراقبة اللوجز:**
```
🎯 Media Worker Cycle #1
🔄 Step 1: Social Media Images
   Reports processed: 4
🔄 Step 2: Reel Generation  
   Reports processed: 4
🔄 Step 3: Publishing
✅ All media tasks completed successfully!
```

---

*آخر تحديث: يناير 2026*