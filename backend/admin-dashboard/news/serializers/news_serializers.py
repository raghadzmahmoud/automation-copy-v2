from rest_framework import serializers
from news.models import RawNews, Source, Category, Language


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ['id', 'code', 'name']


class SourceSerializer(serializers.ModelSerializer):
    source_type_name = serializers.CharField(
        source='source_type.name', 
        read_only=True
    )
    
    class Meta:
        model = Source
        fields = [
            'id', 'name', 'source_type', 'source_type_name',
            'url', 'is_active', 'last_fetched'
        ]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class RawNewsSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    tags_list = serializers.ListField(read_only=True)
    
    class Meta:
        model = RawNews
        fields = [
            'id', 'title', 'content_text', 'content_img', 'content_video',
            'tags', 'tags_list', 'source', 'source_name',
            'language', 'language_code', 'category', 'category_name',
            'published_at', 'collected_at'
        ]
        read_only_fields = ['collected_at']


class RawNewsListSerializer(serializers.ModelSerializer):
    """نسخة مختصرة للقوائم"""
    source_name = serializers.CharField(source='source.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = RawNews
        fields = [
            'id', 'title', 'source_name', 'category_name',
            'published_at', 'tags'
        ]