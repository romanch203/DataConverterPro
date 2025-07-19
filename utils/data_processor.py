import logging
import pandas as pd
import csv
import io
from typing import List, Dict, Any, Optional
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class DataProcessor:
    """Process and convert extracted table data to CSV format"""
    
    def __init__(self):
        pass
    
    def convert_to_csv(self, tables_data: List[Dict], original_filename: str) -> Dict[str, Any]:
        """
        Convert extracted table data to CSV format
        
        Args:
            tables_data: List of extracted table data
            original_filename: Name of original file
            
        Returns:
            Dictionary containing CSV conversion results
        """
        try:
            logger.info(f"Converting {len(tables_data)} tables to CSV")
            
            if not tables_data:
                return {
                    'success': False,
                    'message': 'No table data provided for conversion'
                }
            
            # Combine all tables into a single CSV or create separate sections
            combined_data = []
            table_info = []
            
            for i, table in enumerate(tables_data):
                table_data = table.get('data', [])
                if not table_data:
                    continue
                
                # Add table separator if multiple tables
                if len(tables_data) > 1 and combined_data:
                    combined_data.append([])  # Empty row separator
                    combined_data.append([f"=== TABLE {i + 1} ==="])
                    combined_data.append([])
                
                # Clean and validate table data
                cleaned_table = self._clean_table_data(table_data)
                
                # Add table headers if needed
                processed_table = self._process_table_headers(cleaned_table)
                
                # Add processed table to combined data
                combined_data.extend(processed_table)
                
                table_info.append({
                    'table_index': i,
                    'rows': len(processed_table),
                    'columns': len(processed_table[0]) if processed_table else 0,
                    'has_headers': self._has_headers(processed_table)
                })
            
            if not combined_data:
                return {
                    'success': False,
                    'message': 'No valid data found in tables'
                }
            
            # Convert to CSV string
            csv_content = self._generate_csv_content(combined_data)
            
            # Calculate statistics
            total_rows = len(combined_data)
            total_columns = max(len(row) for row in combined_data) if combined_data else 0
            
            result = {
                'success': True,
                'csv_content': csv_content,
                'row_count': total_rows,
                'column_count': total_columns,
                'table_count': len(tables_data),
                'table_info': table_info,
                'conversion_stats': {
                    'original_filename': original_filename,
                    'conversion_timestamp': datetime.now().isoformat(),
                    'data_validation': self._validate_csv_data(combined_data)
                }
            }
            
            logger.info(f"CSV conversion completed: {total_rows} rows x {total_columns} columns")
            return result
            
        except Exception as e:
            logger.error(f"CSV conversion failed: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to convert data to CSV: {str(e)}',
                'details': {'error_type': type(e).__name__}
            }
    
    def _clean_table_data(self, table_data: List[List[str]]) -> List[List[str]]:
        """
        Clean and normalize table data
        
        Args:
            table_data: Raw table data
            
        Returns:
            Cleaned table data
        """
        if not table_data:
            return []
        
        cleaned_data = []
        
        for row in table_data:
            if not row:
                continue
            
            cleaned_row = []
            for cell in row:
                # Clean cell content
                cleaned_cell = self._clean_cell_content(cell)
                cleaned_row.append(cleaned_cell)
            
            # Only add rows with some content
            if any(cell.strip() for cell in cleaned_row):
                cleaned_data.append(cleaned_row)
        
        # Ensure all rows have the same number of columns
        if cleaned_data:
            max_columns = max(len(row) for row in cleaned_data)
            for row in cleaned_data:
                while len(row) < max_columns:
                    row.append('')
        
        return cleaned_data
    
    def _clean_cell_content(self, cell: str) -> str:
        """
        Clean individual cell content
        
        Args:
            cell: Raw cell content
            
        Returns:
            Cleaned cell content
        """
        if not cell:
            return ''
        
        # Convert to string if not already
        cell = str(cell)
        
        # Remove extra whitespace
        cell = ' '.join(cell.split())
        
        # Remove or replace problematic characters
        cell = cell.replace('\x00', '')  # Null bytes
        cell = cell.replace('\ufeff', '')  # BOM
        cell = cell.replace('\r', ' ')  # Carriage returns
        
        # Normalize quotes
        cell = cell.replace('"', '""')  # Escape quotes for CSV
        
        # Handle numeric data
        cell = self._normalize_numeric_data(cell)
        
        return cell.strip()
    
    def _normalize_numeric_data(self, cell: str) -> str:
        """
        Normalize numeric data in cells
        
        Args:
            cell: Cell content
            
        Returns:
            Normalized cell content
        """
        if not cell:
            return cell
        
        # Remove common currency symbols and thousands separators
        numeric_cell = re.sub(r'[$£€¥₹,]', '', cell)
        
        # Handle percentage values
        if '%' in cell:
            try:
                numeric_value = float(numeric_cell.replace('%', '').strip())
                return f"{numeric_value}%"
            except ValueError:
                pass
        
        # Try to identify and format numbers
        try:
            # Check if it's a float
            if '.' in numeric_cell:
                float_value = float(numeric_cell)
                # Keep reasonable precision
                if float_value.is_integer():
                    return str(int(float_value))
                else:
                    return f"{float_value:.6g}"  # Up to 6 significant digits
            else:
                # Check if it's an integer
                int_value = int(numeric_cell)
                return str(int_value)
        except ValueError:
            # Not a number, return as is
            return cell
    
    def _process_table_headers(self, table_data: List[List[str]]) -> List[List[str]]:
        """
        Process and validate table headers
        
        Args:
            table_data: Cleaned table data
            
        Returns:
            Table data with processed headers
        """
        if not table_data:
            return []
        
        # Check if first row looks like headers
        if self._has_headers(table_data):
            # Clean up headers
            headers = table_data[0]
            cleaned_headers = []
            
            for i, header in enumerate(headers):
                if not header or header.strip() == '':
                    cleaned_headers.append(f'Column_{i + 1}')
                else:
                    # Clean header text
                    clean_header = re.sub(r'[^\w\s-]', '', header.strip())
                    clean_header = re.sub(r'\s+', '_', clean_header)
                    cleaned_headers.append(clean_header or f'Column_{i + 1}')
            
            # Ensure unique headers
            unique_headers = []
            header_counts = {}
            
            for header in cleaned_headers:
                if header in header_counts:
                    header_counts[header] += 1
                    unique_header = f"{header}_{header_counts[header]}"
                else:
                    header_counts[header] = 0
                    unique_header = header
                unique_headers.append(unique_header)
            
            processed_data = [unique_headers] + table_data[1:]
            return processed_data
        else:
            # Add generic headers if none detected
            if table_data:
                num_columns = len(table_data[0])
                headers = [f'Column_{i + 1}' for i in range(num_columns)]
                return [headers] + table_data
        
        return table_data
    
    def _has_headers(self, table_data: List[List[str]]) -> bool:
        """
        Determine if the first row contains headers
        
        Args:
            table_data: Table data to analyze
            
        Returns:
            True if first row appears to be headers
        """
        if not table_data or len(table_data) < 2:
            return False
        
        first_row = table_data[0]
        second_row = table_data[1] if len(table_data) > 1 else []
        
        # Check for header indicators
        header_indicators = 0
        
        for i, cell in enumerate(first_row):
            if not cell:
                continue
            
            # Headers are typically text
            if not re.match(r'^[\d.,%-]+$', cell.strip()):
                header_indicators += 1
            
            # Compare with second row if available
            if i < len(second_row) and second_row[i]:
                first_is_text = not re.match(r'^[\d.,%-]+$', cell.strip())
                second_is_number = re.match(r'^[\d.,%-]+$', second_row[i].strip())
                
                if first_is_text and second_is_number:
                    header_indicators += 1
        
        # Consider it headers if more than half the cells look like headers
        return header_indicators > len(first_row) * 0.5
    
    def _generate_csv_content(self, table_data: List[List[str]]) -> str:
        """
        Generate CSV content from table data
        
        Args:
            table_data: Processed table data
            
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        
        for row in table_data:
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
    
    def _validate_csv_data(self, table_data: List[List[str]]) -> Dict[str, Any]:
        """
        Validate CSV data quality
        
        Args:
            table_data: Table data to validate
            
        Returns:
            Validation results
        """
        if not table_data:
            return {
                'valid': False,
                'issues': ['No data to validate']
            }
        
        issues = []
        warnings = []
        
        # Check for empty rows
        empty_rows = sum(1 for row in table_data if not any(cell.strip() for cell in row))
        if empty_rows > 0:
            warnings.append(f'{empty_rows} empty rows found')
        
        # Check for inconsistent column counts
        column_counts = [len(row) for row in table_data]
        if len(set(column_counts)) > 1:
            issues.append(f'Inconsistent column counts: {set(column_counts)}')
        
        # Check for very sparse data
        total_cells = sum(len(row) for row in table_data)
        empty_cells = sum(sum(1 for cell in row if not cell.strip()) for row in table_data)
        
        if total_cells > 0:
            sparsity = empty_cells / total_cells
            if sparsity > 0.8:
                warnings.append(f'Data is very sparse: {sparsity:.1%} empty cells')
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'stats': {
                'total_rows': len(table_data),
                'total_cells': total_cells,
                'empty_cells': empty_cells,
                'sparsity': empty_cells / total_cells if total_cells > 0 else 0
            }
        }
