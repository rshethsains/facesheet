# Base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies for playwright
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    unzip \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm-dev \
    libpango-1.0-0 \
    libcairo2 \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements.txt from the root directory into the container
COPY ../requirements.txt /app/

RUN pip install --no-cache-dir -r /app/requirements.txt

# Install playwright browsers
RUN python -m playwright install --with-deps

# Copy application code from the app directory into the container
COPY ../app /app/

# Expose port for the Flask app
EXPOSE 8080

# Set the command to use the entrypoint script
CMD ["python", "app.py"]