#!/usr/bin/env python3
"""
🔧 Database Encoding Fix Script
═══════════════════════════════════════════════════════════════
يصلح مشاكل الـ encoding في قاعدة البيانات للنصوص العربية

Usage:
    python fix_encoding.py
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import psycopg2
import json
from settings import DB_CONFIG

def check_database_encoding():
    """تحقق من إعدادات الـ encoding في قاعدة البيانات"""
    print("🔍 Checking database encoding settings...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # تحقق من encoding الحالي
        cursor.execute("SHOW client_encoding")
        client_encoding = cursor.fetchone()[0]
        print(f"   Client encoding: {client_encoding}")
        
        cursor.execute("SHOW server_encoding")
        server_encoding = cursor.fetchone()[0]
        print(f"   Server encoding: {server_encoding}")
        
        cursor.execute("SELECT datname, encoding FROM pg_database WHERE datname = current_database()")
        db_info = cursor.fetchone()
        print(f"   Database encoding: {db_info[1]} (encoding ID)")
        
        # تحقق من الـ locale
        cursor.execute("SHOW lc_ctype")
        lc_ctype = cursor.fetchone()[0]
        print(f"   LC_CTYPE: {lc_ctype}")
        
        cursor.execute("SHOW lc_collate")
        lc_collate = cursor.fetchone()[0]
        print(f"   LC_COLLATE: {lc_collate}")
        
        cursor.close()
        conn.close()
        
        return client_encoding, server_encoding
        
    except Exception as e:
        print(f"❌ Error checking encoding: {e}")
        return None, None


def fix_connection_encoding():
    """إصلاح إعدادات الـ encoding للاتصال"""
    print("\n🔧 Fixing connection encoding...")
    
    try:
        # إعداد اتصال مع UTF-8 صريح
        db_config = DB_CONFIG.copy()
        db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on'
        
        conn = psycopg2.connect(**db_config)
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        
        # تعيين encoding صريح
        cursor.execute("SET client_encoding TO 'UTF8'")
        cursor.execute("SET standard_conforming_strings = on")
        cursor.execute("SET escape_string_warning = off")
        
        conn.commit()
        
        # تحقق من النتيجة
        cursor.execute("SHOW client_encoding")
        new_encoding = cursor.fetchone()[0]
        print(f"   ✅ Client encoding set to: {new_encoding}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing encoding: {e}")
        return False


def test_arabic_text():
    """اختبار حفظ واسترجاع النص العربي"""
    print("\n🧪 Testing Arabic text handling...")
    
    try:
        # إعداد اتصال مع UTF-8
        db_config = DB_CONFIG.copy()
        db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on'
        
        conn = psycopg2.connect(**db_config)
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        cursor.execute("SET client_encoding TO 'UTF8'")
        
        # نص عربي للاختبار
        test_data = {
            'h-GAZA': 'https://example.com/gaza.jpg',
            'DOT': 'https://example.com/dot.jpg'
        }
        
        test_json = json.dumps(test_data, ensure_ascii=False)
        print(f"   Test JSON: {test_json}")
        
        # محاولة إدراج البيانات
        cursor.execute("""
            CREATE TEMP TABLE test_encoding (
                id SERIAL PRIMARY KEY,
                content TEXT
            )
        """)
        
        cursor.execute("""
            INSERT INTO test_encoding (content) VALUES (%s)
        """, (test_json,))
        
        # استرجاع البيانات
        cursor.execute("SELECT content FROM test_encoding WHERE id = 1")
        retrieved = cursor.fetchone()[0]
        
        print(f"   Retrieved: {retrieved}")
        
        # مقارنة البيانات
        if test_json == retrieved:
            print("   ✅ Arabic text handling works correctly!")
            success = True
        else:
            print("   ❌ Arabic text was corrupted")
            print(f"   Original:  {repr(test_json)}")
            print(f"   Retrieved: {repr(retrieved)}")
            success = False
        
        cursor.close()
        conn.close()
        
        return success
        
    except Exception as e:
        print(f"❌ Error testing Arabic text: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False


def fix_existing_data():
    """محاولة إصلاح البيانات الموجودة (اختياري)"""
    print("\n🔄 Checking existing data...")
    
    try:
        db_config = DB_CONFIG.copy()
        db_config['options'] = '-c client_encoding=utf8 -c standard_conforming_strings=on'
        
        conn = psycopg2.connect(**db_config)
        conn.set_client_encoding('UTF8')
        
        cursor = conn.cursor()
        cursor.execute("SET client_encoding TO 'UTF8'")
        
        # تحقق من البيانات الموجودة
        cursor.execute("""
            SELECT id, content FROM generated_content 
            WHERE content_type_id = 9 
            AND content IS NOT NULL 
            ORDER BY id DESC LIMIT 5
        """)
        
        results = cursor.fetchall()
        
        if results:
            print(f"   Found {len(results)} Facebook template records")
            for record_id, content in results:
                print(f"   Record {record_id}: {content[:100]}...")
                
                # محاولة parse الـ JSON
                try:
                    parsed = json.loads(content)
                    print(f"     ✅ JSON is valid: {list(parsed.keys())}")
                except json.JSONDecodeError as e:
                    print(f"     ❌ JSON is invalid: {e}")
        else:
            print("   No Facebook template records found")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking existing data: {e}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🔧 Database Encoding Fix Script")
    print("=" * 70)
    
    # تحقق من الـ encoding الحالي
    client_enc, server_enc = check_database_encoding()
    
    if not client_enc:
        print("❌ Could not check database encoding")
        return
    
    # إصلاح الـ encoding
    if fix_connection_encoding():
        print("✅ Connection encoding fixed")
    else:
        print("❌ Could not fix connection encoding")
        return
    
    # اختبار النص العربي
    if test_arabic_text():
        print("✅ Arabic text handling is working")
    else:
        print("❌ Arabic text handling still has issues")
    
    # تحقق من البيانات الموجودة
    fix_existing_data()
    
    print("\n" + "=" * 70)
    print("🎉 Encoding fix script completed")
    print("💡 Try running the image generation again")
    print("=" * 70)


if __name__ == "__main__":
    main()