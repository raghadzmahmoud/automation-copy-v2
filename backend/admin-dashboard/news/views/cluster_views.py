from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count

from news.models import NewsCluster, NewsClusterMember
from news.serializers.cluster_serializers import (
    NewsClusterSerializer,
    NewsClusterListSerializer,
    NewsClusterDetailSerializer,
    NewsClusterMemberSerializer
)


class NewsClusterViewSet(viewsets.ModelViewSet):
    """
    API endpoint لمجموعات الأخبار
    """
    queryset = NewsCluster.objects.select_related('category').prefetch_related(
        'members__news__source'
    ).all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category']
    search_fields = ['description', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'news_count']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return NewsClusterListSerializer
        elif self.action == 'retrieve':
            return NewsClusterDetailSerializer
        return NewsClusterSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """جلب آخر المجموعات"""
        limit = int(request.query_params.get('limit', 10))
        recent_clusters = self.get_queryset()[:limit]
        serializer = NewsClusterListSerializer(recent_clusters, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """جلب المجموعات حسب التصنيف"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        clusters = self.get_queryset().filter(category_id=category_id)
        page = self.paginate_queryset(clusters)
        if page is not None:
            serializer = NewsClusterListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = NewsClusterListSerializer(clusters, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def news_items(self, request, pk=None):
        """جلب كل الأخبار في المجموعة"""
        cluster = self.get_object()
        members = cluster.members.select_related('news__source', 'news__category')
        serializer = NewsClusterMemberSerializer(members, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_news(self, request, pk=None):
        """إضافة خبر للمجموعة"""
        cluster = self.get_object()
        news_id = request.data.get('news_id')
        
        if not news_id:
            return Response(
                {'error': 'news_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from news.models import RawNews
            news = RawNews.objects.get(id=news_id)
            
            # إضافة الخبر للمجموعة
            member, created = NewsClusterMember.objects.get_or_create(
                cluster=cluster,
                news=news
            )
            
            if not created:
                return Response(
                    {'message': 'News already in cluster'},
                    status=status.HTTP_200_OK
                )
            
            # تحديث عدد الأخبار
            cluster.update_news_count()
            
            return Response(
                {'message': 'News added to cluster successfully'},
                status=status.HTTP_201_CREATED
            )
            
        except RawNews.DoesNotExist:
            return Response(
                {'error': 'News not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['delete'])
    def remove_news(self, request, pk=None):
        """حذف خبر من المجموعة"""
        cluster = self.get_object()
        news_id = request.query_params.get('news_id')
        
        if not news_id:
            return Response(
                {'error': 'news_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            member = NewsClusterMember.objects.get(
                cluster=cluster,
                news_id=news_id
            )
            member.delete()
            
            # تحديث عدد الأخبار
            cluster.update_news_count()
            
            return Response(
                {'message': 'News removed from cluster successfully'},
                status=status.HTTP_200_OK
            )
            
        except NewsClusterMember.DoesNotExist:
            return Response(
                {'error': 'News not found in cluster'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات المجموعات"""
        from django.db.models import Avg, Max, Min
        
        stats = self.get_queryset().aggregate(
            total_clusters=Count('id'),
            avg_news_count=Avg('news_count'),
            max_news_count=Max('news_count'),
            min_news_count=Min('news_count')
        )
        
        return Response(stats)


class NewsClusterMemberViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint لأعضاء المجموعات (قراءة فقط)"""
    queryset = NewsClusterMember.objects.select_related(
        'cluster', 'news'
    ).all()
    serializer_class = NewsClusterMemberSerializer
    filterset_fields = ['cluster', 'news']