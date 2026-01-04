import asyncio
import requests
import os
from io import BytesIO
from fastapi import UploadFile

try:
    from app.services.processing.video_input_processor import VideoInputProcessor
except ImportError:
    print("❌ فشل استيراد VideoInputProcessor. استخدم: py -3.11 -m test_video")

async def test_remote_video():
    video_url = "https://media-automation-bucket.s3.us-east-1.amazonaws.com/generated/reels/reel_4870_1767387148.mp4"
    
    print(f"📥 جاري تحميل الفيديو من الرابط...")
    
    try:
        response = requests.get(video_url)
        if response.status_code != 200:
            print(f"❌ فشل تحميل الفيديو.")
            return

        # 1. حفظ المحتوى في متغير ثابت أولاً لمنع ضياعه
        content = response.content
        
        # 2. إنشاء BytesIO مع المحتوى
        video_stream = BytesIO(content)
        
        # 3. محاكاة UploadFile
        upload_file = UploadFile(
            filename="reel_test.mp4",
            file=video_stream
        )

        print(f"🚀 بدء السايكل للفيديو: {upload_file.filename}")

        processor = VideoInputProcessor()
        try:
            # تشغيل المعالجة
            result = processor.process_video(
                file=upload_file,
                user_id=1,
                source_type_id=8
            )

            if result.get('success'):
                print("\n" + "="*50)
                print("✅ اكتملت السايكل بنجاح!")
                print(f"📰 العنوان: {result.get('title')}")
                print(f"🆔 رقم الخبر: {result.get('news_id')}")
                print("="*50)
            else:
                print(f"\n❌ فشلت المعالجة: {result.get('error')}")
        
        finally:
            processor.close()

    except Exception as e:
        print(f"❌ حدث خطأ: {e}")

if __name__ == "__main__":
    asyncio.run(test_remote_video())