from rest_framework import serializers
from news.models import GeneratedReport
from .cluster_serializers import NewsClusterListSerializer


class GeneratedReportSerializer(serializers.ModelSerializer):
    cluster_description = serializers.CharField(
        source='cluster.description',
        read_only=True
    )
    word_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'cluster', 'cluster_description', 'title', 'content',
            'status', 'source_news_count', 'word_count',
            'published_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['published_at', 'created_at', 'updated_at']


class GeneratedReportListSerializer(serializers.ModelSerializer):
    """نسخة مختصرة للقوائم"""
    cluster_description = serializers.CharField(
        source='cluster.description',
        read_only=True
    )
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'title', 'status', 'cluster_description',
            'source_news_count', 'created_at'
        ]


class GeneratedReportDetailSerializer(serializers.ModelSerializer):
    """نسخة تفصيلية مع معلومات الـ cluster"""
    cluster_detail = NewsClusterListSerializer(source='cluster', read_only=True)
    word_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = [
            'id', 'cluster', 'cluster_detail', 'title', 'content',
            'status', 'source_news_count', 'word_count',
            'published_at', 'created_at', 'updated_at'
        ]