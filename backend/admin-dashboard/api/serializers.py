from rest_framework import serializers
from users.models import User
from news.models import NewsSource, Article, GeneratedReport

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class NewsSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsSource
        fields = '__all__'

class ArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source='source.name', read_only=True)
    
    class Meta:
        model = Article
        fields = '__all__'

class GeneratedReportSerializer(serializers.ModelSerializer):
    article_title = serializers.CharField(source='article.title', read_only=True)
    
    class Meta:
        model = GeneratedReport
        fields = '__all__'