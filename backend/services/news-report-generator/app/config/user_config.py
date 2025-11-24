from pydantic import BaseModel

class UserConfig(BaseModel):
    # Display
    news_display_limit: int = 10
    
    # Scraping (every 10 minutes)
    scraping_enabled: bool = True
    scraping_timeout_seconds: int = 30
    max_news_per_source: int = 50
    default_fetch_interval_minutes: int = 10  # ← Changed to 10
    
    # Clustering (every 1 hour, look back 48 hours)
    clustering_enabled: bool = True
    clustering_time_window_hours: int = 48  # ← Changed to 48
    clustering_min_similarity: float = 0.15
    
    # Reports (every 1 hour, from clusters updated in last 1 hour)
    auto_generate_reports: bool = True
    report_generation_interval_hours: int = 1

user_config = UserConfig()