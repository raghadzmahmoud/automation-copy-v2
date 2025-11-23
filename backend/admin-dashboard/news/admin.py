from django.contrib import admin
from .models import NewsSource, Article, GeneratedReport

@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'is_active', 'created_at']
    list_filter = ['source_type', 'is_active']
    search_fields = ['name', 'url']

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'source', 'category', 'language', 'sentiment', 'published_at']
    list_filter = ['source', 'category', 'language', 'sentiment', 'published_at']
    search_fields = ['title', 'content', 'author']
    date_hierarchy = 'published_at'

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ['article', 'format_type', 'created_by', 'created_at']
    list_filter = ['format_type', 'created_at']
    search_fields = ['article__title', 'content']