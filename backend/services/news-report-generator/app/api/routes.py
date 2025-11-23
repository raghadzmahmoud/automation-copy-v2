from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_endpoint():
    return {
        "message": "News Report Generator API is working!",
        "endpoints": [
            "/api/v1/collect-news",
            "/api/v1/generate-report",
            "/api/v1/reports"
        ]
    }

@router.post("/collect-news")
async def collect_news():
    return {
        "status": "success",
        "message": "News collection endpoint - Coming soon!"
    }

@router.post("/generate-report")
async def generate_report():
    return {
        "status": "success",
        "message": "Report generation endpoint - Coming soon!"
    }