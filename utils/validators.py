import logging
import os
from typing import Dict, Any
from werkzeug.datastructures import FileStorage

logger = logging.getLogger(__name__)

class FileValidator:
    """Validate uploaded files for security and format compliance"""
    
    def __init__(self):
        self.allowed_extensions = {
            '.docx': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            '.pdf': ['application/pdf'],
            '.png': ['image/png'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.bmp': ['image/bmp'],
            '.tiff': ['image/tiff']
        }
        
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.min_file_size = 100  # 100 bytes
    
    def validate_file(self, file: FileStorage) -> Dict[str, Any]:
        """
        Validate uploaded file for security and format compliance
        
        Args:
            file: Uploaded file object
            
        Returns:
            Dictionary containing validation results
        """
        try:
            # Check if file exists
            if not file or not file.filename:
                return {
                    'valid': False,
                    'message': 'No file provided'
                }
            
            # Get file extension
            filename = file.filename.lower()
            file_extension = None
            
            for ext in self.allowed_extensions.keys():
                if filename.endswith(ext):
                    file_extension = ext
                    break
            
            if not file_extension:
                return {
                    'valid': False,
                    'message': f'Unsupported file format. Allowed formats: {", ".join(self.allowed_extensions.keys())}'
                }
            
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)  # Reset file pointer
            
            if file_size < self.min_file_size:
                return {
                    'valid': False,
                    'message': f'File too small. Minimum size: {self.min_file_size} bytes'
                }
            
            if file_size > self.max_file_size:
                return {
                    'valid': False,
                    'message': f'File too large. Maximum size: {self.max_file_size // (1024*1024)}MB'
                }
            
            # Validate MIME type
            mime_type = file.content_type
            allowed_mimes = self.allowed_extensions[file_extension]
            
            if mime_type not in allowed_mimes:
                logger.warning(f"MIME type mismatch: {mime_type} not in {allowed_mimes}")
                # Don't fail validation for MIME type mismatch, just log warning
            
            # Basic file content validation
            file.seek(0)
            file_header = file.read(512)  # Read first 512 bytes
            file.seek(0)  # Reset file pointer
            
            validation_result = self._validate_file_header(file_header, file_extension)
            if not validation_result['valid']:
                return validation_result
            
            # Security checks
            security_result = self._security_checks(filename, file_header)
            if not security_result['valid']:
                return security_result
            
            return {
                'valid': True,
                'message': 'File validation passed',
                'extension': file_extension,
                'size': file_size,
                'mime_type': mime_type
            }
            
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            return {
                'valid': False,
                'message': f'File validation failed: {str(e)}'
            }
    
    def _validate_file_header(self, file_header: bytes, file_extension: str) -> Dict[str, Any]:
        """
        Validate file header/magic bytes
        
        Args:
            file_header: First bytes of the file
            file_extension: Expected file extension
            
        Returns:
            Validation result
        """
        try:
            if not file_header:
                return {
                    'valid': False,
                    'message': 'File appears to be empty or corrupted'
                }
            
            # Define magic bytes for different file types
            magic_bytes = {
                '.pdf': [b'%PDF'],
                '.png': [b'\x89PNG'],
                '.jpg': [b'\xff\xd8\xff'],
                '.jpeg': [b'\xff\xd8\xff'],
                '.bmp': [b'BM'],
                '.tiff': [b'II*\x00', b'MM\x00*'],
                '.docx': [b'PK\x03\x04']  # ZIP-based format
            }
            
            if file_extension in magic_bytes:
                expected_magic = magic_bytes[file_extension]
                
                # Check if file header starts with any of the expected magic bytes
                header_match = False
                for magic in expected_magic:
                    if file_header.startswith(magic):
                        header_match = True
                        break
                
                if not header_match:
                    return {
                        'valid': False,
                        'message': f'File header does not match expected format for {file_extension}'
                    }
            
            return {'valid': True}
            
        except Exception as e:
            logger.error(f"Header validation error: {str(e)}")
            return {
                'valid': False,
                'message': 'Failed to validate file header'
            }
    
    def _security_checks(self, filename: str, file_header: bytes) -> Dict[str, Any]:
        """
        Perform security checks on the file
        
        Args:
            filename: Name of the file
            file_header: File header bytes
            
        Returns:
            Security validation result
        """
        try:
            # Check for suspicious filename patterns
            suspicious_patterns = [
                '../', '..\\',  # Path traversal
                '<script', '</script>',  # Script injection
                '<?php', '?>',  # PHP code
                '<%', '%>',  # ASP code
                'javascript:',  # JavaScript protocol
                'data:',  # Data URI
            ]
            
            filename_lower = filename.lower()
            for pattern in suspicious_patterns:
                if pattern in filename_lower:
                    return {
                        'valid': False,
                        'message': f'Suspicious filename pattern detected: {pattern}'
                    }
            
            # Check for embedded executables or scripts in file header
            executable_signatures = [
                b'MZ',  # Windows executable
                b'\x7fELF',  # Linux executable
                b'\xca\xfe\xba\xbe',  # Java class file
                b'#!/bin/',  # Shell script
                b'#!/usr/bin/',  # Shell script
            ]
            
            for signature in executable_signatures:
                if file_header.startswith(signature):
                    return {
                        'valid': False,
                        'message': 'File appears to contain executable code'
                    }
            
            # Check file size limits per type
            max_sizes = {
                '.pdf': 40 * 1024 * 1024,  # 40MB for PDFs
                '.docx': 30 * 1024 * 1024,  # 30MB for DOCX
                '.png': 20 * 1024 * 1024,   # 20MB for images
                '.jpg': 20 * 1024 * 1024,
                '.jpeg': 20 * 1024 * 1024,
                '.bmp': 25 * 1024 * 1024,
                '.tiff': 25 * 1024 * 1024,
            }
            
            # Additional security validations can be added here
            
            return {'valid': True}
            
        except Exception as e:
            logger.error(f"Security check error: {str(e)}")
            return {
                'valid': False,
                'message': 'Security validation failed'
            }
    
    def get_file_info(self, file: FileStorage) -> Dict[str, Any]:
        """
        Get detailed information about the uploaded file
        
        Args:
            file: Uploaded file object
            
        Returns:
            File information dictionary
        """
        try:
            if not file or not file.filename:
                return {}
            
            # Get file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            # Get file extension
            filename = file.filename.lower()
            file_extension = None
            for ext in self.allowed_extensions.keys():
                if filename.endswith(ext):
                    file_extension = ext
                    break
            
            return {
                'filename': file.filename,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'extension': file_extension,
                'mime_type': file.content_type,
                'is_supported': file_extension in self.allowed_extensions
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return {}
