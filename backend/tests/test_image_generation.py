#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Image Generation System
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json


def test_imports():
    """اختبار استيراد المكتبات"""
    print("\n" + "="*70)
    print("1️⃣ Testing Imports")
    print("="*70)
    
    errors = []
    
    # Test boto3
    try:
        import boto3
        print("   ✅ boto3 imported")
    except ImportError as e:
        errors.append(f"boto3: {e}")
        print("   ❌ boto3 not found - run: pip install boto3")
    
    # Test service
    try:
        from app.services.image_generator import ImageGenerator
        print("   ✅ ImageGenerator service imported")
    except Exception as e:
        errors.append(f"ImageGenerator: {e}")
        print(f"   ❌ ImageGenerator: {str(e)[:60]}")
    
    # Test routes
    try:
        from app.api import image_routes
        print("   ✅ Image routes imported")
    except Exception as e:
        errors.append(f"image_routes: {e}")
        print(f"   ❌ image_routes: {str(e)[:60]}")
    
    return len(errors) == 0, errors


def test_aws_connection():
    """اختبار الاتصال بـ AWS S3"""
    print("\n" + "="*70)
    print("2️⃣ Testing AWS S3 Connection")
    print("="*70)
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        s3 = boto3.client('s3')
        
        # Test listing buckets
        try:
            response = s3.list_buckets()
            buckets = [b['Name'] for b in response['Buckets']]
            
            print(f"   ✅ Connected to AWS S3")
            print(f"   📦 Found {len(buckets)} buckets")
            
            # Check if our bucket exists
            if 'media-automation-bucket' in buckets:
                print("   ✅ Target bucket 'media-automation-bucket' found")
                return True, None
            else:
                print("   ⚠️  Bucket 'media-automation-bucket' not found")
                print("   📦 Available buckets:")
                for b in buckets[:5]:
                    print(f"      - {b}")
                return False, "Target bucket not found"
                
        except ClientError as e:
            error_msg = str(e)
            print(f"   ❌ AWS Error: {error_msg[:100]}")
            return False, error_msg
            
    except NoCredentialsError:
        print("   ❌ AWS credentials not found")
        print("   💡 Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False, "No credentials"
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False, str(e)


def test_database_schema():
    """اختبار schema قاعدة البيانات"""
    print("\n" + "="*70)
    print("3️⃣ Testing Database Schema")
    print("="*70)
    
    try:
        from app.utils.database import get_db_connection
        
        conn = get_db_connection()
        if not conn:
            print("   ❌ Database connection failed")
            return False, "Connection failed"
        
        cursor = conn.cursor()
        
        # Check content_types table
        cursor.execute("""
            SELECT id, name FROM content_types
            WHERE id = 6
        """)
        
        row = cursor.fetchone()
        
        if row:
            print(f"   ✅ Content Type found: ID={row[0]}, Name={row[1]}")
        else:
            print("   ⚠️  Content Type ID=6 not found")
            print("   💡 Run: INSERT INTO content_types (id, name, description, created_at, updated_at)")
            print("           VALUES (6, 'Generation Image', 'AI-generated images', NOW(), NOW());")
        
        # Check generated_content table structure
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'generated_content'
            ORDER BY ordinal_position
        """)
        
        columns = [row[0] for row in cursor.fetchall()]
        
        required = ['id', 'report_id', 'content_type_id', 'file_url', 'content']
        missing = [c for c in required if c not in columns]
        
        if not missing:
            print("   ✅ generated_content table has all required columns")
        else:
            print(f"   ❌ Missing columns: {missing}")
            cursor.close()
            conn.close()
            return False, f"Missing columns: {missing}"
        
        # Check scheduled_tasks
        cursor.execute("""
            SELECT id, name FROM scheduled_tasks
            WHERE task_type = 'image_generation'
        """)
        
        task = cursor.fetchone()
        
        if task:
            print(f"   ✅ Scheduled task found: ID={task[0]}, Name={task[1]}")
        else:
            print("   ⚠️  image_generation task not found")
            print("   💡 Run: python add_image_task.py")
        
        cursor.close()
        conn.close()
        
        return True, None
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        return False, str(e)


def test_report_fetch():
    """اختبار جلب التقارير"""
    print("\n" + "="*70)
    print("4️⃣ Testing Report Fetching")
    print("="*70)
    
    try:
        from app.services.image_generator import ImageGenerator
        
        generator = ImageGenerator()
        
        # Fetch reports without images
        reports = generator._fetch_reports_without_images(limit=5)
        
        print(f"   📊 Reports without images: {len(reports)}")
        
        if reports:
            print("   📰 Sample reports:")
            for i, r in enumerate(reports[:3], 1):
                print(f"      {i}. ID={r['id']}: {r['title'][:50]}...")
        else:
            print("   ℹ️  No reports need images (all reports have images)")
        
        generator.close()
        
        return True, None
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def test_dry_run():
    """اختبار توليد صورة (بدون فعلي)"""
    print("\n" + "="*70)
    print("5️⃣ Testing Image Generation (Dry Run)")
    print("="*70)
    
    try:
        from app.services.image_generator import ImageGenerator
        
        generator = ImageGenerator()
        
        # Get first report
        reports = generator._fetch_reports_without_images(limit=1)
        
        if not reports:
            print("   ℹ️  No reports available for testing")
            generator.close()
            return True, "No reports"
        
        report = reports[0]
        print(f"   📰 Test Report: {report['title'][:60]}...")
        
        # Test prompt creation
        prompt = generator._create_image_prompt(report)
        print(f"\n   📝 Generated Prompt:")
        print(f"   {prompt[:200]}...")
        
        # Test keyword extraction
        keywords = generator._extract_keywords(report['title'], report['content'][:500])
        print(f"\n   🔑 Extracted Keywords: {', '.join(keywords[:10])}")
        
        print("\n   ✅ Dry run successful")
        print("   💡 To generate actual image, run:")
        print(f"      python -m app.services.image_generator {report['id']}")
        
        generator.close()
        
        return True, None
        
    except Exception as e:
        print(f"   ❌ Error: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def main():
    """تشغيل جميع الاختبارات"""
    print("\n" + "="*70)
    print("🧪 IMAGE GENERATION SYSTEM - COMPREHENSIVE TEST")
    print("="*70)
    
    results = []
    
    # Run tests
    success, error = test_imports()
    results.append(('Imports', success, error))
    
    success, error = test_aws_connection()
    results.append(('AWS S3', success, error))
    
    success, error = test_database_schema()
    results.append(('Database', success, error))
    
    success, error = test_report_fetch()
    results.append(('Reports', success, error))
    
    success, error = test_dry_run()
    results.append(('Dry Run', success, error))
    
    # Summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for name, success, error in results:
        if success:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}: {error if error else 'Unknown error'}")
            failed += 1
    
    print("\n" + "="*70)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*70)
    
    if failed == 0:
        print("\n🎉 All tests passed! System ready for image generation.")
        print("\n📝 Next steps:")
        print("   1. Verify Google Imagen API Project ID in code")
        print("   2. Test single report: python -m app.services.image_generator <report_id>")
        print("   3. Start API: python api_service.py")
        print("   4. Start worker: python start_worker.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix issues before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())