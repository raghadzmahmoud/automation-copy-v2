from django.db import models
from .raw_news import Category, RawNews


class NewsCluster(models.Model):
    """نموذج مجموعات الأخبار"""
    description = models.TextField(blank=True, null=True)
    tags = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column='category_id'
    )
    news_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'news_clusters'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'created_at']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        return f"Cluster #{self.id} - {self.description[:50]}"

    @property
    def tags_list(self):
        """تحويل tags من string إلى list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []

    def update_news_count(self):
        """تحديث عدد الأخبار في المجموعة"""
        self.news_count = self.members.count()
        self.save(update_fields=['news_count'])


class NewsClusterMember(models.Model):
    """نموذج أعضاء مجموعات الأخبار"""
    cluster = models.ForeignKey(
        NewsCluster,
        on_delete=models.CASCADE,
        related_name='members',
        db_column='cluster_id'
    )
    news = models.ForeignKey(
        RawNews,
        on_delete=models.CASCADE,
        related_name='cluster_memberships',
        db_column='news_id'
    )

    class Meta:
        db_table = 'news_cluster_members'
        unique_together = ['cluster', 'news']
        indexes = [
            models.Index(fields=['cluster']),
            models.Index(fields=['news']),
        ]

    def __str__(self):
        return f"Cluster {self.cluster_id} - News {self.news_id}"