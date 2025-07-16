"""
Google Slides API Handler

This module provides a clean interface for Google Slides API operations,
managing resources efficiently and providing better error handling.
"""

import os
import re
from typing import Dict, List, Any, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle
from logger import get_logger


class GoogleSlidesAPIHandler:
    """Handles Google Slides API operations with better resource management."""
    
    # If modifying these scopes, delete the file token.pickle.
    SCOPES = [
        'https://www.googleapis.com/auth/presentations',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str = 'credentials.json'):
        """
        Initialize the Google Slides API handler.
        
        Args:
            credentials_path: Path to the Google API credentials JSON file
        """
        self.credentials_path = credentials_path
        self.slides_service = None
        self.drive_service = None
        self.logger = get_logger()
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google API using OAuth2."""
        with self.logger.operation_context("Google API Authentication", {
            'credentials_path': self.credentials_path
        }):
            creds = None
            
            # The file token.pickle stores the user's access and refresh tokens.
            if os.path.exists('token.pickle'):
                self.logger.log_debug("Loading existing token from token.pickle")
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in.
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    self.logger.log_info("Refreshing expired token")
                    creds.refresh(Request())
                else:
                    self.logger.log_info("Starting OAuth2 flow for new authentication")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                self.logger.log_debug("Saving token to token.pickle")
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            # Initialize services
            self.logger.log_debug("Initializing Google API services")
            self.slides_service = build('slides', 'v1', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            self.logger.log_success("Google API services initialized successfully")
    
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
                
                self.logger.log_success("Batch update executed successfully", {
                    'request_count': len(requests),
                    'payload_size_bytes': payload_size
                })
                
                # Track batch update statistics
                if stats_callback:
                    stats_callback(requests)
                
            except HttpError as error:
                self.logger.log_error("Failed to execute batch update", error, {
                    'presentation_id': presentation_id,
                    'request_count': len(requests),
                    'payload_size_bytes': payload_size
                })
                # Re-raise the original error instead of creating a new one
                raise
    
    def _calculate_payload_size(self, requests: List[Dict[str, Any]]) -> int:
        """
        Calculate the size of the batch update payload in bytes.
        
        Args:
            requests: List of update requests
            
        Returns:
            Size of the payload in bytes
        """
        import json
        
        # Create the full payload structure
        payload = {
            'requests': requests
        }
        
        # Convert to JSON string and calculate size
        json_string = json.dumps(payload, separators=(',', ':'))
        return len(json_string.encode('utf-8'))
    
    def batch_update_with_size_check(self, presentation_id: str, requests: List[Dict[str, Any]], 
                                   max_size_bytes: int = 10 * 1024 * 1024) -> None:
        """
        Execute a batch update with automatic size checking and chunking.
        
        Args:
            presentation_id: The ID of the presentation
            requests: List of update requests
            max_size_bytes: Maximum payload size in bytes (default: 10MB)
            
        Raises:
            HttpError: If the API request fails
            ValueError: If individual request exceeds size limit
        """
        if not requests:
            self.logger.log_debug("Skipping empty batch update")
            return
        
        # Check if we need to split the batch
        payload_size = self._calculate_payload_size(requests)
        
        if payload_size <= max_size_bytes:
            # Single batch is fine
            self.batch_update(presentation_id, requests)
        else:
            # Need to split into chunks
            self.logger.log_info(f"Payload size ({payload_size:,} bytes) exceeds limit ({max_size_bytes:,} bytes). Splitting into chunks.")
            
            chunks = self._split_requests_into_chunks(requests, max_size_bytes)
            
            for i, chunk in enumerate(chunks):
                chunk_size = self._calculate_payload_size(chunk)
                self.logger.log_info(f"Executing chunk {i+1}/{len(chunks)} with {len(chunk)} requests ({chunk_size:,} bytes)")
                self.batch_update(presentation_id, chunk)
    
    def _split_requests_into_chunks(self, requests: List[Dict[str, Any]], 
                                  max_size_bytes: int) -> List[List[Dict[str, Any]]]:
        """
        Split requests into chunks that fit within the size limit.
        
        Args:
            requests: List of update requests
            max_size_bytes: Maximum payload size in bytes
            
        Returns:
            List of request chunks
        """
        chunks = []
        current_chunk = []
        current_size = 0
        
        for request in requests:
            # Calculate size of this single request
            single_request_size = self._calculate_payload_size([request])
            
            # If adding this request would exceed the limit, start a new chunk
            if current_size + single_request_size > max_size_bytes and current_chunk:
                chunks.append(current_chunk)
                current_chunk = [request]
                current_size = single_request_size
            else:
                current_chunk.append(request)
                current_size = self._calculate_payload_size(current_chunk)
        
        # Add the last chunk if it has requests
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _track_batch_update_stats(self, requests: List[Dict[str, Any]]) -> None:
        """
        Track batch update statistics for reporting.
        
        Args:
            requests: List of update requests
        """
        # This method will be called by the automation class to track stats
        pass
    
    def find_tables_with_array_markers(self, presentation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find all tables in the presentation that have array markers.
        
        Args:
            presentation: The presentation data
            
        Returns:
            List of tables with their array markers and slide information
        """
        tables_with_markers = []
        
        for slide_index, slide in enumerate(presentation.get('slides', [])):
            slide_id = slide['objectId']
            
            for element in slide.get('pageElements', []):
                if 'table' in element:
                    table = element['table']
                    table_id = element['objectId']
                    
                    # Check for array markers
                    array_key = self._find_array_marker_in_table(table)
                    if array_key:
                        tables_with_markers.append({
                            'slide_id': slide_id,
                            'slide_index': slide_index,
                            'table_id': table_id,
                            'table': table,
                            'array_key': array_key
                        })
        
        return tables_with_markers
    
    def _find_array_marker_in_table(self, table: Dict[str, Any]) -> Optional[str]:
        """
        Find array marker in table headers.
        
        Args:
            table: The table data
            
        Returns:
            The array key if found, None otherwise
        """
        if not table.get('tableRows'):
            return None
        
        # Check the first row (headers) for array markers
        header_row = table['tableRows'][0]
        for cell in header_row.get('tableCells', []):
            if 'text' in cell:
                text_elements = cell['text'].get('textElements', [])
                for text_element in text_elements:
                    if 'textRun' in text_element:
                        text = text_element['textRun'].get('content', '')
                        # Look for array pattern: {{ARRAY:key}}
                        match = re.search(r'\{\{ARRAY:([^}]+)\}\}', text)
                        if match:
                            return match.group(1)
        return None
    
    def get_table_headers(self, table: Dict[str, Any]) -> List[str]:
        """
        Extract headers from a table, removing array markers.
        
        Args:
            table: The table data
            
        Returns:
            List of cleaned header strings
        """
        headers = []
        if table.get('tableRows'):
            header_row = table['tableRows'][0]
            for cell in header_row.get('tableCells', []):
                if 'text' in cell:
                    text_content = ''
                    for text_element in cell['text'].get('textElements', []):
                        if 'textRun' in text_element:
                            text_content += text_element['textRun'].get('content', '')
                    # Remove the ARRAY marker from headers
                    text_content = re.sub(r'\{\{ARRAY:[^}]+\}\}', '', text_content).strip()
                    headers.append(text_content)
        return headers
    
    def create_table_row_request(self, table_id: str, row_index: int, cell_values: list) -> dict:
        """
        Create a request to insert a table row (Google Slides API expects camelCase keys).
        Args:
            table_id: The ID of the table
            row_index: The index where to insert the row (1-based, where 1 is first data row)
            cell_values: List of values for each cell
        Returns:
            The insert table row request (with camelCase keys)
        """
        # For insertTableRows, we need to reference an existing row
        # Since we have only 1 row (header), we reference row 0 and insert below
        return {
            'insertTableRows': {
                'tableObjectId': table_id,
                'cellLocation': {
                    'rowIndex': 0,  # Reference the header row (0-based)
                    'columnIndex': 0
                },
                'number': 1,
                'insertBelow': True
            }
        }
    
    def create_duplicate_slide_request(self, slide_id: str) -> Dict[str, Any]:
        """
        Create a request to duplicate a slide.
        
        Args:
            slide_id: The ID of the slide to duplicate
            
        Returns:
            The duplicate object request
        """
        return {
            'duplicateObject': {
                'objectId': slide_id
            }
        }
    
    def create_delete_slide_request(self, slide_id: str) -> Dict[str, Any]:
        """
        Create a request to delete a slide.
        
        Args:
            slide_id: The ID of the slide to delete
            
        Returns:
            The delete object request
        """
        return {
            'deleteObject': {
                'objectId': slide_id
            }
        }
    
    def create_replace_text_request(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """
        Create a request to replace text.
        
        Args:
            old_text: The text to replace
            new_text: The replacement text
            
        Returns:
            The replace all text request
        """
        return {
            'replaceAllText': {
                'containsText': {
                    'text': old_text,
                    'matchCase': True
                },
                'replaceText': new_text
            }
        }
    
    def create_update_table_cell_request(self, table_id: str, row_index: int, column_index: int, text: str) -> Dict[str, Any]:
        """
        Create a request to update a specific table cell.
        
        Args:
            table_id: The ID of the table
            row_index: The row index (0-based)
            column_index: The column index (0-based)
            text: The text to set in the cell
            
        Returns:
            The update table cell properties request
        """
        return {
            'updateTableCellProperties': {
                'objectId': table_id,
                'tableRange': {
                    'location': {
                        'rowIndex': row_index,
                        'columnIndex': column_index
                    },
                    'rowSpan': 1,
                    'columnSpan': 1
                },
                'tableCellProperties': {
                    'tableCellBackgroundFill': {
                        'propertyState': 'NOT_RENDERED'
                    }
                },
                'fields': 'tableCellBackgroundFill'
            }
        }
    
    def create_update_table_cell_text_request(self, table_id: str, row_index: int, column_index: int, text: str) -> Dict[str, Any]:
        """
        Create a request to update text in a specific table cell.
        This is more efficient than replaceAllText for table operations.
        
        Args:
            table_id: The ID of the table
            row_index: The row index (0-based)
            column_index: The column index (0-based)
            text: The text to set in the cell
            
        Returns:
            The update text style request
        """
        return {
            'insertText': {
                'objectId': table_id,
                'insertionIndex': 0,
                'text': text
            }
        } 

    def get_shape_ids_for_slide(self, presentation: Dict[str, Any], slide_object_id: str) -> dict:
        """
        Get the object IDs for the title and subtitle shapes for a given slide.
        Returns a dict with keys 'title' and 'subtitle' if found.
        """
        shape_ids = {}
        for slide in presentation.get('slides', []):
            if slide.get('objectId') == slide_object_id:
                for element in slide.get('pageElements', []):
                    if 'shape' in element:
                        shape_type = element['shape'].get('shapeType', '')
                        if shape_type == 'TITLE':
                            shape_ids['title'] = element['objectId']
                        elif shape_type == 'SUBTITLE':
                            shape_ids['subtitle'] = element['objectId']
        return shape_ids 