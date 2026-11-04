# ==============================================================================
# AUTOMA PRODUCTION DOCKERFILE
# Uses official Microsoft Playwright image with pre-installed Chromium & system deps
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install system dependencies for cairosvg (SVG→PNG card rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libcairo2-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create runtime directories
RUN mkdir -p data content/media content/published content/rejected content/queue logs

# Copy application source
COPY . .

# Default port
ENV PORT=8080
EXPOSE 8080

# Start Gunicorn WSGI server bound to Render's dynamic $PORT
CMD ["sh", "-c", "gunicorn automa.web.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120"]

