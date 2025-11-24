from rest_framework import serializers
from news.models import NewsCluster, NewsClusterMember
from .news_serializers import RawNewsListSerializer, CategorySerializer


class NewsClusterMemberSerializer(serializers.ModelSerializer):
    news_detail = RawNewsListSerializer(source='news', read_only=True)
    
    class Meta:
        model = NewsClusterMember
        fields = ['id', 'news', 'news_detail']


class NewsClusterSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags_list = serializers.ListField(read_only=True)
    members = NewsClusterMemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = NewsCluster
        fields = [
            'id', 'description', 'tags', 'tags_list',
            'category', 'category_name', 'news_count',
            'members', 'created_at', 'updated_at'
        ]
        read_only_fields = ['news_count', 'created_at', 'updated_at']


class NewsClusterListSerializer(serializers.ModelSerializer):
    """نسخة مختصرة للقوائم"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = NewsCluster
        fields = [
            'id', 'description', 'category_name',
            'news_count', 'created_at'
        ]


class NewsClusterDetailSerializer(serializers.ModelSerializer):
    """نسخة تفصيلية مع كل الأخبار"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags_list = serializers.ListField(read_only=True)
    news_items = serializers.SerializerMethodField()
    
    class Meta:
        model = NewsCluster
        fields = [
            'id', 'description', 'tags', 'tags_list',
            'category', 'category_name', 'news_count',
            'news_items', 'created_at', 'updated_at'
        ]
    
    def get_news_items(self, obj):
        """جلب كل الأخبار المرتبطة"""
        members = obj.members.select_related('news__source', 'news__category')
        return RawNewsListSerializer(
            [m.news for m in members],
            many=True
        ).data