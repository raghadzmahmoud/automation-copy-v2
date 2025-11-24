from django.db import models
from django.conf import settings


class Language(models.Model):
    """نموذج اللغات"""
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = 'language'

    def __str__(self):
        return f"{self.name} ({self.code})"


class SourceType(models.Model):
    """أنواع المصادر"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'source_types'

    def __str__(self):
        return self.name


class Source(models.Model):
    """نموذج المصادر"""
    name = models.CharField(max_length=255)
    source_type = models.ForeignKey(
        SourceType, 
        on_delete=models.CASCADE,
        db_column='source_type_id'
    )
    url = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sources'

    def __str__(self):
        return self.name


class Category(models.Model):
    """نموذج التصنيفات"""
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categories'

    def __str__(self):
        return self.name


class RawNews(models.Model):
    """نموذج الأخبار الخام"""
    title = models.CharField(max_length=500)
    content_text = models.TextField(blank=True, null=True)
    content_img = models.TextField(blank=True, null=True)
    content_video = models.TextField(blank=True, null=True)
    tags = models.TextField(blank=True, null=True)
    
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        db_column='source_id'
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
        db_column='language_id'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='category_id'
    )
    
    published_at = models.DateTimeField()
    collected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'raw_news'
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['published_at']),
            models.Index(fields=['source', 'published_at']),
            models.Index(fields=['category', 'published_at']),
        ]

    def __str__(self):
        return self.title[:50]

    @property
    def tags_list(self):
        """تحويل tags من string إلى list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []