from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from news.models import RawNews, Source, Category, Language
from news.serializers.news_serializers import (
    RawNewsSerializer,
    RawNewsListSerializer,
    SourceSerializer,
    CategorySerializer,
    LanguageSerializer
)


class RawNewsViewSet(viewsets.ModelViewSet):
    """
    API endpoint للأخبار الخام
    
    list: جلب قائمة الأخبار
    retrieve: جلب خبر واحد
    create: إضافة خبر جديد
    update: تحديث خبر
    destroy: حذف خبر
    """
    queryset = RawNews.objects.select_related(
        'source', 'category', 'language'
    ).all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source', 'category', 'language']
    search_fields = ['title', 'content_text', 'tags']
    ordering_fields = ['published_at', 'collected_at']
    ordering = ['-published_at']
    
    def get_serializer_class(self):
        """استخدام serializer مختلف للقائمة والتفاصيل"""
        if self.action == 'list':
            return RawNewsListSerializer
        return RawNewsSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """جلب آخر 20 خبر"""
        recent_news = self.get_queryset()[:20]
        serializer = RawNewsListSerializer(recent_news, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_source(self, request):
        """جلب الأخبار حسب المصدر"""
        source_id = request.query_params.get('source_id')
        if not source_id:
            return Response(
                {'error': 'source_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        news = self.get_queryset().filter(source_id=source_id)
        page = self.paginate_queryset(news)
        if page is not None:
            serializer = RawNewsListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = RawNewsListSerializer(news, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """جلب الأخبار حسب التصنيف"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        news = self.get_queryset().filter(category_id=category_id)
        page = self.paginate_queryset(news)
        if page is not None:
            serializer = RawNewsListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = RawNewsListSerializer(news, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_by_tags(self, request):
        """البحث في الأخبار باستخدام tags"""
        tags = request.query_params.get('tags', '')
        if not tags:
            return Response(
                {'error': 'tags parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # البحث في كل tag
        tag_list = [t.strip() for t in tags.split(',')]
        query = Q()
        for tag in tag_list:
            query |= Q(tags__icontains=tag)
        
        news = self.get_queryset().filter(query)
        page = self.paginate_queryset(news)
        if page is not None:
            serializer = RawNewsListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = RawNewsListSerializer(news, many=True)
        return Response(serializer.data)


class SourceViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint للمصادر (قراءة فقط)"""
    queryset = Source.objects.select_related('source_type').all()
    serializer_class = SourceSerializer
    filterset_fields = ['is_active', 'source_type']
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """جلب المصادر النشطة فقط"""
        active_sources = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(active_sources, many=True)
        return Response(serializer.data)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint للتصنيفات (قراءة فقط)"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint للغات (قراءة فقط)"""
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer