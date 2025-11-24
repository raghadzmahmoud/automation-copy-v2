from django.db import models
from .clusters import NewsCluster


class GeneratedReport(models.Model):
    """نموذج التقارير المولدة"""
    
    STATUS_CHOICES = [
        ('draft', 'مسودة'),
        ('published', 'منشور'),
        ('archived', 'مؤرشف'),
    ]
    
    cluster = models.OneToOneField(
        NewsCluster,
        on_delete=models.CASCADE,
        related_name='report',
        db_column='cluster_id'
    )
    title = models.CharField(max_length=500)
    content = models.TextField()
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='draft'
    )
    source_news_count = models.IntegerField(default=0)
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'generated_report'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['published_at']),
        ]

    def __str__(self):
        return self.title[:50]

    @property
    def word_count(self):
        """حساب عدد الكلمات"""
        return len(self.content.split())

    def publish(self):
        """نشر التقرير"""
        from django.utils import timezone
        self.status = 'published'
        self.published_at = timezone.now()
        self.save()

    def archive(self):
        """أرشفة التقرير"""
        self.status = 'archived'
        self.save()