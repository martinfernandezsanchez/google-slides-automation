"""
Google Slides Automation Service Client

A Python client library for interacting with the Google Slides Automation Service.
"""

import requests
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CreatePresentationResponse:
    """Response from creating a presentation."""
    presentation_id: str
    presentation_url: str
    batch_updates: int
    total_requests: int
    duration_seconds: float
    status: str


@dataclass
class HealthResponse:
    """Health check response."""
    status: str
    version: str
    uptime: float


class SlidesAutomationClient:
    """Client for the Google Slides Automation Service."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            base_url: The base URL of the service (e.g., https://slides-automation-service-xxx.run.app)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the service."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response
    
    def health_check(self) -> HealthResponse:
        """Check the health of the service."""
        response = self._make_request('GET', '/health')
        data = response.json()
        return HealthResponse(**data)
    
    def create_presentation(
        self,
        template_id: str,
        title: str,
        json_data: Dict[str, Any],
        credentials_path: Optional[str] = None
    ) -> CreatePresentationResponse:
        """
        Create a presentation from template and populate with JSON data.
        
        Args:
            template_id: Google Slides template ID
            title: Title for the new presentation
            json_data: JSON data to populate the presentation
            credentials_path: Optional path to credentials file
            
        Returns:
            CreatePresentationResponse with presentation details
        """
        payload = {
            'template_id': template_id,
            'title': title,
            'json_data': json_data
        }
        
        if credentials_path:
            payload['credentials_path'] = credentials_path
        
        response = self._make_request('POST', '/presentations/create', json=payload)
        data = response.json()
        return CreatePresentationResponse(**data)
    
    def get_presentation_info(self, presentation_id: str) -> Dict[str, Any]:
        """Get information about a specific presentation."""
        response = self._make_request('GET', f'/presentations/{presentation_id}/info')
        return response.json()
    
    def get_template_info(self, template_id: str) -> Dict[str, Any]:
        """Get information about a specific template."""
        response = self._make_request('GET', f'/templates/{template_id}/info')
        return response.json()
    
    def get_metrics(self) -> str:
        """Get Prometheus metrics from the service."""
        response = self._make_request('GET', '/metrics')
        return response.text
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information."""
        response = self._make_request('GET', '/')
        return response.json()


# Example usage
if __name__ == "__main__":
    # Example configuration
    SERVICE_URL = "https://slides-automation-service-xxx.run.app"  # Replace with your service URL
    API_KEY = None  # Add your API key if required
    
    # Initialize client
    client = SlidesAutomationClient(SERVICE_URL, API_KEY)
    
    # Check service health
    try:
        health = client.health_check()
        print(f"Service Status: {health.status}")
        print(f"Version: {health.version}")
        print(f"Uptime: {health.uptime:.2f} seconds")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Example: Create a presentation
    template_id = "1V8gBPnE4-ukMHv7rX3XNKfAI8p0rp7XhAnNXTv4xgL8"
    title = "Test Presentation"
    json_data = {
        "company_name": "Example Corp",
        "report_date": "2024-01-15",
        "quarter": "Q1",
        "total_revenue": "$1,000,000",
        "growth_rate": "15%",
        "employees": [
            {"name": "John Doe", "role": "CEO", "department": "Executive"},
            {"name": "Jane Smith", "role": "CTO", "department": "Technology"}
        ],
        "projects": [
            {"name": "Project A", "status": "In Progress", "budget": "$50,000"},
            {"name": "Project B", "status": "Completed", "budget": "$75,000"}
        ],
        "departments": [
            {"name": "Engineering", "head_count": 25, "budget": "$500,000"},
            {"name": "Marketing", "head_count": 15, "budget": "$300,000"}
        ]
    }
    
    try:
        result = client.create_presentation(template_id, title, json_data)
        print(f"\n✅ Presentation created successfully!")
        print(f"Presentation ID: {result.presentation_id}")
        print(f"Presentation URL: {result.presentation_url}")
        print(f"Batch Updates: {result.batch_updates}")
        print(f"Total Requests: {result.total_requests}")
        print(f"Duration: {result.duration_seconds:.2f} seconds")
    except Exception as e:
        print(f"❌ Failed to create presentation: {e}") 