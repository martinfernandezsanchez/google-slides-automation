"""
Google Slides Automation Service

A FastAPI service that provides Google Slides automation capabilities
with centralized management and comprehensive monitoring.
"""

import os
import time
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.security import OAuth2PasswordBearer
from google.oauth2.credentials import Credentials as UserCredentials
from google.auth.exceptions import RefreshError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our existing modules
from slides_automation import GoogleSlidesAutomation
from logger import get_logger

# Global variables
automation_service: Optional[GoogleSlidesAutomation] = None
logger = get_logger()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class CreatePresentationRequest(BaseModel):
    template_id: str = Field(..., description="Google Slides template ID")
    title: str = Field(..., description="Title for the new presentation")
    json_data: Dict[str, Any] = Field(..., description="JSON data to populate the presentation")
    credentials_path: Optional[str] = Field("credentials.json", description="Path to credentials file")
    drive_folder_url: Optional[str] = Field(None, description="Google Drive folder URL to save the presentation in")

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

def get_user_credentials(authorization: Optional[str] = Header(None, description="Authorization header with Bearer token")) -> UserCredentials:
    """Create user credentials object from the Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Please provide: Authorization: Bearer <your_access_token>"
        )
    
    # Parse Bearer token from Authorization header
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use Bearer token format: Authorization: Bearer <your_access_token>"
        )
    
    access_token = authorization[7:]  # Remove "Bearer " prefix
    
    if not access_token or len(access_token) < 20:  # Basic sanity check
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired access token provided in Authorization header."
        )
    
    try:
        # This creates a credentials object from the user's access token.
        credentials = UserCredentials(token=access_token)
        return credentials
    except Exception as e:
        logger.log_error("Failed to create credentials from Authorization header", e)
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials from Authorization header",
        )

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
        logger.warning(f"Failed to initialize automation service: {e}")
        logger.warning("Service will start but presentation creation will not work until credentials are available")
        automation_service = None
    
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
    
    # Add custom headers for monitoring
    response.headers["X-Request-Duration"] = str(duration)
    
    return response

# GET /health
# Returns the health status of the service.
# - Response:
#   {
#     "status": "healthy" | "unhealthy",
#     "version": "1.0.0",
#     "uptime": 1234.56
#   }
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = time.time() - app.state.start_time
    return HealthResponse(
        status="healthy" if automation_service else "unhealthy",
        version="1.0.0",
        uptime=uptime
    )

# POST /presentations/create
# Creates a new presentation from a template and populates it with JSON data.
# - Request Body:
#   {
#     "template_id": "your_google_slides_template_id",
#     "title": "New Presentation Title",
#     "json_data": { "key": "value", "items": [...] },
#     "drive_folder_url": "https://... or null"
#   }
# - Response:
#   {
#     "presentation_id": "new_presentation_id",
#     "presentation_url": "https://...",
#     "batch_updates": 5,
#     "total_requests": 150,
#     "duration_seconds": 15.2,
#     "status": "success"
#   }
@app.post("/presentations/create", response_model=CreatePresentationResponse)
async def create_presentation(
    request: CreatePresentationRequest,
    user_credentials: UserCredentials = Depends(get_user_credentials)
):
    """
    Create a presentation from template and populate with JSON data.
    
    This endpoint:
    1. Copies the specified template
    2. Populates it with the provided JSON data
    3. Returns the new presentation ID and URL
    """
    start_time = time.time()
    
    try:
        # Initialize the automation service with user's credentials for this request
        automation_service = GoogleSlidesAutomation(user_credentials=user_credentials)

        with logger.operation_context("API Create Presentation", {
            'template_id': request.template_id,
            'title': request.title,
            'data_keys': list(request.json_data.keys()) if request.json_data else []
        }):
            # Create the presentation
            presentation_id = automation_service.create_presentation_from_template(
                template_id=request.template_id,
                json_data=request.json_data,
                title=request.title,
                drive_folder_url=request.drive_folder_url
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Get batch update statistics
            stats = automation_service.batch_update_stats
            
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
            
    except RefreshError as e:
        logger.log_error("Token refresh error during presentation creation", e, {
            'template_id': request.template_id,
            'title': request.title,
        })
        raise HTTPException(status_code=401, detail=f"Authentication token is invalid or expired: {e}")
    except Exception as e:
        duration = time.time() - start_time
        logger.log_error("Failed to create presentation via API", e, {
            'template_id': request.template_id,
            'title': request.title,
            'duration_seconds': duration
        })
        raise HTTPException(status_code=500, detail=f"Failed to create presentation: {str(e)}")

# GET /
# Returns basic information about the service and available endpoints.
# - Response:
#   {
#     "service": "Google Slides Automation Service",
#     "version": "1.0.0",
#     "status": "running",
#     "endpoints": {
#       "health": "/health",
#       "create_presentation": "/presentations/create"
#     }
#   }
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Google Slides Automation Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "create_presentation": "/presentations/create"
        }
    }

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    
    # Add startup logging
    print("🚀 Starting Google Slides Automation Service")
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Environment variables: {dict(os.environ)}")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 