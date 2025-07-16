# Google Slides Automation Service

A production-ready FastAPI service for automating Google Slides presentations with JSON data, featuring dynamic table population, slide duplication, and comprehensive monitoring.

## Features

- **Dynamic Table Population**: Automatically populates tables with JSON data
- **Slide Duplication**: Intelligently duplicates slides for large datasets
- **Batch Processing**: Optimized batch updates with 10MB payload limits
- **Comprehensive Monitoring**: Prometheus metrics, structured logging, and health checks
- **Docker Support**: Containerized deployment with Docker and Docker Compose
- **GCP Integration**: Cloud Build configuration for automated deployments
- **Python Client**: Easy-to-use client library for integration

## Architecture

```
├── app.py                 # FastAPI service with monitoring
├── slides_automation.py   # Core automation logic
├── api_handler.py         # Google Slides API wrapper
├── logger.py             # Structured logging
├── client.py             # Python client library
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Local development setup
├── cloudbuild.yaml       # GCP Cloud Build config
├── deploy.sh            # Deployment script
└── requirements.txt      # Python dependencies
```

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd google-slides-automation
   ```

2. **Set up credentials**
   ```bash
   # Place your Google service account credentials in credentials.json
   # or set GOOGLE_CREDENTIALS_PATH environment variable
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the service**
   ```bash
   python app.py
   ```

5. **Test with the client**
   ```python
   from client import GoogleSlidesClient
   
   client = GoogleSlidesClient("http://localhost:8000")
   
   # Create a presentation
   response = client.create_presentation(
       template_id="your_template_id",
       title="My Presentation",
       json_data={
           "employees": [...],
           "projects": [...],
           "departments": [...]
       }
   )
   print(f"Presentation created: {response['presentation_url']}")
   ```

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

2. **Or build manually**
   ```bash
   docker build -t google-slides-automation .
   docker run -p 8000:8000 google-slides-automation
   ```

### GCP Deployment

1. **Deploy to Google Cloud Run**
   ```bash
   ./deploy.sh
   ```

2. **Or use Cloud Build**
   ```bash
   gcloud builds submit --config cloudbuild.yaml .
   ```

## API Endpoints

### Create Presentation
```http
POST /presentations/create
Content-Type: application/json

{
  "template_id": "string",
  "title": "string", 
  "json_data": {
    "employees": [...],
    "projects": [...],
    "departments": [...]
  },
  "credentials_path": "optional"
}
```

### Health Check
```http
GET /health
```

### Metrics
```http
GET /metrics
```

### Service Info
```http
GET /
```

## Configuration

### Environment Variables

- `GOOGLE_CREDENTIALS_PATH`: Path to Google service account credentials (default: `credentials.json`)
- `LOG_LEVEL`: Logging level (default: `INFO`)
- `PORT`: Service port (default: `8000`)

### Google Slides Template Requirements

Your Google Slides template should include:

1. **Array Markers**: Place `{{employees}}`, `{{projects}}`, `{{departments}}` in text boxes where you want tables
2. **Table Structure**: Include at least one row in each table for proper formatting
3. **Permissions**: Ensure the service account has edit access to the template

## Monitoring

### Prometheus Metrics

- `slides_automation_requests_total`: Total API requests by endpoint and status
- `slides_automation_request_duration_seconds`: Request duration by endpoint
- `slides_automation_batch_updates_total`: Batch updates by operation type
- `slides_automation_presentations_created_total`: Total presentations created

### Logging

Structured logging with operation context and performance metrics:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "operation": "API Create Presentation",
  "template_id": "1ABC...",
  "batch_updates": 3,
  "total_requests": 15,
  "duration_seconds": 2.5
}
```

## Performance Optimizations

- **Batch Updates**: Combines multiple API requests into single batches
- **Payload Size Limits**: Automatically splits large batches to stay under 10MB
- **Slide Index Management**: Efficiently handles slide duplication and reindexing
- **Memory Management**: Optimized for large datasets

## Security

- **Credential Management**: Secure handling of Google service account credentials
- **Input Validation**: Comprehensive request validation with Pydantic
- **Error Handling**: Graceful error handling without exposing sensitive information
- **CORS Configuration**: Configurable CORS settings for production

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Quality
```bash
# Install linting tools
pip install black flake8 mypy

# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .
```

## Troubleshooting

### Common Issues

1. **Missing Credentials**: Ensure `credentials.json` is present and has correct permissions
2. **Template Access**: Verify the service account has edit access to the template
3. **Large Datasets**: The service automatically handles large datasets with slide duplication
4. **API Limits**: Batch processing helps stay within Google Slides API limits

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python app.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Open an issue on GitHub 