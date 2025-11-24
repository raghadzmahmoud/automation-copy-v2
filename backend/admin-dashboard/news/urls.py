from django.urls import path, include
from rest_framework.routers import DefaultRouter

from news.views.news_views import (
    RawNewsViewSet,
    SourceViewSet,
    CategoryViewSet,
    LanguageViewSet
)
from news.views.cluster_views import (
    NewsClusterViewSet,
    NewsClusterMemberViewSet
)
from news.views.report_views import GeneratedReportViewSet

# إنشاء router
router = DefaultRouter()

# تسجيل الـ viewsets
router.register(r'news', RawNewsViewSet, basename='rawnews')
router.register(r'sources', SourceViewSet, basename='source')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'clusters', NewsClusterViewSet, basename='newscluster')
router.register(r'cluster-members', NewsClusterMemberViewSet, basename='clustermember')
router.register(r'reports', GeneratedReportViewSet, basename='report')

urlpatterns = [
    path('', include(router.urls)),
]