"""
Google Slides Automation Service

A FastAPI service that provides Google Slides automation capabilities
with centralized management and comprehensive monitoring.
"""

import os
import time
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# Import our existing modules
from slides_automation import GoogleSlidesAutomation
from logger import get_logger

# Prometheus metrics
REQUEST_COUNT = Counter('slides_automation_requests_total', 'Total requests', ['endpoint', 'status'])
REQUEST_DURATION = Histogram('slides_automation_request_duration_seconds', 'Request duration', ['endpoint'])
BATCH_UPDATE_COUNT = Counter('slides_automation_batch_updates_total', 'Total batch updates', ['operation_type'])
PRESENTATION_CREATED = Counter('slides_automation_presentations_created_total', 'Presentations created')

# Global variables
automation_service: Optional[GoogleSlidesAutomation] = None
logger = get_logger()

class CreatePresentationRequest(BaseModel):
    template_id: str = Field(..., description="Google Slides template ID")
    title: str = Field(..., description="Title for the new presentation")
    json_data: Dict[str, Any] = Field(..., description="JSON data to populate the presentation")
    credentials_path: Optional[str] = Field("credentials.json", description="Path to credentials file")

class CreatePresentationResponse(BaseModel):
    presentation_id: str
    presentation_url: str
    batch_updates: int
    total_requests: int
    duration_seconds: float
    status: str = "success"

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime: float

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown."""
    global automation_service
    
    # Startup
    logger.info("Starting Google Slides Automation Service")
    start_time = time.time()
    
    # Initialize the automation service
    try:
        credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        automation_service = GoogleSlidesAutomation(credentials_path)
        logger.info("Google Slides Automation Service initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize automation service", error=e)
        raise
    
    # Store startup time for health checks
    app.state.start_time = start_time
    
    yield
    
    # Shutdown
    logger.info("Shutting down Google Slides Automation Service")

# Create FastAPI app
app = FastAPI(
    title="Google Slides Automation Service",
    description="A service for automating Google Slides presentations with JSON data",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def monitor_requests(request: Request, call_next):
    """Middleware to monitor requests and collect metrics."""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Record metrics
    endpoint = request.url.path
    status = response.status_code
    REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
    REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
    
    # Add custom headers for monitoring
    response.headers["X-Request-Duration"] = str(duration)
    
    return response

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - app.state.start_time
    return HealthResponse(
        status="healthy" if automation_service else "unhealthy",
        version="1.0.0",
        uptime=uptime
    )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/presentations/create", response_model=CreatePresentationResponse)
async def create_presentation(request: CreatePresentationRequest):
    """
    Create a presentation from template and populate with JSON data.
    
    This endpoint:
    1. Copies the specified template
    2. Populates it with the provided JSON data
    3. Returns the new presentation ID and URL
    """
    if not automation_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    start_time = time.time()
    
    try:
        with logger.operation_context("API Create Presentation", {
            'template_id': request.template_id,
            'title': request.title,
            'data_keys': list(request.json_data.keys()) if request.json_data else []
        }):
            # Create the presentation
            presentation_id = automation_service.create_presentation_from_template(
                template_id=request.template_id,
                json_data=request.json_data,
                title=request.title
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Get batch update statistics
            stats = automation_service.batch_update_stats
            
            # Record metrics
            PRESENTATION_CREATED.inc()
            for op_type, count in stats['operations_by_type'].items():
                BATCH_UPDATE_COUNT.labels(operation_type=op_type).inc(count)
            
            # Create response
            presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            
            response = CreatePresentationResponse(
                presentation_id=presentation_id,
                presentation_url=presentation_url,
                batch_updates=stats['total_batches'],
                total_requests=stats['total_requests'],
                duration_seconds=duration
            )
            
            logger.log_success("Presentation created successfully via API", {
                'presentation_id': presentation_id,
                'batch_updates': stats['total_batches'],
                'total_requests': stats['total_requests'],
                'duration_seconds': duration
            })
            
            return response
            
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error("Failed to create presentation via API", e, {
            'template_id': request.template_id,
            'title': request.title,
            'duration_seconds': duration
        })
        raise HTTPException(status_code=500, detail=f"Failed to create presentation: {str(e)}")

@app.get("/presentations/{presentation_id}/info")
async def get_presentation_info(presentation_id: str):
    """Get information about a specific presentation."""
    if not automation_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        presentation = automation_service.api_handler.get_presentation(presentation_id)
        
        return {
            "presentation_id": presentation_id,
            "title": presentation.get('title', 'Unknown'),
            "slide_count": len(presentation.get('slides', [])),
            "presentation_url": f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        }
    except Exception as e:
        logger.log_error("Failed to get presentation info", e, {'presentation_id': presentation_id})
        raise HTTPException(status_code=404, detail=f"Presentation not found or access denied: {str(e)}")

@app.get("/templates/{template_id}/info")
async def get_template_info(template_id: str):
    """Get information about a specific template."""
    if not automation_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        presentation = automation_service.api_handler.get_presentation(template_id)
        
        return {
            "template_id": template_id,
            "title": presentation.get('title', 'Unknown'),
            "slide_count": len(presentation.get('slides', [])),
            "template_url": f"https://docs.google.com/presentation/d/{template_id}/edit"
        }
    except Exception as e:
        logger.log_error("Failed to get template info", e, {'template_id': template_id})
        raise HTTPException(status_code=404, detail=f"Template not found or access denied: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Google Slides Automation Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "create_presentation": "/presentations/create",
            "presentation_info": "/presentations/{presentation_id}/info",
            "template_info": "/templates/{template_id}/info"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 