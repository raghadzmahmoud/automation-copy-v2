# news/admin.py
from django.contrib import admin
from news.models import (
    RawNews, Source, Category, Language,
    NewsCluster, NewsClusterMember,
    GeneratedReport
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['id', 'code', 'name']
    search_fields = ['code', 'name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at']
    search_fields = ['name']
    list_filter = ['created_at']


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'source_type', 'is_active', 'last_fetched']
    list_filter = ['is_active', 'source_type']
    search_fields = ['name', 'url']
    readonly_fields = ['last_fetched', 'created_at', 'updated_at']


@admin.register(RawNews)
class RawNewsAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title_preview', 'source', 'category',
        'language', 'published_at'
    ]
    list_filter = ['source', 'category', 'language', 'published_at']
    search_fields = ['title', 'content_text', 'tags']
    readonly_fields = ['collected_at']
    date_hierarchy = 'published_at'
    
    def title_preview(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_preview.short_description = 'Title'


@admin.register(NewsCluster)
class NewsClusterAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'description_preview', 'category',
        'news_count', 'created_at'
    ]
    list_filter = ['category', 'created_at']
    search_fields = ['description', 'tags']
    readonly_fields = ['news_count', 'created_at', 'updated_at']
    
    def description_preview(self, obj):
        if obj.description:
            return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
        return '-'
    description_preview.short_description = 'Description'


@admin.register(NewsClusterMember)
class NewsClusterMemberAdmin(admin.ModelAdmin):
    list_display = ['id', 'cluster', 'news']
    list_filter = ['cluster']
    search_fields = ['cluster__description', 'news__title']
    raw_id_fields = ['cluster', 'news']


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title_preview', 'status',
        'source_news_count', 'published_at', 'created_at'
    ]
    list_filter = ['status', 'published_at', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at', 'word_count']
    date_hierarchy = 'created_at'
    
    actions = ['publish_reports', 'archive_reports']
    
    def title_preview(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_preview.short_description = 'Title'
    
    def publish_reports(self, request, queryset):
        for report in queryset:
            report.publish()
        self.message_user(request, f'{queryset.count()} reports published successfully')
    publish_reports.short_description = 'Publish selected reports'
    
    def archive_reports(self, request, queryset):
        for report in queryset:
            report.archive()
        self.message_user(request, f'{queryset.count()} reports archived successfully')
    archive_reports.short_description = 'Archive selected reports'