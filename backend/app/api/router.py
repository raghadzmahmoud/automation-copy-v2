from fastapi import APIRouter
from .media.avatar_routes import router as avatar_router
from .media.image_routes import router as image_router
from .media.social_media_routes import router as social_media_router
from .media.content_routes import router as content_router

from .media.audio_input_routes import router as audio_input_router
from .media.audio_routes import router as audio_router
from .media.avatar_routes import router as avatar_router
from .media.image_routes import router as image_router
from .media.social_media_routes import router as social_media_router
from .news.category_routes import router as category_router
from .news.cluster_routes import router as cluster_router
from .news.source_routes import router as source_router
from .media.audio_input_routes import router as audio_input_router
from .media.video_input_routes import router as video_input_router
from .news.news_routes import router as news_router
from .reports.report_routes import router as report_router

from .media.audio_routes import router as audio_router
from .media.avatar_routes import router as avatar_router
from .media.image_routes import router as image_router
from .media.social_media_routes import router as social_media_router
from .media.content_routes import router as content_router

from .users.user_routes import router as user_router
from .users.role_routes import router as role_router

from .system.config_routes import router as config_router
from .system.language_routes import router as language_router
from .system.task_routes import router as task_router


# Main API Router
api_router = APIRouter()


# ============================================
# News Module
# ============================================
api_router.include_router(news_router, prefix="/news", tags=["News"])
api_router.include_router(category_router, prefix="/categories", tags=["Categories"])
api_router.include_router(cluster_router, prefix="/clusters", tags=["Clusters"])
api_router.include_router(source_router, prefix="/sources", tags=["Sources"])


# ============================================
# Reports Module
# ============================================
api_router.include_router(report_router, prefix="/reports", tags=["Reports"])


# ============================================
# Media Module
# ============================================
api_router.include_router(audio_router, prefix="/audio", tags=["Audio Generation"])
api_router.include_router(avatar_router, prefix="/avatars", tags=["Avatars & Voices"])
api_router.include_router(image_router, prefix="/images", tags=["Image Generation"])
api_router.include_router(social_media_router, prefix="/social-media", tags=["Social Media"])
api_router.include_router(content_router, prefix="/content", tags=["Generated Content"])


# ============================================
# Users Module
# ============================================
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(role_router, prefix="/roles", tags=["Roles & Permissions"])


# ============================================
# System Module
# ============================================
api_router.include_router(config_router, prefix="/config", tags=["Configuration"])
api_router.include_router(language_router, prefix="/languages", tags=["Languages"])
api_router.include_router(task_router, prefix="/tasks", tags=["Scheduled Tasks"])

# ============================================
# Media Input Module
# ============================================
api_router.include_router(
    audio_input_router,
    prefix="/media/input/audio",
    tags=["Media Input - Audio"]
)

api_router.include_router(
    video_input_router,
    prefix="/media/input/video",
    tags=["Media Input - Video"]
)

# ============================================
# Test Endpoint
# ============================================
@api_router.get("/test")
async def test_endpoint():
    return {
        "message": "AI Media Center API is working!",
        "status": "ok"
    }