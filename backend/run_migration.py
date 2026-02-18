#!/usr/bin/env python3
"""
🚀 Run Database Migration
═══════════════════════════════════════════════════════════════
يقرأ إعدادات الـ DB من .env تلقائياً ويشغّل الـ migration

Usage:
    python run_migration.py
    python run_migration.py --check    (تحقق فقط بدون تشغيل)
    python run_migration.py --rollback (حذف الجدول إذا أردت التراجع)
═══════════════════════════════════════════════════════════════
"""

import os
import sys
import argparse

# ─── تحميل الـ .env ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settings import DB_CONFIG

import psycopg2

# ─── ألوان للـ terminal ───────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def print_header():
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"{BOLD}  🚀 News Pipeline Queue — Database Migration{RESET}")
    print(f"{BOLD}{'═' * 60}{RESET}")
    print(f"  Host:     {BLUE}{DB_CONFIG.get('host')}:{DB_CONFIG.get('port')}{RESET}")
    print(f"  Database: {BLUE}{DB_CONFIG.get('dbname')}{RESET}")
    print(f"  User:     {BLUE}{DB_CONFIG.get('user')}{RESET}")
    print(f"{'═' * 60}\n")


def get_connection():
    """الاتصال بقاعدة البيانات"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except psycopg2.OperationalError as e:
        print(f"{RED}❌ Cannot connect to database:{RESET}")
        print(f"   {e}")
        print(f"\n{YELLOW}💡 تأكد من:")
        print(f"   1. ملف .env موجود في backend/")
        print(f"   2. DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT صحيحة{RESET}")
        sys.exit(1)


def check_table_exists(conn, table_name: str) -> bool:
    """تحقق إذا الجدول موجود"""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = %s
        )
    """, (table_name,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def check_status(conn):
    """عرض حالة الـ migration"""
    print(f"{BOLD}📊 Migration Status:{RESET}\n")

    tables = {
        'news_pipeline_queue': 'جدول الـ Queue الرئيسي',
    }

    all_ok = True
    for table, desc in tables.items():
        exists = check_table_exists(conn, table)
        status = f"{GREEN}✅ موجود{RESET}" if exists else f"{RED}❌ غير موجود{RESET}"
        print(f"  {table:<35} {status}  ({desc})")
        if not exists:
            all_ok = False

    # تحقق من الـ View
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name = 'v_pipeline_queue_stats'
        )
    """)
    view_exists = cur.fetchone()[0]
    cur.close()

    status = f"{GREEN}✅ موجود{RESET}" if view_exists else f"{RED}❌ غير موجود{RESET}"
    print(f"  {'v_pipeline_queue_stats':<35} {status}  (View للمراقبة)")
    if not view_exists:
        all_ok = False

    print()
    if all_ok:
        print(f"{GREEN}{BOLD}✅ Migration مكتملة — النظام جاهز!{RESET}\n")

        # عرض إحصائيات إذا الجدول موجود
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM news_pipeline_queue")
            count = cur.fetchone()[0]
            cur.close()
            print(f"  📊 عدد المهام في الـ queue: {BLUE}{count}{RESET}\n")
        except:
            pass
    else:
        print(f"{YELLOW}⚠️  Migration غير مكتملة — شغّل: python run_migration.py{RESET}\n")

    return all_ok


def run_migration(conn):
    """تشغيل الـ migration"""
    sql_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'db_migrations',
        'add_news_pipeline_queue.sql'
    )

    if not os.path.exists(sql_file):
        print(f"{RED}❌ ملف الـ migration غير موجود:{RESET}")
        print(f"   {sql_file}")
        sys.exit(1)

    print(f"📄 قراءة الملف: {BLUE}{sql_file}{RESET}\n")

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # تقسيم الـ SQL إلى statements منفصلة
    # نتجاهل الـ COMMIT لأننا نتحكم بالـ transaction يدوياً
    statements = []
    current = []

    for line in sql_content.split('\n'):
        stripped = line.strip()

        # تخطي الـ comments والـ COMMIT
        if stripped.startswith('--') or stripped == 'COMMIT;' or stripped == 'COMMIT':
            continue

        current.append(line)

        # نهاية الـ statement
        if stripped.endswith(';') and not stripped.startswith('--'):
            stmt = '\n'.join(current).strip()
            if stmt and stmt != ';':
                statements.append(stmt)
            current = []

    # إضافة أي شيء متبقي
    if current:
        stmt = '\n'.join(current).strip()
        if stmt:
            statements.append(stmt)

    print(f"  📝 عدد الـ SQL statements: {len(statements)}\n")

    cur = conn.cursor()
    success_count = 0
    skip_count = 0

    for i, stmt in enumerate(statements, 1):
        # أخذ أول سطر للعرض
        first_line = stmt.split('\n')[0][:70].strip()
        if not first_line:
            continue

        try:
            cur.execute(stmt)
            success_count += 1
            print(f"  {GREEN}✅{RESET} [{i:02d}] {first_line}")

        except psycopg2.errors.DuplicateTable:
            conn.rollback()
            conn.autocommit = False
            skip_count += 1
            print(f"  {YELLOW}⏭️{RESET}  [{i:02d}] Already exists (skip): {first_line}")

        except psycopg2.errors.DuplicateObject:
            conn.rollback()
            conn.autocommit = False
            skip_count += 1
            print(f"  {YELLOW}⏭️{RESET}  [{i:02d}] Already exists (skip): {first_line}")

        except Exception as e:
            conn.rollback()
            print(f"\n  {RED}❌ [{i:02d}] Error:{RESET}")
            print(f"      Statement: {first_line}")
            print(f"      Error:     {e}")

            # بعض الـ errors مقبولة (مثل IF NOT EXISTS)
            if 'already exists' in str(e).lower():
                skip_count += 1
                print(f"      {YELLOW}→ Skipping (already exists){RESET}")
                conn.autocommit = False
                continue

            print(f"\n{RED}❌ Migration فشلت — تم التراجع عن كل التغييرات{RESET}\n")
            cur.close()
            sys.exit(1)

    conn.commit()
    cur.close()

    print(f"\n{'─' * 60}")
    print(f"  {GREEN}✅ نجح:{RESET}  {success_count} statements")
    if skip_count:
        print(f"  {YELLOW}⏭️  تخطي:{RESET} {skip_count} statements (موجودة مسبقاً)")
    print(f"{'─' * 60}\n")


def rollback_migration(conn):
    """حذف الجدول (للتراجع)"""
    print(f"{YELLOW}⚠️  Rollback — سيتم حذف:{RESET}")
    print(f"   - جدول news_pipeline_queue")
    print(f"   - view v_pipeline_queue_stats")
    print(f"   - function update_news_pipeline_queue_updated_at")
    print()

    confirm = input("هل أنت متأكد؟ اكتب 'yes' للتأكيد: ").strip().lower()
    if confirm != 'yes':
        print(f"{YELLOW}تم الإلغاء{RESET}")
        return

    cur = conn.cursor()
    try:
        cur.execute("DROP VIEW IF EXISTS v_pipeline_queue_stats CASCADE")
        print(f"  {GREEN}✅{RESET} Dropped view v_pipeline_queue_stats")

        cur.execute("DROP TABLE IF EXISTS news_pipeline_queue CASCADE")
        print(f"  {GREEN}✅{RESET} Dropped table news_pipeline_queue")

        cur.execute("DROP FUNCTION IF EXISTS update_news_pipeline_queue_updated_at() CASCADE")
        print(f"  {GREEN}✅{RESET} Dropped function update_news_pipeline_queue_updated_at")

        conn.commit()
        print(f"\n{GREEN}✅ Rollback مكتمل{RESET}\n")

    except Exception as e:
        conn.rollback()
        print(f"{RED}❌ Rollback فشل: {e}{RESET}")
    finally:
        cur.close()


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Run news_pipeline_queue migration'
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help='تحقق من حالة الـ migration فقط (بدون تشغيل)'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='تراجع عن الـ migration (حذف الجدول)'
    )
    args = parser.parse_args()

    print_header()

    conn = get_connection()
    print(f"{GREEN}✅ Connected to database successfully{RESET}\n")

    try:
        if args.check:
            check_status(conn)

        elif args.rollback:
            rollback_migration(conn)

        else:
            # تحقق أولاً
            already_done = check_table_exists(conn, 'news_pipeline_queue')

            if already_done:
                print(f"{YELLOW}⚠️  الجدول موجود مسبقاً{RESET}\n")
                check_status(conn)
                print(f"{BLUE}💡 لإعادة التشغيل: python run_migration.py --rollback ثم أعد التشغيل{RESET}\n")
            else:
                print(f"{BOLD}🔧 تشغيل الـ Migration...{RESET}\n")
                run_migration(conn)
                print(f"{GREEN}{BOLD}🎉 Migration مكتملة بنجاح!{RESET}\n")
                check_status(conn)
                print(f"{BOLD}🚀 الخطوة التالية:{RESET}")
                print(f"   python pipeline_queue_workers.py --stats\n")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
