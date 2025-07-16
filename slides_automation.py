"""
Google Slides Automation Module

This module provides functionality to:
1. Copy a Google Slides template
2. Populate the copied presentation with JSON data
3. Perform dynamic table operations and text replacement
"""

from typing import Dict, List, Any
from api_handler import GoogleSlidesAPIHandler
from logger import get_logger


class GoogleSlidesAutomation:
    """Main class for Google Slides automation operations."""
    
    def __init__(self, credentials_path: str = 'credentials.json'):
        """
        Initialize the Google Slides automation.
        
        Args:
            credentials_path: Path to the Google API credentials JSON file
        """
        self.api_handler = GoogleSlidesAPIHandler(credentials_path)
        self.logger = get_logger()
        self.batch_update_stats = {
            'total_batches': 0,
            'operations_by_type': {},
            'total_requests': 0,
            'batch_details': []  # Track each batch with details
        }
        
        # Override the API handler's batch update methods to track statistics
        self._original_batch_update = self.api_handler.batch_update
        self._original_batch_update_with_size_check = self.api_handler.batch_update_with_size_check
        
        # Replace with tracking versions
        self.api_handler.batch_update = lambda pid, reqs: self._original_batch_update(pid, reqs, lambda reqs: self._track_batch_stats(reqs, "Unknown operation"))
        self.api_handler.batch_update_with_size_check = self._tracked_batch_update_with_size_check
    
    def _track_batch_stats(self, requests: List[Dict[str, Any]], operation_description: str = "Unknown operation") -> None:
        """Track batch update statistics with operation description."""
        self.batch_update_stats['total_batches'] += 1
        self.batch_update_stats['total_requests'] += len(requests)
        
        # Track operation types
        for request in requests:
            request_type = list(request.keys())[0] if request else 'unknown'
            self.batch_update_stats['operations_by_type'][request_type] = self.batch_update_stats['operations_by_type'].get(request_type, 0) + 1
        
        # Store batch details
        batch_detail = {
            'batch_number': self.batch_update_stats['total_batches'],
            'description': operation_description,
            'request_count': len(requests),
            'request_types': {},
            'payload_size': self.api_handler._calculate_payload_size(requests)
        }
        
        # Count request types for this batch
        for request in requests:
            request_type = list(request.keys())[0] if request else 'unknown'
            batch_detail['request_types'][request_type] = batch_detail['request_types'].get(request_type, 0) + 1
        
        self.batch_update_stats['batch_details'].append(batch_detail)
    
    def _tracked_batch_update_with_size_check(self, presentation_id: str, requests: List[Dict[str, Any]], max_size_bytes: int = 10*1024*1024, operation_description: str = "Unknown operation") -> None:
        """Execute batch update with size checking and tracking."""
        if not requests:
            self.logger.log_debug("Skipping empty batch update")
            return
        
        # Check if we need to split the batch
        payload_size = self.api_handler._calculate_payload_size(requests)
        
        if payload_size <= max_size_bytes:
            # Single batch is fine
            self._original_batch_update(presentation_id, requests, lambda reqs: self._track_batch_stats(reqs, operation_description))
        else:
            # Need to split into chunks
            self.logger.log_info(f"Payload size ({payload_size:,} bytes) exceeds limit ({max_size_bytes:,} bytes). Splitting into chunks.")
            
            chunks = self.api_handler._split_requests_into_chunks(requests, max_size_bytes)
            
            for i, chunk in enumerate(chunks):
                chunk_size = self.api_handler._calculate_payload_size(chunk)
                chunk_description = f"{operation_description} (chunk {i+1}/{len(chunks)})"
                self.logger.log_info(f"Executing chunk {i+1}/{len(chunks)} with {len(chunk)} requests ({chunk_size:,} bytes)")
                self._original_batch_update(presentation_id, chunk, lambda reqs: self._track_batch_stats(reqs, chunk_description))
    
    def _log_batch_update_summary(self) -> None:
        """Log a summary of all batch update operations."""
        stats = self.batch_update_stats
        
        self.logger.log_info("📊 BATCH UPDATE SUMMARY", {
            'total_batches': stats['total_batches'],
            'total_requests': stats['total_requests'],
            'operations_by_type': stats['operations_by_type']
        })
        
        # Print a formatted summary
        print("\n" + "="*60)
        print("📊 BATCH UPDATE OPERATIONS SUMMARY")
        print("="*60)
        print(f"Total Batch Updates: {stats['total_batches']}")
        print(f"Total Requests: {stats['total_requests']}")
        print("\nOperations by Type:")
        for op_type, count in sorted(stats['operations_by_type'].items()):
            print(f"  • {op_type}: {count} requests")
        
        print("\n📋 DETAILED BATCH BREAKDOWN:")
        print("-" * 60)
        for batch in stats['batch_details']:
            print(f"Batch #{batch['batch_number']}: {batch['description']}")
            print(f"  • Requests: {batch['request_count']}")
            print(f"  • Payload: {batch['payload_size']:,} bytes")
            print(f"  • Operations: {', '.join([f'{k}: {v}' for k, v in batch['request_types'].items()])}")
            print()
        
        print("="*60)
    
    def copy_presentation(self, template_id: str, title: str = "Generated Presentation") -> str:
        """
        Copy a Google Slides template to create a new presentation.
        
        Args:
            template_id: The ID of the template presentation
            title: Title for the new presentation
            
        Returns:
            The ID of the newly created presentation
        """
        with self.logger.operation_context("Copy Presentation Template", {
            'template_id': template_id,
            'title': title
        }):
            return self.api_handler.copy_presentation(template_id, title)
    
    def process_presentation(self, presentation_id: str, json_data: Dict[str, Any]) -> None:
        """
        Process a presentation and populate it with JSON data.
        
        Args:
            presentation_id: The ID of the presentation to process
            json_data: The JSON data to populate the presentation with
        """
        with self.logger.operation_context("Process Presentation", {
            'presentation_id': presentation_id,
            'data_keys': list(json_data.keys()) if json_data else []
        }):
            try:
                # Get the presentation once
                presentation = self.api_handler.get_presentation(presentation_id)
                
                # Collect all operations and execute them efficiently
                self._process_all_operations(presentation_id, presentation, json_data)
                
            except Exception as error:
                self.logger.log_error("Failed to process presentation", error, {
                    'presentation_id': presentation_id
                })
                raise
    
    def _process_all_operations(self, presentation_id: str, presentation: Dict, json_data: Dict[str, Any]) -> None:
        """
        Process all operations following the correct 3-step approach:
        1. Get slides info -> identify tables that point to an array
        2. Duplicating and erasing slides -> batch update
        3. Replacing text from all tables and components with identifiers
        """
        # Step 1: Get slides info and identify tables with array markers
        tables_with_markers = self.api_handler.find_tables_with_array_markers(presentation)
        self.logger.log_info(f"Found {len(tables_with_markers)} tables with array markers")
        
        # Step 2: Prepare structural changes (duplicate/erase slides)
        structural_requests = []
        table_operations = []
        
        for table_info in tables_with_markers:
            array_key = table_info['array_key']
            if array_key in json_data:
                array_data = json_data[array_key]
                
                self.logger.log_table_operation(table_info, "Processing", {
                    'array_key': array_key,
                    'data_count': len(array_data) if array_data else 0
                })
                
                if not array_data:  # Empty array - mark slide for deletion
                    self.logger.log_slide_operation(table_info['slide_id'], "Marked for deletion (empty array)")
                    structural_requests.append(
                        self.api_handler.create_delete_slide_request(table_info['slide_id'])
                    )
                else:
                    # Calculate how many slides we need
                    items_per_slide = 5  # Max 5 data rows per slide (plus 1 header row = 6 total)
                    total_slides_needed = (len(array_data) + items_per_slide - 1) // items_per_slide
                    
                    self.logger.log_data_processing(array_key, len(array_data), {
                        'items_per_slide': items_per_slide,
                        'total_slides_needed': total_slides_needed
                    })
                    
                    # Add slide duplication requests if needed
                    if total_slides_needed > 1:
                        for i in range(total_slides_needed - 1):
                            self.logger.log_slide_operation(table_info['slide_id'], f"Duplication {i+1}/{total_slides_needed-1}")
                            structural_requests.append(
                                self.api_handler.create_duplicate_slide_request(table_info['slide_id'])
                            )
                    
                    # Store table operation info for later processing
                    table_operations.append({
                        'slide_id': table_info['slide_id'],
                        'slide_index': table_info['slide_index'],
                        'table_id': table_info['table_id'],
                        'array_key': array_key,
                        'array_data': array_data,
                        'items_per_slide': items_per_slide,
                        'total_slides_needed': total_slides_needed
                    })
            else:
                self.logger.log_warning(f"Array key '{array_key}' not found in JSON data")
        
        # Execute structural changes (Step 2)
        if structural_requests:
            self.logger.log_info(f"Executing {len(structural_requests)} structural changes")
            self.api_handler.batch_update_with_size_check(presentation_id, structural_requests, operation_description="Structural changes (slide duplication/deletion)")
        
        # Get updated presentation if structural changes were made
        if structural_requests:
            self.logger.log_info("Fetching updated presentation after structural changes")
            presentation = self.api_handler.get_presentation(presentation_id)
        
        # Step 3: Collect all row and cell requests for all tables
        all_row_requests = []
        all_cell_requests = []
        for table_op in table_operations:
            row_requests, cell_requests = self._collect_table_population_requests(presentation_id, table_op)
            all_row_requests.extend(row_requests)
            all_cell_requests.extend(cell_requests)
        
        if all_row_requests:
            self.api_handler.batch_update_with_size_check(presentation_id, all_row_requests, operation_description="Insert table rows for all tables")
        if all_cell_requests:
            self.api_handler.batch_update_with_size_check(presentation_id, all_cell_requests, operation_description="Populate table cells for all tables")
        
        # Process text replacement for non-table elements
        self.logger.log_info("Creating text replacement requests")
        content_requests = self._create_text_replacement_requests(presentation, json_data)
        if content_requests:
            self.logger.log_info(f"Executing {len(content_requests)} content changes")
            self.api_handler.batch_update_with_size_check(presentation_id, content_requests, operation_description="Text replacement for placeholders")
    
    def _create_table_population_requests(self, presentation: Dict, table_op: Dict) -> List[Dict]:
        """
        Create table population requests using replaceAllText to populate existing table cells.
        This approach works within Google Slides API limitations.
        """
        requests = []
        array_key = table_op['array_key']
        array_data = table_op['array_data']
        
        # Find all slides that contain tables with this array marker
        slides_to_populate = []
        original_slide_index = table_op['slide_index']
        slides = presentation.get('slides', [])
        
        # Find the original slide and all its duplicates
        for i in range(original_slide_index, min(original_slide_index + table_op['total_slides_needed'], len(slides))):
            slide = slides[i]
            for element in slide.get('pageElements', []):
                if 'table' in element:
                    found_array_key = self.api_handler._find_array_marker_in_table(element['table'])
                    if found_array_key == array_key:
                        slides_to_populate.append({
                            'slide_index': i,
                            'table_id': element['objectId'],
                            'table': element['table']
                        })
                        break
        
        if not slides_to_populate:
            self.logger.log_warning(f"No slides found with array marker '{array_key}'")
            return requests
        
        # Get headers from the first table
        headers = self.api_handler.get_table_headers(slides_to_populate[0]['table'])
        items_per_slide = table_op['items_per_slide']
        
        self.logger.log_info(f"Processing {len(slides_to_populate)} slides for array '{array_key}' with {len(array_data)} items")
        
        # Process each slide with its portion of data
        for slide_idx, slide_data in enumerate(slides_to_populate):
            # Calculate which portion of data goes to this slide
            slide_start = slide_idx * items_per_slide
            slide_end = min(slide_start + items_per_slide, len(array_data))
            slide_items = array_data[slide_start:slide_end]
            
            self.logger.log_info(f"Slide {slide_idx + 1}: processing items {slide_start + 1}-{slide_end} ({len(slide_items)} items)")
            
            # Get current table structure
            current_table = slide_data['table']
            current_rows = len(current_table.get('tableRows', []))
            available_data_rows = current_rows - 1  # -1 for header row
            
            # Populate available rows with data using replaceAllText
            for item_index, item in enumerate(slide_items):
                if item_index >= available_data_rows:
                    self.logger.log_warning(f"Slide {slide_idx + 1}: More items than available rows, stopping at row {available_data_rows}")
                    break  # No more rows available
                    
                row_index = item_index + 1  # +1 because row 0 is headers
                
                for col_index, header in enumerate(headers):
                    # Create a unique placeholder for this cell
                    placeholder = f"{{{{{array_key}_{row_index}_{header}}}}}"
                    value = str(item.get(header, item.get(str(header), '')))
                    
                    # Add the replacement request
                    requests.append(
                        self.api_handler.create_replace_text_request(placeholder, value)
                    )
            
            # Clear unused rows if we have fewer items than rows
            unused_rows = max(0, available_data_rows - len(slide_items))
            if unused_rows > 0:
                self.logger.log_info(f"Slide {slide_idx + 1}: Clearing {unused_rows} unused rows")
                for row_offset in range(unused_rows):
                    row_index = len(slide_items) + 1 + row_offset
                    for col_index, header in enumerate(headers):
                        placeholder = f"{{{{{array_key}_{row_index}_{header}}}}}"
                        requests.append(
                            self.api_handler.create_replace_text_request(placeholder, '')
                        )
        
        self.logger.log_info(f"Created {len(requests)} table population requests for array '{array_key}'")
        return requests
    
    def _create_text_replacement_requests(self, presentation: Dict, json_data: Dict[str, Any]) -> List[Dict]:
        """
        Create all text replacement requests.
        
        Args:
            presentation: The presentation data
            json_data: The JSON data for replacements
            
        Returns:
            List of text replacement requests
        """
        requests = []
        
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                # Handle text in shapes
                if 'shape' in element and 'text' in element['shape']:
                    text_elements = element['shape']['text'].get('textElements', [])
                    for text_element in text_elements:
                        if 'textRun' in text_element:
                            text = text_element['textRun'].get('content', '')
                            # Look for JSON data patterns: {{json_key}}
                            matches = re.findall(r'\{\{([^}]+)\}\}', text)
                            for match in matches:
                                if match in json_data:
                                    replacement_text = str(json_data[match])
                                    requests.append(
                                        self.api_handler.create_replace_text_request(
                                            f'{{{{{match}}}}}', 
                                            replacement_text
                                        )
                                    )
                
                # Handle text in table cells
                elif 'table' in element:
                    table = element['table']
                    for row in table.get('tableRows', []):
                        for cell in row.get('tableCells', []):
                            if 'text' in cell:
                                text_elements = cell['text'].get('textElements', [])
                                for text_element in text_elements:
                                    if 'textRun' in text_element:
                                        text = text_element['textRun'].get('content', '')
                                        # Look for JSON data patterns: {{json_key}}
                                        matches = re.findall(r'\{\{([^}]+)\}\}', text)
                                        for match in matches:
                                            if match in json_data:
                                                replacement_text = str(json_data[match])
                                                requests.append(
                                                    self.api_handler.create_replace_text_request(
                                                        f'{{{{{match}}}}}', 
                                                        replacement_text
                                                    )
                                                )
        
        return requests
    
    def create_presentation_from_template(self, template_id: str, json_data: Dict[str, Any], 
                                        title: str = "Generated Presentation") -> str:
        """
        Main method to create a presentation from template and populate with JSON data.
        
        Args:
            template_id: The ID of the template presentation
            json_data: The JSON data to populate the presentation with
            title: Title for the new presentation
            
        Returns:
            The ID of the newly created presentation
        """
        # Start logging session
        self.logger.start_session("Create Presentation from Template", 
            template_id=template_id,
            title=title,
            data_keys=list(json_data.keys()) if json_data else []
        )
        
        try:
            # Step 1: Copy the template
            new_presentation_id = self.copy_presentation(template_id, title)
            # Step 2: Process and populate the presentation
            self.process_presentation(new_presentation_id, json_data)
            self.logger.log_success("Presentation creation completed", {
                'new_presentation_id': new_presentation_id
            })
            return new_presentation_id 
        finally:
            # Log final batch update statistics
            self._log_batch_update_summary()
            # End logging session
            self.logger.end_session() 

    def _collect_table_population_requests(self, presentation_id: str, slide_info: Dict) -> (list, list):
        """
        Collect row and cell requests for a table, but do not send them. Returns (row_requests, cell_requests).
        """
        # Get the updated presentation to access the new table IDs after duplication
        presentation = self.api_handler.get_presentation(presentation_id)
        slides_to_populate = []
        # Search through all slides to find tables with the correct array marker
        slides = presentation.get('slides', [])
        for i, slide in enumerate(slides):
            for element in slide.get('pageElements', []):
                if 'table' in element:
                    array_key = self.api_handler._find_array_marker_in_table(element['table'])
                    if array_key == slide_info['array_key']:
                        slides_to_populate.append({
                            'slide_index': i,
                            'table_id': element['objectId'],
                            'table': element['table']
                        })
                        break
        headers = []
        if slides_to_populate:
            headers = self.api_handler.get_table_headers(slides_to_populate[0]['table'])
        else:
            self.logger.log_warning(f"No slides found for array '{slide_info['array_key']}'")
            return [], []
        array_data = slide_info['array_data']
        items_per_slide = slide_info['items_per_slide']
        row_requests = []
        cell_requests = []
        for slide_idx, slide_data in enumerate(slides_to_populate):
            slide_start = slide_idx * items_per_slide
            slide_end = min(slide_start + items_per_slide, len(array_data))
            slide_items = array_data[slide_start:slide_end]
            for item_index, item in enumerate(slide_items):
                row_requests.append(
                    self.api_handler.create_table_row_request(
                        slide_data['table_id'],
                        item_index + 1,
                        []
                    )
                )
            for item_index, item in enumerate(slide_items):
                actual_row_index = item_index + 1
                for col_index, header in enumerate(headers):
                    cell_value = item.get(header, item.get(str(header), ''))
                    cell_requests.append({
                        'insertText': {
                            'objectId': slide_data['table_id'],
                            'cellLocation': {
                                'rowIndex': actual_row_index,
                                'columnIndex': col_index
                            },
                            'text': str(cell_value)
                        }
                    })
        return row_requests, cell_requests 