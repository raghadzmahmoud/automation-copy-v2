import sys, os
sys.path.insert(0, os.path.abspath('.'))
try:
    from app.services.ingestion.content_extractor import ContentExtractor, extract_and_prepare_news
    print('IMPORT_OK', ContentExtractor.__name__, extract_and_prepare_news.__name__)
    ext = ContentExtractor()
    r = ext.extract('Title line\n\nArticle body here')
    print('EXTRACT_OK', r.success, r.title)
    news = extract_and_prepare_news('Paragraph1\n\nParagraph2', 'https://example.com', 123, 1)
    print('NEWS_COUNT', len(news))
except Exception as e:
    print('IMPORT_FAIL', e)
