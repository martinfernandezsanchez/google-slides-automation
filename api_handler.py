"""
Google Slides API Handler

This module provides a clean interface for Google Slides API operations,
managing resources efficiently and providing better error handling.
"""

import os
import re
import json
from typing import Dict, List, Any, Optional
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from logger import get_logger
from google.oauth2.service_account import Credentials


class GoogleSlidesAPIHandler:
    """Handles Google Slides API operations with better resource management."""
    
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = [
        'https://www.googleapis.com/auth/presentations',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str = 'credentials.json', user_credentials: Optional[UserCredentials] = None):
        """
        Initialize the Google Slides API handler.
        
        Args:
            credentials_path: Path to the Google API credentials JSON file
            user_credentials: Optional user credentials to use for authentication
        """
        self.credentials_path = credentials_path
        self.user_credentials = user_credentials
        self.slides_service = None
        self.drive_service = None
        self.logger = get_logger()
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google API using service account or user credentials."""
        with self.logger.operation_context("Google API Authentication", {
            'credentials_path': self.credentials_path,
            'has_user_credentials': bool(self.user_credentials)
        }):
            try:
                creds = None
                if self.user_credentials:
                    self.logger.log_info("Using user-provided credentials")
                    creds = self.user_credentials
                # Try to load service account credentials from file
                elif os.path.exists(self.credentials_path):
                    self.logger.log_info(f"Loading service account credentials from {self.credentials_path}")
                    with open(self.credentials_path, 'r') as f:
                        service_account_info = json.load(f)
                    
                    from google.oauth2 import service_account
                    creds = service_account.Credentials.from_service_account_info(
                        service_account_info, scopes=self.SCOPES
                    )
                else:
                    # Fall back to default credentials (useful for Cloud Run)
                    self.logger.log_info("Using default credentials")
                    creds, project = default(scopes=self.SCOPES)
                
                if not creds:
                    raise Exception("Authentication failed: No valid credentials found.")

                # Initialize services
                self.logger.log_debug("Initializing Google API services")
                self.slides_service = build('slides', 'v1', credentials=creds)
                self.drive_service = build('drive', 'v3', credentials=creds)
                
                self.logger.log_success("Google API services initialized successfully")
                
            except Exception as e:
                self.logger.log_error("Failed to authenticate with Google API", e)
                raise
    
    def copy_presentation(self, template_id: str, title: str) -> str:
        """
        Copy a Google Slides template to create a new presentation.
        
        Args:
            template_id: The ID of the template presentation
            title: Title for the new presentation
            
        Returns:
            The ID of the newly created presentation
            
        Raises:
            HttpError: If the API request fails
        """
        with self.logger.operation_context("Copy Presentation", {
            'template_id': template_id,
            'title': title
        }):
            try:
                copy_request = {'name': title}
                self.logger.log_api_call("Drive API: Copy file", {
                    'template_id': template_id,
                    'title': title
                })
                
                copied_file = self.drive_service.files().copy(
                    fileId=template_id,
                    body=copy_request
                ).execute()
                
                new_presentation_id = copied_file['id']
                self.logger.log_success("Presentation copied successfully", {
                    'new_presentation_id': new_presentation_id
                })
                
                return new_presentation_id
                
            except HttpError as error:
                self.logger.log_error("Failed to copy presentation", error, {
                    'template_id': template_id,
                    'title': title
                })
                raise error
    
    def create_presentation(self, title: str) -> str:
        """
        Create a new empty Google Slides presentation.
        
        Args:
            title: Title for the new presentation
            
        Returns:
            The ID of the newly created presentation
            
        Raises:
            HttpError: If the API request fails
        """
        with self.logger.operation_context("Create Presentation", {
            'title': title
        }):
            try:
                self.logger.log_api_call("Slides API: Create presentation", {
                    'title': title
                })
                
                presentation = self.slides_service.presentations().create(
                    body={'title': title}
                ).execute()
                
                presentation_id = presentation['presentationId']
                self.logger.log_success("Presentation created successfully", {
                    'presentation_id': presentation_id
                })
                
                return presentation_id
                
            except HttpError as error:
                self.logger.log_error("Failed to create presentation", error, {
                    'title': title
                })
                raise error
    
    def get_presentation(self, presentation_id: str) -> Dict[str, Any]:
        """
        Get a presentation by ID.
        
        Args:
            presentation_id: The ID of the presentation
            
        Returns:
            The presentation data
            
        Raises:
            HttpError: If the API request fails
        """
        with self.logger.operation_context("Get Presentation", {
            'presentation_id': presentation_id
        }):
            try:
                self.logger.log_api_call("Slides API: Get presentation", {
                    'presentation_id': presentation_id
                })
                
                presentation = self.slides_service.presentations().get(
                    presentationId=presentation_id
                ).execute()
                
                slide_count = len(presentation.get('slides', []))
                self.logger.log_success("Presentation retrieved successfully", {
                    'slide_count': slide_count
                })
                
                return presentation
                
            except HttpError as error:
                self.logger.log_error("Failed to get presentation", error, {
                    'presentation_id': presentation_id
                })
                raise error
    
    def batch_update(self, presentation_id: str, requests: List[Dict[str, Any]], stats_callback=None) -> None:
        """
        Execute a batch update on a presentation.
        
        Args:
            presentation_id: The ID of the presentation
            requests: List of update requests
            
        Raises:
            HttpError: If the API request fails
            ValueError: If the payload size exceeds 10MB limit
        """
        if not requests:
            self.logger.log_debug("Skipping empty batch update")
            return
        
        # Check payload size before executing
        payload_size = self._calculate_payload_size(requests)
        max_size_bytes = 10 * 1024 * 1024  # 10MB in bytes
        
        if payload_size > max_size_bytes:
            error_msg = f"Batch update payload size ({payload_size:,} bytes) exceeds 10MB limit ({max_size_bytes:,} bytes). Consider splitting the batch into smaller chunks."
            self.logger.log_error("Payload size limit exceeded", ValueError(error_msg), {
                'payload_size_bytes': payload_size,
                'max_size_bytes': max_size_bytes,
                'request_count': len(requests)
            })
            raise ValueError(error_msg)
            
        with self.logger.operation_context("Batch Update", {
            'presentation_id': presentation_id,
            'request_count': len(requests),
            'payload_size_bytes': payload_size
        }):
            try:
                # Log request types for debugging
                request_types = {}
                for req in requests:
                    req_type = list(req.keys())[0] if req else 'unknown'
                    request_types[req_type] = request_types.get(req_type, 0) + 1
                
                self.logger.log_batch_update(len(requests), {
                    'request_types': request_types,
                    'payload_size_bytes': payload_size
                })
                
                self.logger.log_api_call("Slides API: Batch update", {
                    'presentation_id': presentation_id,
                    'request_count': len(requests),
                    'request_types': request_types,
                    'payload_size_bytes': payload_size
                })
                
                self.slides_service.presentations().batchUpdate(
                    presentationId=presentation_id,
                    body={'requests': requests}
                ).execute()
                
                if stats_callback:
                    stats_callback(requests)
                    
            except HttpError as error:
                self.logger.log_error("Failed to execute batch update", error, {
                    'presentation_id': presentation_id,
                    'request_count': len(requests)
                })
                raise error

    def _calculate_payload_size(self, requests: List[Dict[str, Any]]) -> int:
        """Calculate the JSON payload size of a list of requests."""
        try:
            return len(json.dumps({'requests': requests}).encode('utf-8'))
        except (TypeError, OverflowError) as e:
            self.logger.log_warning(f"Could not calculate payload size: {e}")
            return 0
    
    def batch_update_with_size_check(self, presentation_id: str, requests: List[Dict[str, Any]], 
                                   max_size_bytes: int = 10 * 1024 * 1024, operation_description: str = "Unknown operation",
                                   stats_callback=None) -> None:
        """
        Execute batch update and automatically split into chunks if payload exceeds size limit.
        
        Args:
            presentation_id: The ID of the presentation
            requests: List of update requests
            max_size_bytes: Maximum payload size for a single batch
            operation_description: Description of the operation for tracking purposes
            stats_callback: Optional callback function for tracking batch statistics
        """
        if not requests:
            self.logger.log_debug("Skipping empty batch update")
            return
            
        chunks = self._split_requests_into_chunks(requests, max_size_bytes)
        
        with self.logger.operation_context("Batch Update with Size Check", {
            'presentation_id': presentation_id,
            'total_requests': len(requests),
            'chunk_count': len(chunks),
            'operation_description': operation_description
        }):
            for i, chunk in enumerate(chunks):
                chunk_size = self._calculate_payload_size(chunk)
                self.logger.log_info(f"Executing chunk {i+1}/{len(chunks)} with {len(chunk)} requests ({chunk_size:,} bytes)")
                
                # Call stats callback if provided
                if stats_callback:
                    stats_callback(chunk, f"{operation_description} (chunk {i+1}/{len(chunks)})")
                
                self.batch_update(presentation_id, chunk)

    def _split_requests_into_chunks(self, requests: List[Dict[str, Any]], 
                                  max_size_bytes: int) -> List[List[Dict[str, Any]]]:
        """
        Split a list of requests into smaller chunks that are under the size limit.
        
        Args:
            requests: The original list of requests
            max_size_bytes: The maximum size for each chunk
            
        Returns:
            A list of request chunks
        """
        if not requests:
            return []
            
        # If the total size is already under the limit, no need to split
        total_size = self._calculate_payload_size(requests)
        if total_size <= max_size_bytes:
            return [requests]
            
        chunks = []
        current_chunk = []
        current_size = 0
        
        for request in requests:
            request_size = self._calculate_payload_size([request])
            
            if current_size + request_size > max_size_bytes and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
                
            current_chunk.append(request)
            current_size += request_size
            
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    def find_tables_with_array_markers(self, presentation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find all tables with array markers (e.g., {{my_array}})."""
        tables_with_markers = []
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'table' in element:
                    array_key = self._find_array_marker_in_table(element['table'])
                    if array_key:
                        tables_with_markers.append({
                            'slide_id': slide['objectId'],
                            'table_id': element['objectId'],
                            'array_key': array_key,
                            'table_info': element['table']
                        })
                        self.logger.log_discovery("Found table with array marker", {
                            'slide_id': slide['objectId'],
                            'table_id': element['objectId'],
                            'array_key': array_key
                        })
        return tables_with_markers

    def _find_array_marker_in_table(self, table: Dict[str, Any]) -> Optional[str]:
        """Find an array marker like {{my_array}} in any cell of a table."""
        for row in table.get('tableRows', []):
            for cell in row.get('tableCells', []):
                for element in cell.get('text', {}).get('textElements', []):
                    content = element.get('textRun', {}).get('content', '')
                    match = re.search(r'\{\{(\w+)\}\}', content)
                    if match:
                        return match.group(1)
        return None

    def get_table_headers(self, table: Dict[str, Any]) -> List[str]:
        """Extract the headers from the first row of a table."""
        headers = []
        if table.get('tableRows'):
            header_row = table['tableRows'][0]
            for cell in header_row.get('tableCells', []):
                header_text = ""
                for element in cell.get('text', {}).get('textElements', []):
                    header_text += element.get('textRun', {}).get('content', '')
                headers.append(header_text.strip())
        return headers

    def create_table_row_request(self, table_id: str, row_index: int, cell_values: list) -> dict:
        """Create a request to insert a new row into a table."""
        return {
            'insertTableRows': {
                'tableObjectId': table_id,
                'cellLocation': {
                    'rowIndex': row_index,
                    'columnIndex': 0
                },
                'insertBelow': True,
                'number': 1
            }
        }

    def create_duplicate_slide_request(self, slide_id: str) -> Dict[str, Any]:
        """Create a request to duplicate a slide."""
        self.logger.log_slide_operation(slide_id, "Creating duplicate request")
        return {
            'duplicateObject': {
                'objectId': slide_id,
            }
        }

    def create_delete_slide_request(self, slide_id: str) -> Dict[str, Any]:
        """Create a request to delete a slide."""
        self.logger.log_slide_operation(slide_id, "Creating delete request")
        return {
            'deleteObject': {
                'objectId': slide_id
            }
        }

    def create_replace_text_request(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """
        Create a request to replace all occurrences of text in a presentation.
        
        Args:
            old_text: The text to replace
            new_text: The text to replace it with
            
        Returns:
            A dictionary representing the replaceAllText request
        """
        self.logger.log_info("Creating text replacement request", {
            'old_text': old_text,
            'new_text': new_text
        })
        return {
            'replaceAllText': {
                'containsText': {'text': old_text, 'matchCase': False},
                'pageObjectIds': [],
                'replaceText': new_text
            }
        }

    def create_update_table_cell_request(self, table_id: str, row_index: int, column_index: int, text: str) -> Dict[str, Any]:
        """
        Create a request to update the text in a table cell.
        
        Args:
            table_id: ID of the table
            row_index: Row index of the cell
            column_index: Column index of the cell
            text: The new text to insert
            
        Returns:
            A dictionary representing the API request
        """
        return self.create_update_table_cell_text_request(table_id, row_index, column_index, text)
        
    def create_update_table_cell_text_request(self, table_id: str, row_index: int, column_index: int, text: str) -> Dict[str, Any]:
        """
        Create a request to update the text in a table cell.
        This is a more specific version to handle text replacement.
        
        Args:
            table_id: ID of the table
            row_index: Row index of the cell
            column_index: Column index of the cell
            text: The new text to insert
            
        Returns:
            A dictionary representing the API request
        """
        return {
            'insertText': {
                'objectId': table_id,
                'cellLocation': {
                    'rowIndex': row_index,
                    'columnIndex': column_index
                },
                'text': text,
                'insertionIndex': 0
            }
        }

    def get_shape_ids_for_slide(self, presentation: Dict[str, Any], slide_object_id: str) -> dict:
        """Get the title and subtitle shape IDs for a given slide."""
        shape_ids = {'title': None, 'subtitle': None}
        for slide in presentation.get('slides', []):
            if slide['objectId'] == slide_object_id:
                for element in slide.get('pageElements', []):
                    if element.get('shape', {}).get('placeholder', {}).get('type') == 'TITLE':
                        shape_ids['title'] = element['objectId']
                    elif element.get('shape', {}).get('placeholder', {}).get('type') == 'SUBTITLE':
                        shape_ids['subtitle'] = element['objectId']
        return shape_ids
    
    def move_presentation_to_folder(self, presentation_id: str, folder_url: str):
        """
        Move a presentation to a specific Google Drive folder.
        
        Args:
            presentation_id: The ID of the presentation to move
            folder_url: The URL of the Google Drive folder
        """
        try:
            folder_id = self._extract_folder_id_from_url(folder_url)
            self.logger.log_info(f"Moving presentation {presentation_id} to folder {folder_id}")
            
            # Get the file to move
            file = self.drive_service.files().get(fileId=presentation_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            
            # Move the file
            self.drive_service.files().update(
                fileId=presentation_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            self.logger.log_success(f"Successfully moved presentation {presentation_id} to folder {folder_id}")
            
        except Exception as e:
            self.logger.log_error(f"Failed to move presentation {presentation_id} to folder {folder_url}", e)
            # We don't re-raise the exception because moving the file is not a critical failure
            
    def _extract_folder_id_from_url(self, folder_url: str) -> str:
        """Extract folder ID from Google Drive folder URL."""
        match = re.search(r'/folders/([a-zA-Z0-9_-]+)', folder_url)
        if match:
            return match.group(1)
        
        match = re.search(r'id=([a-zA-Z0-9_-]+)', folder_url)
        if match:
            return match.group(1)
            
        raise ValueError("Invalid Google Drive folder URL") 