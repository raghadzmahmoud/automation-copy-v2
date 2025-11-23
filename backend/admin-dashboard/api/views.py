from django.shortcuts import render

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from users.models import User
from news.models import NewsSource, Article, GeneratedReport
from .serializers import (
    UserSerializer, NewsSourceSerializer, 
    ArticleSerializer, GeneratedReportSerializer
)

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class NewsSourceViewSet(viewsets.ModelViewSet):
    queryset = NewsSource.objects.all()
    serializer_class = NewsSourceSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        recent_articles = self.queryset.order_by('-published_at')[:10]
        serializer = self.get_serializer(recent_articles, many=True)
        return Response(serializer.data)

class GeneratedReportViewSet(viewsets.ModelViewSet):
    queryset = GeneratedReport.objects.all()
    serializer_class = GeneratedReportSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]