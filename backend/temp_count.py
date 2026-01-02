import psycopg2
from settings import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

# عدد التقارير بدون صور
cursor.execute('''
    SELECT COUNT(*) FROM generated_report gr
    WHERE gr.status = 'draft'
    AND NOT EXISTS (
        SELECT 1 FROM generated_content gc
        WHERE gc.report_id = gr.id AND gc.content_type_id = 6
    )
''')
images_pending = cursor.fetchone()[0]

# عدد التقارير بدون صوت
cursor.execute('''
    SELECT COUNT(*) FROM generated_report gr
    WHERE gr.status = 'draft'
    AND NOT EXISTS (
        SELECT 1 FROM generated_content gc
        WHERE gc.report_id = gr.id AND gc.content_type_id = 7
    )
''')
audio_pending = cursor.fetchone()[0]

cursor.close()
conn.close()

print(f'تقارير بدون صور: {images_pending}')
print(f'تقارير بدون صوت: {audio_pending}')
