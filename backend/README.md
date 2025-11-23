# News Report Generator Service

## Description
AI-powered service for news aggregation and multi-format content generation.

## Setup

### Prerequisites
- Python 3.8+
- Virtual environment

### Installation
```bash
# Activate virtual environment
source venv/Scripts/activate  # Windows Git Bash

# Install dependencies
pip install -r requirements.txt
```

### Running the Service
```bash
cd services/news-report-generator
python main.py

# Service runs on http://localhost:8001
```

## API Endpoints

- **GET /** - Root endpoint
- **GET /health** - Health check
- **GET /docs** - Interactive API documentation (Swagger UI)
- **GET /api/v1/test** - Test endpoint
- **POST /api/v1/collect-news** - Collect news (coming soon)
- **POST /api/v1/generate-report** - Generate report (coming soon)

## Interactive Documentation

Visit http://localhost:8001/docs for full API documentation.

## Status
 Basic setup complete  
 News collection - Under development  
