#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🧪 Test Script for Updated Schema
اختبار شامل بعد التحديثات
"""

import sys
import os

print("="*70)
print("🧪 Testing Updated Schema Compatibility")
print("="*70)

errors = []
warnings = []
success = []

# Test 1: Database Connection
print("\n1️⃣ Testing Database Connection...")
try:
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        success.append("Database connection")
        print("   ✅ Connected successfully")
    else:
        errors.append("Database connection returned None")
except Exception as e:
    errors.append(f"Database connection: {e}")
    print(f"   ❌ {e}")

# Test 2: Language Table
print("\n2️⃣ Testing Language Table...")
try:
    from app.utils.database import get_language_id
    
    # Test with 'ar'
    lang_id = get_language_id('ar')
    
    if lang_id:
        success.append("Language table (code field)")
        print(f"   ✅ Arabic language_id: {lang_id}")
    else:
        warnings.append("No Arabic language found")
        print("   ⚠️  No Arabic language")
        
except Exception as e:
    errors.append(f"Language test: {e}")
    print(f"   ❌ {e}")

# Test 3: Source Types Table
print("\n3️⃣ Testing Source Types...")
try:
    from app.utils.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if source_types exists
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = 'source_types'
    """)
    
    if cursor.fetchone()[0] > 0:
        # Get source types
        cursor.execute("SELECT id, name FROM source_types")
        types = cursor.fetchall()
        
        if types:
            success.append("Source types table")
            print(f"   ✅ Found {len(types)} source types:")
            for t in types:
                print(f"      - {t[1]} (ID: {t[0]})")
        else:
            warnings.append("No source types found")
            print("   ⚠️  No source types in table")
    else:
        errors.append("source_types table not found")
        print("   ❌ Table doesn't exist")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    errors.append(f"Source types: {e}")
    print(f"   ❌ {e}")

# Test 4: Sources Table Structure
print("\n4️⃣ Testing Sources Table...")
try:
    from app.utils.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check columns
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'sources'
        ORDER BY ordinal_position
    """)
    
    columns = [row[0] for row in cursor.fetchall()]
    
    required_columns = ['id', 'name', 'source_type_id', 'url', 'is_active', 'last_fetched']
    missing = [col for col in required_columns if col not in columns]
    
    if not missing:
        success.append("Sources table structure")
        print("   ✅ All required columns present")
    else:
        errors.append(f"Sources missing columns: {missing}")
        print(f"   ❌ Missing: {missing}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    errors.append(f"Sources structure: {e}")
    print(f"   ❌ {e}")

# Test 5: Get Active Sources
print("\n5️⃣ Testing get_active_sources()...")
try:
    from app.utils.database import get_active_sources
    
    sources = get_active_sources()
    
    if sources:
        success.append("get_active_sources()")
        print(f"   ✅ Found {len(sources)} active sources")
        
        # Check first source structure
        first = sources[0]
        required_keys = ['id', 'name', 'source_type_id', 'url', 'source_type_name']
        missing_keys = [k for k in required_keys if k not in first]
        
        if missing_keys:
            warnings.append(f"Source dict missing keys: {missing_keys}")
            print(f"   ⚠️  Missing keys: {missing_keys}")
        else:
            print(f"   ✅ Source structure correct")
            print(f"      Example: {first['name']} ({first['source_type_name']})")
    else:
        warnings.append("No active sources")
        print("   ⚠️  No active sources found")
        
except Exception as e:
    errors.append(f"get_active_sources(): {e}")
    print(f"   ❌ {e}")

# Test 6: Generated Report Table
print("\n6️⃣ Testing generated_report Table...")
try:
    from app.utils.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'generated_report'
        ORDER BY ordinal_position
    """)
    
    columns = [row[0] for row in cursor.fetchall()]
    
    # Check new schema
    should_have = ['status', 'published_at']
    should_not_have = ['word_count', 'model_used', 'generation_time_seconds']
    
    has_new = [col for col in should_have if col in columns]
    has_old = [col for col in should_not_have if col in columns]
    
    if len(has_new) == len(should_have) and not has_old:
        success.append("generated_report schema")
        print("   ✅ Schema updated correctly")
    else:
        if has_old:
            warnings.append(f"Old columns still present: {has_old}")
            print(f"   ⚠️  Old columns: {has_old}")
        if len(has_new) < len(should_have):
            missing_new = [col for col in should_have if col not in has_new]
            errors.append(f"Missing new columns: {missing_new}")
            print(f"   ❌ Missing: {missing_new}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    errors.append(f"generated_report: {e}")
    print(f"   ❌ {e}")

# Test 7: Scheduled Tasks Table
print("\n7️⃣ Testing scheduled_tasks Table...")
try:
    from app.utils.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'scheduled_tasks'
    """)
    
    columns = [row[0] for row in cursor.fetchall()]
    
    if 'name' in columns and 'task_type' in columns:
        success.append("scheduled_tasks schema")
        print("   ✅ Has 'name' and 'task_type' columns")
        
        # Check if there are tasks
        cursor.execute("SELECT COUNT(*) FROM scheduled_tasks")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"   ✅ Found {count} scheduled tasks")
        else:
            warnings.append("No scheduled tasks")
            print("   ⚠️  No tasks in table")
    else:
        errors.append("scheduled_tasks missing required columns")
        print("   ❌ Missing 'name' or 'task_type'")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    errors.append(f"scheduled_tasks: {e}")
    print(f"   ❌ {e}")

# Test 8: Import Services
print("\n8️⃣ Testing Services Import...")
services = [
    ('scraper', 'app.services.scraper', 'NewsScraper'),
    ('classifier', 'app.services.classifier', 'classify_with_gemini'),
    ('clustering', 'app.services.clustering', 'NewsClusterer'),
    ('reporter', 'app.services.reporter', 'ReportGenerator'),
]

for name, module, obj in services:
    try:
        exec(f"from {module} import {obj}")
        success.append(f"{name} service")
        print(f"   ✅ {name}")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"   ❌ {name}: {str(e)[:60]}")

# Final Summary
print("\n" + "="*70)
print("📊 Test Results Summary")
print("="*70)

if success:
    print(f"\n✅ Passed ({len(success)}):")
    for s in success:
        print(f"   • {s}")

if warnings:
    print(f"\n⚠️  Warnings ({len(warnings)}):")
    for w in warnings:
        print(f"   • {w}")

if errors:
    print(f"\n❌ Errors ({len(errors)}):")
    for e in errors:
        print(f"   • {e}")

print("\n" + "="*70)

if errors:
    print("⚠️  Please fix errors before running the system")
    sys.exit(1)
elif warnings:
    print("✅ System can run but check warnings")
    sys.exit(0)
else:
    print("🎉 All tests passed! System ready!")
    sys.exit(0)