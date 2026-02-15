# 🎨 Image Generation Optimization

## 📋 التحديث

تم تحسين Image Generation Job ليولد صور فقط للتقارير اللي الأخبار الأصلية (raw_news) ما فيها صور.

---

## 🎯 الهدف

**توفير استهلاك Gemini API** عن طريق:
- عدم توليد صور للتقارير اللي أخبارها الأصلية فيها صور
- استخدام الصور الموجودة بدل توليد صور جديدة

---

## 🔍 المنطق الجديد

### قبل:
```sql
-- يولد صورة لكل تقرير ما عنده صورة
SELECT * FROM generated_report gr
WHERE NOT EXISTS (
    SELECT 1 FROM generated_content gc
    WHERE gc.report_id = gr.id
    AND gc.content_type_id = 6
)
```

### بعد:
```sql
-- يولد صورة فقط إذا:
-- 1. التقرير ما عنده صورة مولدة
-- 2. الأخبار الأصلية ما فيها صور
SELECT * FROM generated_report gr
WHERE NOT EXISTS (
    SELECT 1 FROM generated_content gc
    WHERE gc.report_id = gr.id
    AND gc.content_type_id = 6
)
AND NOT EXISTS (
    SELECT 1 FROM news_cluster_members ncm
    JOIN raw_news rn ON ncm.news_id = rn.id
    WHERE ncm.cluster_id = gr.cluster_id
    AND rn.image_url IS NOT NULL 
    AND rn.image_url != ''
)
```

---

## 📊 التأثير المتوقع

### مثال:
لو عندك 100 تقرير جديد:
- 60 تقرير من أخبار فيها صور → **لا يولد صور** ✅
- 40 تقرير من أخبار بدون صور → **يولد صور** 🎨

### التوفير:
- **60% أقل** استهلاك لـ Gemini API
- **60% أسرع** في معالجة التقارير
- **نفس الجودة** (الصور الأصلية أفضل من المولدة)

---

## 🔧 الملفات المعدلة

1. **backend/app/jobs/image_generation_job.py**
   - `has_reports_without_images()` - إضافة فلتر الصور الأصلية
   - `has_reports_without_images_simple()` - نفس الفلتر للـ fallback

2. **backend/app/services/generators/image_generator.py**
   - `_fetch_reports_without_images()` - إضافة فلتر الصور الأصلية
   - `_fetch_reports_without_images_simple()` - نفس الفلتر للـ fallback

---

## 🧪 الاختبار

### اختبار يدوي:
```bash
# شوف كم تقرير محتاج صور
python backend/app/jobs/image_generation_job.py --status

# شغل الـ job
python backend/app/jobs/image_generation_job.py
```

### اختبار SQL:
```sql
-- التقارير اللي محتاجة صور (بدون فلتر)
SELECT COUNT(*) FROM generated_report gr
WHERE NOT EXISTS (
    SELECT 1 FROM generated_content gc
    WHERE gc.report_id = gr.id AND gc.content_type_id = 6
);

-- التقارير اللي محتاجة صور (مع الفلتر الجديد)
SELECT COUNT(*) FROM generated_report gr
WHERE NOT EXISTS (
    SELECT 1 FROM generated_content gc
    WHERE gc.report_id = gr.id AND gc.content_type_id = 6
)
AND NOT EXISTS (
    SELECT 1 FROM news_cluster_members ncm
    JOIN raw_news rn ON ncm.news_id = rn.id
    WHERE ncm.cluster_id = gr.cluster_id
    AND rn.image_url IS NOT NULL 
    AND rn.image_url != ''
);
```

---

## 💡 استخدام الصور الأصلية

لو عايز تستخدم الصور الأصلية في الـ API، ممكن تضيف logic في الـ report routes:

```python
# في get_report_by_id أو get_reports
if not report['generated_image']:
    # جيب الصورة من raw_news
    cursor.execute("""
        SELECT rn.image_url 
        FROM news_cluster_members ncm
        JOIN raw_news rn ON ncm.news_id = rn.id
        WHERE ncm.cluster_id = %s
        AND rn.image_url IS NOT NULL
        LIMIT 1
    """, (report['cluster_id'],))
    
    original_image = cursor.fetchone()
    if original_image:
        report['image_url'] = original_image[0]
        report['image_source'] = 'original'
```

---

## 📈 المراقبة

راقب الـ logs:
```bash
tail -f backend/app/logs/image_generation_job.log
```

ابحث عن:
- `Found X reports needing images` - العدد المفروض يقل
- `Images created: X` - العدد المفروض يقل
- `Skipped: X` - ممكن يزيد (لو في تقارير فيها صور أصلية)

---

## ⚠️ ملاحظات

1. **الصور الأصلية أفضل**: الصور من المصادر الإخبارية عادة أفضل من المولدة بالـ AI
2. **التوفير**: هذا يوفر استهلاك API بشكل كبير
3. **السرعة**: الـ job يخلص أسرع لأنه يعالج تقارير أقل

---

تم التحديث: 2026-02-15
