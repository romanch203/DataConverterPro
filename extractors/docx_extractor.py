import logging
import time
from docx import Document
from docx.table import Table
import pandas as pd
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DocxExtractor:
    """Extract tables and data from DOCX files"""
    
    def __init__(self):
        self.supported_extensions = ['.docx']
    
    def extract_tables(self, file_path: str) -> Dict[str, Any]:
        """
        Extract all tables from a DOCX file
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Dictionary containing extraction results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting DOCX extraction for: {file_path}")
            
            # Open document
            doc = Document(file_path)
            
            # Extract tables
            tables_data = []
            warnings = []
            
            for i, table in enumerate(doc.tables):
                try:
                    table_data = self._extract_single_table(table, i)
                    if table_data and len(table_data) > 0:
                        tables_data.append({
                            'table_index': i,
                            'data': table_data,
                            'rows': len(table_data),
                            'columns': len(table_data[0]) if table_data else 0
                        })
                        logger.info(f"Extracted table {i}: {len(table_data)} rows x {len(table_data[0]) if table_data else 0} columns")
                    else:
                        warnings.append(f"Table {i} appears to be empty or malformed")
                        
                except Exception as e:
                    logger.error(f"Error extracting table {i}: {str(e)}")
                    warnings.append(f"Failed to extract table {i}: {str(e)}")
            
            processing_time = time.time() - start_time
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(tables_data)
            
            result = {
                'success': True,
                'tables': tables_data,
                'table_count': len(tables_data),
                'processing_time': processing_time,
                'accuracy_score': quality_metrics['accuracy_score'],
                'quality_metrics': quality_metrics,
                'warnings': warnings,
                'extraction_method': 'docx_native'
            }
            
            logger.info(f"DOCX extraction completed: {len(tables_data)} tables in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"DOCX extraction failed: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to extract data from DOCX file: {str(e)}',
                'details': {'error_type': type(e).__name__, 'file_path': file_path}
            }
    
    def _extract_single_table(self, table: Table, table_index: int) -> List[List[str]]:
        """
        Extract data from a single table
        
        Args:
            table: Document table object
            table_index: Index of the table in document
            
        Returns:
            List of rows, each row is a list of cell values
        """
        try:
            table_data = []
            
            for row_idx, row in enumerate(table.rows):
                row_data = []
                
                for cell_idx, cell in enumerate(row.cells):
                    # Clean cell text
                    cell_text = cell.text.strip()
                    
                    # Handle merged cells by checking if this cell spans multiple columns
                    if hasattr(cell, '_element'):
                        # Check for merged cells and handle accordingly
                        cell_text = self._clean_cell_text(cell_text)
                    
                    row_data.append(cell_text)
                
                # Only add non-empty rows
                if any(cell.strip() for cell in row_data):
                    table_data.append(row_data)
            
            # Normalize table structure (ensure all rows have same number of columns)
            if table_data:
                max_cols = max(len(row) for row in table_data)
                for row in table_data:
                    while len(row) < max_cols:
                        row.append('')
            
            return table_data
            
        except Exception as e:
            logger.error(f"Error extracting single table {table_index}: {str(e)}")
            return []
    
    def _clean_cell_text(self, text: str) -> str:
        """
        Clean and normalize cell text
        
        Args:
            text: Raw cell text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ''
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Remove common unwanted characters but preserve numbers and punctuation
        text = text.replace('\x0b', ' ')  # Vertical tab
        text = text.replace('\x0c', ' ')  # Form feed
        
        return text.strip()
    
    def _calculate_quality_metrics(self, tables_data: List[Dict]) -> Dict[str, Any]:
        """
        Calculate quality metrics for extracted data
        
        Args:
            tables_data: List of extracted table data
            
        Returns:
            Dictionary containing quality metrics
        """
        if not tables_data:
            return {
                'accuracy_score': 0.0,
                'completeness': 0.0,
                'consistency': 0.0,
                'data_quality_issues': ['No tables extracted']
            }
        
        total_cells = 0
        empty_cells = 0
        inconsistent_columns = 0
        data_quality_issues = []
        
        for table in tables_data:
            table_data = table['data']
            if not table_data:
                continue
                
            # Count cells and empty cells
            for row in table_data:
                total_cells += len(row)
                empty_cells += sum(1 for cell in row if not cell.strip())
            
            # Check column consistency
            if table_data:
                expected_cols = len(table_data[0])
                for i, row in enumerate(table_data[1:], 1):
                    if len(row) != expected_cols:
                        inconsistent_columns += 1
                        if len(data_quality_issues) < 5:  # Limit number of issues reported
                            data_quality_issues.append(f"Table {table['table_index']} row {i}: inconsistent column count")
        
        # Calculate metrics
        completeness = (total_cells - empty_cells) / total_cells if total_cells > 0 else 0.0
        consistency = 1.0 - (inconsistent_columns / len(tables_data)) if tables_data else 0.0
        
        # Overall accuracy score (weighted average)
        accuracy_score = (completeness * 0.6 + consistency * 0.4)
        
        return {
            'accuracy_score': round(accuracy_score, 3),
            'completeness': round(completeness, 3),
            'consistency': round(consistency, 3),
            'total_cells': total_cells,
            'empty_cells': empty_cells,
            'data_quality_issues': data_quality_issues
        }
