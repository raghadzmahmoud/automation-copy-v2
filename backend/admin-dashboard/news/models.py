from django.db import models
from django.conf import settings

class NewsSource(models.Model):
    """News Source Model"""
    name = models.CharField(max_length=200)
    url = models.URLField()
    api_key = models.CharField(max_length=255, blank=True, null=True)
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('rss', 'RSS Feed'),
            ('api', 'API'),
            ('web', 'Web Scraping'),
        ]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sources'
    
    def __str__(self):
        return self.name


class Article(models.Model):
    """Article Model"""
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='articles')
    title = models.CharField(max_length=500)
    content = models.TextField(db_column='content_text')
    summary = models.TextField(blank=True, null=True)
    author = models.CharField(max_length=200, blank=True, null=True)
    published_at = models.DateTimeField()
    url = models.URLField()
    image_url = models.URLField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('positive', 'Positive'),
            ('negative', 'Negative'),
            ('neutral', 'Neutral'),
        ],
        blank=True,
        null=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'raw_news'
        ordering = ['-published_at']
    
    def __str__(self):
        return self.title


class GeneratedReport(models.Model):
    """Generated Report Model"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='reports')
    format_type = models.CharField(
        max_length=50,
        choices=[
            ('text', 'Text Report'),
            ('audio_script', 'Audio Script'),
            ('video_script', 'Video Script'),
            ('social_twitter', 'Twitter Post'),
            ('social_facebook', 'Facebook Post'),
            ('social_instagram', 'Instagram Post'),
            ('email', 'Email Newsletter'),
        ]
    )
    content = models.TextField()
    metadata = models.JSONField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'generated_report'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.article.title} - {self.format_type}"
