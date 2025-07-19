import logging
import time
import cv2
import numpy as np
import pytesseract
from PIL import Image
import pandas as pd
from typing import List, Dict, Any, Optional
import re
import os

logger = logging.getLogger(__name__)

class ImageExtractor:
    """Extract tables and data from images using OCR and computer vision"""
    
    def __init__(self):
        self.supported_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']
        
        # Configure Tesseract (adjust path if needed)
        # pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        
    def extract_tables(self, file_path: str) -> Dict[str, Any]:
        """
        Extract tables from image using OCR and table detection
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dictionary containing extraction results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting image extraction for: {file_path}")
            
            # Load and preprocess image
            image = cv2.imread(file_path)
            if image is None:
                raise ValueError("Could not load image file")
            
            # Preprocess image for better OCR
            processed_image = self._preprocess_image(image)
            
            # Detect table regions
            table_regions = self._detect_table_regions(processed_image)
            
            tables_data = []
            warnings = []
            
            if not table_regions:
                # If no tables detected, try full image OCR
                logger.info("No table regions detected, performing full image OCR")
                full_text_result = self._extract_full_text_as_table(processed_image)
                if full_text_result:
                    tables_data.append(full_text_result)
                else:
                    warnings.append("No tabular data could be extracted from image")
            else:
                # Extract data from each detected table region
                for i, region in enumerate(table_regions):
                    try:
                        table_data = self._extract_table_from_region(processed_image, region, i)
                        if table_data:
                            tables_data.append(table_data)
                            logger.info(f"Extracted table {i}: {table_data['rows']} rows x {table_data['columns']} columns")
                        else:
                            warnings.append(f"Table region {i} produced no usable data")
                    except Exception as e:
                        logger.error(f"Error extracting table {i}: {str(e)}")
                        warnings.append(f"Failed to extract table {i}: {str(e)}")
            
            processing_time = time.time() - start_time
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(tables_data, processed_image)
            
            result = {
                'success': True,
                'tables': tables_data,
                'table_count': len(tables_data),
                'processing_time': processing_time,
                'accuracy_score': quality_metrics['accuracy_score'],
                'quality_metrics': quality_metrics,
                'warnings': warnings,
                'extraction_method': 'ocr_cv'
            }
            
            logger.info(f"Image extraction completed: {len(tables_data)} tables in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Image extraction failed: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to extract data from image: {str(e)}',
                'details': {'error_type': type(e).__name__, 'file_path': file_path}
            }
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results
        
        Args:
            image: Original image
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply noise removal
        denoised = cv2.medianBlur(gray, 3)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Apply morphological operations to enhance table lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed
    
    def _detect_table_regions(self, image: np.ndarray) -> List[Dict[str, int]]:
        """
        Detect table regions in the image using line detection
        
        Args:
            image: Preprocessed image
            
        Returns:
            List of table region coordinates
        """
        try:
            # Detect horizontal and vertical lines
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            
            # Detect horizontal lines
            horizontal_lines = cv2.morphologyEx(image, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Detect vertical lines
            vertical_lines = cv2.morphologyEx(image, cv2.MORPH_OPEN, vertical_kernel)
            
            # Combine lines
            table_mask = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
            
            # Find contours of table regions
            contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter and sort contours by area
            table_regions = []
            min_area = 1000  # Minimum area for a table
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > min_area:
                    x, y, w, h = cv2.boundingRect(contour)
                    # Add some padding
                    padding = 10
                    table_regions.append({
                        'x': max(0, x - padding),
                        'y': max(0, y - padding),
                        'width': min(image.shape[1] - x + padding, w + 2*padding),
                        'height': min(image.shape[0] - y + padding, h + 2*padding),
                        'area': area
                    })
            
            # Sort by area (largest first)
            table_regions.sort(key=lambda x: x['area'], reverse=True)
            
            logger.info(f"Detected {len(table_regions)} potential table regions")
            return table_regions
            
        except Exception as e:
            logger.error(f"Table detection failed: {str(e)}")
            return []
    
    def _extract_table_from_region(self, image: np.ndarray, region: Dict[str, int], table_index: int) -> Optional[Dict[str, Any]]:
        """
        Extract table data from a specific region
        
        Args:
            image: Preprocessed image
            region: Table region coordinates
            table_index: Index of the table
            
        Returns:
            Extracted table data
        """
        try:
            # Extract region of interest
            x, y, w, h = region['x'], region['y'], region['width'], region['height']
            roi = image[y:y+h, x:x+w]
            
            # Perform OCR on the region
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()%$-+= '
            
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(roi, config=custom_config, output_type=pytesseract.Output.DICT)
            
            # Parse OCR data into table structure
            table_data = self._parse_ocr_to_table(ocr_data, roi.shape)
            
            if table_data and len(table_data) > 0:
                return {
                    'table_index': table_index,
                    'data': table_data,
                    'rows': len(table_data),
                    'columns': len(table_data[0]) if table_data else 0,
                    'region': region,
                    'confidence': self._calculate_ocr_confidence(ocr_data)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting table from region {table_index}: {str(e)}")
            return None
    
    def _extract_full_text_as_table(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Extract full image text and attempt to structure it as a table
        
        Args:
            image: Preprocessed image
            
        Returns:
            Structured table data or None
        """
        try:
            # Perform OCR on entire image
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            if not text.strip():
                return None
            
            # Try to parse text into table structure
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Attempt to detect table-like structure
            table_data = []
            for line in lines:
                # Split by multiple spaces, tabs, or common separators
                row = re.split(r'\s{2,}|\t|[|]', line)
                row = [cell.strip() for cell in row if cell.strip()]
                
                if len(row) > 1:  # Only keep rows with multiple columns
                    table_data.append(row)
            
            if table_data:
                # Normalize column count
                max_cols = max(len(row) for row in table_data)
                for row in table_data:
                    while len(row) < max_cols:
                        row.append('')
                
                return {
                    'table_index': 0,
                    'data': table_data,
                    'rows': len(table_data),
                    'columns': max_cols,
                    'confidence': 0.5  # Lower confidence for full-text extraction
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Full text extraction failed: {str(e)}")
            return None
    
    def _parse_ocr_to_table(self, ocr_data: Dict, image_shape: tuple) -> List[List[str]]:
        """
        Parse OCR data into table structure based on word positions
        
        Args:
            ocr_data: OCR data from pytesseract
            image_shape: Shape of the processed image
            
        Returns:
            Table data as list of lists
        """
        try:
            # Extract words with positions and confidence
            words = []
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) > 30:  # Filter low confidence words
                    word = ocr_data['text'][i].strip()
                    if word:
                        words.append({
                            'text': word,
                            'left': ocr_data['left'][i],
                            'top': ocr_data['top'][i],
                            'width': ocr_data['width'][i],
                            'height': ocr_data['height'][i],
                            'conf': ocr_data['conf'][i]
                        })
            
            if not words:
                return []
            
            # Group words into rows based on vertical position
            words.sort(key=lambda x: x['top'])
            
            rows = []
            current_row = []
            row_threshold = 20  # Pixels tolerance for same row
            
            for word in words:
                if not current_row:
                    current_row = [word]
                else:
                    # Check if word is in same row
                    avg_top = sum(w['top'] for w in current_row) / len(current_row)
                    if abs(word['top'] - avg_top) <= row_threshold:
                        current_row.append(word)
                    else:
                        # Sort current row by horizontal position and add to rows
                        current_row.sort(key=lambda x: x['left'])
                        rows.append(current_row)
                        current_row = [word]
            
            # Add last row
            if current_row:
                current_row.sort(key=lambda x: x['left'])
                rows.append(current_row)
            
            # Convert to table structure
            table_data = []
            for row in rows:
                row_text = [word['text'] for word in row]
                table_data.append(row_text)
            
            # Normalize column count
            if table_data:
                max_cols = max(len(row) for row in table_data)
                for row in table_data:
                    while len(row) < max_cols:
                        row.append('')
            
            return table_data
            
        except Exception as e:
            logger.error(f"OCR parsing failed: {str(e)}")
            return []
    
    def _calculate_ocr_confidence(self, ocr_data: Dict) -> float:
        """Calculate average OCR confidence score"""
        try:
            confidences = [int(conf) for conf in ocr_data['conf'] if int(conf) > 0]
            return sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
        except:
            return 0.0
    
    def _calculate_quality_metrics(self, tables_data: List[Dict], image: np.ndarray) -> Dict[str, Any]:
        """Calculate quality metrics for image extraction"""
        if not tables_data:
            return {
                'accuracy_score': 0.0,
                'ocr_confidence': 0.0,
                'data_quality_issues': ['No tables extracted from image']
            }
        
        # Calculate average OCR confidence
        confidences = [table.get('confidence', 0.0) for table in tables_data]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Estimate data completeness based on table structure
        total_cells = sum(table['rows'] * table['columns'] for table in tables_data)
        non_empty_cells = 0
        
        for table in tables_data:
            for row in table.get('data', []):
                non_empty_cells += sum(1 for cell in row if cell.strip())
        
        completeness = non_empty_cells / total_cells if total_cells > 0 else 0.0
        
        # Overall accuracy (weighted combination)
        accuracy_score = (avg_confidence * 0.7 + completeness * 0.3)
        
        return {
            'accuracy_score': round(accuracy_score, 3),
            'ocr_confidence': round(avg_confidence, 3),
            'completeness': round(completeness, 3),
            'total_cells': total_cells,
            'non_empty_cells': non_empty_cells,
            'image_dimensions': f"{image.shape[1]}x{image.shape[0]}"
        }
