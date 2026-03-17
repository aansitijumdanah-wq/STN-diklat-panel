# Dockerfile for STN Diklat Panel

FROM python:3.11-slim

# Set environment variables untuk optimization
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PYTHONOPTIMIZE=2
ENV PIP_NO_CACHE_DIR=1

# Set work directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies (with verbose output for debugging)
COPY requirements.txt .
RUN pip install -v -r requirements.txt --no-cache-dir || \
    (echo "First install attempt failed, trying with pre-built wheels..." && \
     pip install --only-binary :all: --no-cache-dir -r requirements.txt || \
     pip install --no-build-isolation -r requirements.txt)

# Copy project
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Create necessary directories
RUN mkdir -p database instance/uploads instance/cache

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Run the application dengan optimized gunicorn settings
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--worker-class", "gthread", "--timeout", "120", "--access-logfile", "-", "wsgi:application"]