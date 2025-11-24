from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from news.models import GeneratedReport
from news.serializers.report_serializers import (
    GeneratedReportSerializer,
    GeneratedReportListSerializer,
    GeneratedReportDetailSerializer
)


class GeneratedReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint للتقارير المولدة
    """
    queryset = GeneratedReport.objects.select_related('cluster__category').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'published_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return GeneratedReportListSerializer
        elif self.action == 'retrieve':
            return GeneratedReportDetailSerializer
        return GeneratedReportSerializer
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """جلب آخر التقارير"""
        limit = int(request.query_params.get('limit', 10))
        recent_reports = self.get_queryset()[:limit]
        serializer = GeneratedReportListSerializer(recent_reports, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def published(self, request):
        """جلب التقارير المنشورة فقط"""
        published_reports = self.get_queryset().filter(status='published')
        page = self.paginate_queryset(published_reports)
        if page is not None:
            serializer = GeneratedReportListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = GeneratedReportListSerializer(published_reports, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def drafts(self, request):
        """جلب المسودات فقط"""
        drafts = self.get_queryset().filter(status='draft')
        page = self.paginate_queryset(drafts)
        if page is not None:
            serializer = GeneratedReportListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = GeneratedReportListSerializer(drafts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """نشر التقرير"""
        report = self.get_object()
        
        if report.status == 'published':
            return Response(
                {'message': 'Report is already published'},
                status=status.HTTP_200_OK
            )
        
        report.publish()
        
        return Response(
            {
                'message': 'Report published successfully',
                'published_at': report.published_at
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """أرشفة التقرير"""
        report = self.get_object()
        
        if report.status == 'archived':
            return Response(
                {'message': 'Report is already archived'},
                status=status.HTTP_200_OK
            )
        
        report.archive()
        
        return Response(
            {'message': 'Report archived successfully'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات التقارير"""
        from django.db.models import Count, Avg
        
        stats = {
            'total_reports': self.get_queryset().count(),
            'published_count': self.get_queryset().filter(status='published').count(),
            'draft_count': self.get_queryset().filter(status='draft').count(),
            'archived_count': self.get_queryset().filter(status='archived').count(),
        }
        
        # متوسط عدد الأخبار المصدرة
        avg_news = self.get_queryset().aggregate(
            avg_news_count=Avg('source_news_count')
        )
        stats.update(avg_news)
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def by_cluster(self, request):
        """جلب التقرير حسب cluster_id"""
        cluster_id = request.query_params.get('cluster_id')
        if not cluster_id:
            return Response(
                {'error': 'cluster_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            report = self.get_queryset().get(cluster_id=cluster_id)
            serializer = GeneratedReportDetailSerializer(report)
            return Response(serializer.data)
        except GeneratedReport.DoesNotExist:
            return Response(
                {'error': 'Report not found for this cluster'},
                status=status.HTTP_404_NOT_FOUND
            )