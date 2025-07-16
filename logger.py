"""
Comprehensive Logging System for Google Slides Automation

This module provides structured logging with different levels, error tracking,
and execution flow visibility for debugging and monitoring.
"""

import logging
import sys
import traceback
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
import json


class SlidesAutomationLogger:
    """Structured logger for Google Slides automation operations."""
    
    def __init__(self, log_level: str = "INFO", log_file: Optional[str] = None):
        """
        Initialize the logger.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional file path for logging to file
        """
        self.logger = logging.getLogger('slides_automation')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Track operation statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'api_calls': 0,
            'batch_updates': 0,
            'errors': []
        }
    
    def start_session(self, session_name: str, **kwargs):
        """Start a new logging session."""
        self.stats['start_time'] = time.time()
        self.stats['session_name'] = session_name
        
        self.logger.info("=" * 80)
        self.logger.info(f"🚀 STARTING SESSION: {session_name}")
        self.logger.info("=" * 80)
        
        if kwargs:
            self.logger.info(f"📋 Session Parameters: {json.dumps(kwargs, indent=2)}")
    
    def end_session(self):
        """End the current logging session and print summary."""
        self.stats['end_time'] = time.time()
        duration = self.stats['end_time'] - self.stats['start_time']
        
        self.logger.info("=" * 80)
        self.logger.info(f"🏁 SESSION COMPLETED: {self.stats['session_name']}")
        self.logger.info(f"⏱️  Duration: {duration:.2f} seconds")
        self.logger.info(f"📊 Operations: {self.stats['total_operations']} total, "
                        f"{self.stats['successful_operations']} successful, "
                        f"{self.stats['failed_operations']} failed")
        self.logger.info(f"🌐 API Calls: {self.stats['api_calls']}")
        self.logger.info(f"📦 Batch Updates: {self.stats['batch_updates']}")
        
        if self.stats['errors']:
            self.logger.warning(f"⚠️  Errors encountered: {len(self.stats['errors'])}")
            for i, error in enumerate(self.stats['errors'], 1):
                self.logger.warning(f"  {i}. {error}")
        
        self.logger.info("=" * 80)
    
    def log_operation(self, operation: str, details: Dict[str, Any] = None, level: str = "INFO"):
        """Log an operation with details."""
        self.stats['total_operations'] += 1
        
        message = f"🔧 {operation}"
        if details:
            message += f" | {json.dumps(details, default=str)}"
        
        getattr(self.logger, level.lower())(message)
    
    def log_api_call(self, operation: str, details: Dict[str, Any] = None):
        """Log an API call."""
        self.stats['api_calls'] += 1
        self.log_operation(f"API: {operation}", details, "DEBUG")
    
    def log_batch_update(self, operation_count: int, details: Dict[str, Any] = None):
        """Log a batch update operation."""
        self.stats['batch_updates'] += 1
        self.log_operation(f"BATCH UPDATE: {operation_count} operations", details, "INFO")
    
    def log_success(self, operation: str, details: Dict[str, Any] = None):
        """Log a successful operation."""
        self.stats['successful_operations'] += 1
        self.log_operation(f"✅ {operation}", details, "INFO")
    
    def log_error(self, operation: str, error: Exception, details: Dict[str, Any] = None):
        """Log an error with full context."""
        self.stats['failed_operations'] += 1
        error_info = {
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'details': details or {}
        }
        self.stats['errors'].append(error_info)
        
        self.logger.error(f"❌ {operation} | Error: {type(error).__name__}: {str(error)}")
        if details:
            self.logger.error(f"   Details: {json.dumps(details, default=str)}")
        self.logger.debug(f"   Traceback: {traceback.format_exc()}")
    
    def log_warning(self, message: str, details: Dict[str, Any] = None):
        """Log a warning."""
        self.log_operation(f"⚠️  {message}", details, "WARNING")
    
    def log_info(self, message: str, details: Dict[str, Any] = None):
        """Log an info message."""
        self.log_operation(message, details, "INFO")
    
    def log_debug(self, message: str, details: Dict[str, Any] = None):
        """Log a debug message."""
        self.log_operation(message, details, "DEBUG")
    
    @contextmanager
    def operation_context(self, operation_name: str, details: Dict[str, Any] = None):
        """Context manager for tracking operations with automatic success/error logging."""
        start_time = time.time()
        
        try:
            self.log_operation(f"START: {operation_name}", details, "DEBUG")
            yield
            duration = time.time() - start_time
            self.log_success(f"COMPLETED: {operation_name}", {
                **(details or {}),
                'duration_seconds': round(duration, 3)
            })
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_error(f"FAILED: {operation_name}", e, {
                **(details or {}),
                'duration_seconds': round(duration, 3)
            })
            raise
    
    def log_table_operation(self, table_info: Dict[str, Any], operation: str, details: Dict[str, Any] = None):
        """Log table-specific operations."""
        table_details = {
            'table_id': table_info.get('table_id'),
            'array_key': table_info.get('array_key'),
            'slide_index': table_info.get('slide_index'),
            **(details or {})
        }
        self.log_operation(f"📊 TABLE {operation}", table_details)
    
    def log_slide_operation(self, slide_id: str, operation: str, details: Dict[str, Any] = None):
        """Log slide-specific operations."""
        slide_details = {
            'slide_id': slide_id,
            **(details or {})
        }
        self.log_operation(f"🖼️  SLIDE {operation}", slide_details)
    
    def log_data_processing(self, data_type: str, count: int, details: Dict[str, Any] = None):
        """Log data processing operations."""
        data_details = {
            'data_type': data_type,
            'count': count,
            **(details or {})
        }
        self.log_operation(f"📋 DATA PROCESSING: {data_type} ({count} items)", data_details)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current session."""
        return {
            'session_name': self.stats.get('session_name'),
            'duration_seconds': time.time() - self.stats['start_time'] if self.stats['start_time'] else 0,
            'total_operations': self.stats['total_operations'],
            'successful_operations': self.stats['successful_operations'],
            'failed_operations': self.stats['failed_operations'],
            'api_calls': self.stats['api_calls'],
            'batch_updates': self.stats['batch_updates'],
            'error_count': len(self.stats['errors'])
        }


# Global logger instance
_logger_instance = None

def get_logger() -> SlidesAutomationLogger:
    """Get the global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SlidesAutomationLogger()
    return _logger_instance

 