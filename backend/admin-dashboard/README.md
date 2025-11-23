# Admin Dashboard (Django)

## Description
Django-based admin panel for managing users, news sources, articles, and generated reports for the AI Media Center.

## Features
-  User management with roles (Admin, Editor, Viewer)
-  News source configuration
-  Article management
-  Generated report tracking
-  RESTful API with Django REST Framework
-  Swagger/ReDoc API documentation
-  CORS enabled for microservices

## Setup

### Installation
```bash
# Navigate to admin dashboard
cd admin-dashboard

# Activate virtual environment
source ../venv/Scripts/activate  # Windows Git Bash

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
python manage.py runserver 8000
```

## Access Points

- **Admin Panel**: http://localhost:8000/admin
- **API Root**: http://localhost:8000/api/v1/
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/

## API Endpoints

### Users
- `GET/POST` /api/v1/users/
- `GET/PUT/DELETE` /api/v1/users/{id}/

### News Sources
- `GET/POST` /api/v1/news-sources/
- `GET/PUT/DELETE` /api/v1/news-sources/{id}/

### Articles
- `GET/POST` /api/v1/articles/
- `GET/PUT/DELETE` /api/v1/articles/{id}/
- `GET` /api/v1/articles/recent/ (Last 10 articles)

### Generated Reports
- `GET/POST` /api/v1/reports/
- `GET/PUT/DELETE` /api/v1/reports/{id}/

## Models

### User (Custom)
- username, email, password
- role: admin, editor, viewer
- phone, is_active
- timestamps

### NewsSource
- name, url, api_key
- source_type: rss, api, web
- is_active, created_at

### Article
- title, content, summary
- source (FK), author
- published_at, url, image_url
- category, language, sentiment
- created_by (FK), timestamps

### GeneratedReport
- article (FK), format_type
- content, metadata
- created_by (FK), created_at

## Database Schema

Currently using SQLite for development.

For production, migrate to PostgreSQL:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ai_media_center',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Authentication

- Session-based authentication for admin panel
- Token/JWT authentication (to be implemented)

## Status
 Setup complete
 Models created
 Admin panel configured
 REST API functional
 API documentation ready

## Next Steps
- [ ] Implement JWT authentication
- [ ] Add pagination and filtering
- [ ] Connect to FastAPI services
- [ ] Migrate to PostgreSQL
- [ ] Add unit tests