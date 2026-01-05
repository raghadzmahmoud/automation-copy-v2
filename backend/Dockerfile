# 🚀 Dockerfile for Render with Playwright Support
FROM mcr.microsoft.com/playwright/python:v1.41.2-jammy

# Set working directory
WORKDIR /app

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables optimized for Render
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PORT=8000

# Create necessary directories
RUN mkdir -p /app/app/logs
RUN mkdir -p /app/fonts

# Set proper permissions
RUN chmod -R 755 /app

# Expose port for Render
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "print('Health check passed')" || exit 1

# Run the worker
CMD ["python", "start_worker.py"]