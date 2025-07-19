import logging
import time
import pandas as pd
from typing import List, Dict, Any, Optional
import pdfplumber
import tabula
import camelot
import tempfile
import os

logger = logging.getLogger(__name__)

class PdfExtractor:
    """Extract tables and data from PDF files using multiple methods"""
    
    def __init__(self):
        self.supported_extensions = ['.pdf']
    
    def extract_tables(self, file_path: str) -> Dict[str, Any]:
        """
        Extract all tables from a PDF file using multiple extraction methods
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dictionary containing extraction results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting PDF extraction for: {file_path}")
            
            # Try multiple extraction methods and combine results
            extraction_methods = [
                ('pdfplumber', self._extract_with_pdfplumber),
                ('tabula', self._extract_with_tabula),
                ('camelot', self._extract_with_camelot)
            ]
            
            all_tables = []
            warnings = []
            method_results = {}
            
            for method_name, extract_func in extraction_methods:
                try:
                    logger.info(f"Trying extraction method: {method_name}")
                    method_result = extract_func(file_path)
                    method_results[method_name] = method_result
                    
                    if method_result.get('success') and method_result.get('tables'):
                        # Add method info to each table
                        for table in method_result['tables']:
                            table['extraction_method'] = method_name
                        all_tables.extend(method_result['tables'])
                        logger.info(f"{method_name} extracted {len(method_result['tables'])} tables")
                    
                except Exception as e:
                    logger.warning(f"Method {method_name} failed: {str(e)}")
                    warnings.append(f"Extraction method {method_name} failed: {str(e)}")
            
            # Deduplicate and merge similar tables
            unique_tables = self._deduplicate_tables(all_tables)
            
            processing_time = time.time() - start_time
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(unique_tables, method_results)
            
            result = {
                'success': True,
                'tables': unique_tables,
                'table_count': len(unique_tables),
                'processing_time': processing_time,
                'accuracy_score': quality_metrics['accuracy_score'],
                'quality_metrics': quality_metrics,
                'warnings': warnings,
                'extraction_methods_used': list(method_results.keys())
            }
            
            logger.info(f"PDF extraction completed: {len(unique_tables)} tables in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to extract data from PDF file: {str(e)}',
                'details': {'error_type': type(e).__name__, 'file_path': file_path}
            }
    
    def _extract_with_pdfplumber(self, file_path: str) -> Dict[str, Any]:
        """Extract tables using pdfplumber"""
        try:
            tables_data = []
            
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    
                    for table_idx, table in enumerate(page_tables):
                        if table and len(table) > 0:
                            # Clean and process table
                            cleaned_table = self._clean_table_data(table)
                            if cleaned_table:
                                tables_data.append({
                                    'table_index': len(tables_data),
                                    'page': page_num + 1,
                                    'data': cleaned_table,
                                    'rows': len(cleaned_table),
                                    'columns': len(cleaned_table[0]) if cleaned_table else 0
                                })
            
            return {
                'success': True,
                'tables': tables_data,
                'method': 'pdfplumber'
            }
            
        except Exception as e:
            logger.error(f"PDFPlumber extraction failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _extract_with_tabula(self, file_path: str) -> Dict[str, Any]:
        """Extract tables using tabula-py"""
        try:
            tables_data = []
            
            # Read all tables from PDF
            dfs = tabula.read_pdf(file_path, pages='all', multiple_tables=True, silent=True)
            
            for idx, df in enumerate(dfs):
                if not df.empty:
                    # Convert DataFrame to list of lists
                    table_data = []
                    
                    # Add headers if they exist
                    if not df.columns.empty:
                        headers = [str(col) if col and str(col) != 'nan' else f'Column_{i}' 
                                 for i, col in enumerate(df.columns)]
                        table_data.append(headers)
                    
                    # Add data rows
                    for _, row in df.iterrows():
                        row_data = [str(cell) if cell and str(cell) != 'nan' else '' 
                                  for cell in row.values]
                        table_data.append(row_data)
                    
                    if table_data:
                        tables_data.append({
                            'table_index': idx,
                            'data': table_data,
                            'rows': len(table_data),
                            'columns': len(table_data[0]) if table_data else 0
                        })
            
            return {
                'success': True,
                'tables': tables_data,
                'method': 'tabula'
            }
            
        except Exception as e:
            logger.error(f"Tabula extraction failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _extract_with_camelot(self, file_path: str) -> Dict[str, Any]:
        """Extract tables using camelot-py"""
        try:
            tables_data = []
            
            # Extract tables using camelot
            tables = camelot.read_pdf(file_path, pages='all', flavor='lattice')
            
            for idx, table in enumerate(tables):
                df = table.df
                if not df.empty:
                    # Convert DataFrame to list of lists
                    table_data = []
                    
                    for _, row in df.iterrows():
                        row_data = [str(cell).strip() if cell and str(cell) != 'nan' else '' 
                                  for cell in row.values]
                        if any(cell for cell in row_data):  # Only add non-empty rows
                            table_data.append(row_data)
                    
                    if table_data:
                        tables_data.append({
                            'table_index': idx,
                            'data': table_data,
                            'rows': len(table_data),
                            'columns': len(table_data[0]) if table_data else 0,
                            'accuracy': float(table.accuracy) if hasattr(table, 'accuracy') else 0.0
                        })
            
            return {
                'success': True,
                'tables': tables_data,
                'method': 'camelot'
            }
            
        except Exception as e:
            logger.error(f"Camelot extraction failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _clean_table_data(self, table_data: List[List]) -> List[List[str]]:
        """Clean and normalize table data"""
        if not table_data:
            return []
        
        cleaned_table = []
        
        for row in table_data:
            if row is None:
                continue
                
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append('')
                else:
                    # Clean cell text
                    cell_text = str(cell).strip()
                    # Remove extra whitespace
                    cell_text = ' '.join(cell_text.split())
                    cleaned_row.append(cell_text)
            
            # Only add rows that have some content
            if any(cell for cell in cleaned_row):
                cleaned_table.append(cleaned_row)
        
        # Normalize column count
        if cleaned_table:
            max_cols = max(len(row) for row in cleaned_table)
            for row in cleaned_table:
                while len(row) < max_cols:
                    row.append('')
        
        return cleaned_table
    
    def _deduplicate_tables(self, tables: List[Dict]) -> List[Dict]:
        """Remove duplicate tables from different extraction methods"""
        if not tables:
            return []
        
        unique_tables = []
        
        for table in tables:
            is_duplicate = False
            table_data = table.get('data', [])
            
            # Check against existing tables
            for existing_table in unique_tables:
                existing_data = existing_table.get('data', [])
                
                # Simple similarity check based on dimensions and first few cells
                if (len(table_data) == len(existing_data) and 
                    len(table_data) > 0 and len(existing_data) > 0 and
                    len(table_data[0]) == len(existing_data[0])):
                    
                    # Check first few cells for similarity
                    similarity_score = self._calculate_table_similarity(table_data, existing_data)
                    if similarity_score > 0.8:  # 80% similarity threshold
                        is_duplicate = True
                        # Keep table with higher accuracy if available
                        if table.get('accuracy', 0) > existing_table.get('accuracy', 0):
                            # Replace existing table
                            unique_tables.remove(existing_table)
                            unique_tables.append(table)
                        break
            
            if not is_duplicate:
                unique_tables.append(table)
        
        # Re-index tables
        for i, table in enumerate(unique_tables):
            table['table_index'] = i
        
        return unique_tables
    
    def _calculate_table_similarity(self, table1: List[List], table2: List[List]) -> float:
        """Calculate similarity score between two tables"""
        if not table1 or not table2:
            return 0.0
        
        # Compare first 3 rows and first 3 columns for efficiency
        rows_to_check = min(3, len(table1), len(table2))
        cols_to_check = min(3, len(table1[0]) if table1 else 0, len(table2[0]) if table2 else 0)
        
        if rows_to_check == 0 or cols_to_check == 0:
            return 0.0
        
        matching_cells = 0
        total_cells = rows_to_check * cols_to_check
        
        for i in range(rows_to_check):
            for j in range(cols_to_check):
                if (i < len(table1) and j < len(table1[i]) and 
                    i < len(table2) and j < len(table2[i])):
                    
                    cell1 = table1[i][j].strip().lower()
                    cell2 = table2[i][j].strip().lower()
                    
                    if cell1 == cell2:
                        matching_cells += 1
        
        return matching_cells / total_cells if total_cells > 0 else 0.0
    
    def _calculate_quality_metrics(self, tables_data: List[Dict], method_results: Dict) -> Dict[str, Any]:
        """Calculate quality metrics for PDF extraction"""
        if not tables_data:
            return {
                'accuracy_score': 0.0,
                'method_success_rate': 0.0,
                'data_quality_issues': ['No tables extracted']
            }
        
        # Calculate overall accuracy based on individual method accuracies
        total_accuracy = 0.0
        accuracy_count = 0
        
        for table in tables_data:
            if 'accuracy' in table:
                total_accuracy += table['accuracy']
                accuracy_count += 1
        
        avg_accuracy = total_accuracy / accuracy_count if accuracy_count > 0 else 0.5
        
        # Method success rate
        successful_methods = sum(1 for result in method_results.values() if result.get('success'))
        method_success_rate = successful_methods / len(method_results) if method_results else 0.0
        
        # Data completeness
        total_cells = sum(table['rows'] * table['columns'] for table in tables_data)
        
        return {
            'accuracy_score': round(min(avg_accuracy, 1.0), 3),
            'method_success_rate': round(method_success_rate, 3),
            'total_tables': len(tables_data),
            'total_cells': total_cells,
            'extraction_methods': len(method_results)
        }
