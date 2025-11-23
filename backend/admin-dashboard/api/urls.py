from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, NewsSourceViewSet, 
    ArticleViewSet, GeneratedReportViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'news-sources', NewsSourceViewSet)
router.register(r'articles', ArticleViewSet)
router.register(r'reports', GeneratedReportViewSet)

urlpatterns = [
    path('', include(router.urls)),
]