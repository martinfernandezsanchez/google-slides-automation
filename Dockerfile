FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY slides_automation.py .
COPY api_handler.py .
COPY logger.py .
COPY client.py .

# Create directory for credentials
RUN mkdir -p /app/credentials

# Set environment variables
ENV GOOGLE_CREDENTIALS_PATH=/app/credentials/credentials.json
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"] 