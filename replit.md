# File Converter API

## Overview

This is a Flask-based web application that converts various file formats (DOCX, PDF, images) containing statistical data into CSV format. The application uses multiple extraction methods and OCR capabilities to achieve high accuracy in data extraction from tables within documents and images.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask web framework with Python
- **Structure**: Modular design with separate packages for extractors and utilities
- **File Processing**: Multi-method extraction approach for different file types
- **API Design**: RESTful API endpoints with both web interface and programmatic access

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask
- **Styling**: Bootstrap 5 with dark theme
- **JavaScript**: Vanilla JavaScript for form handling and API interactions
- **UI Components**: File upload forms, progress indicators, and result displays

## Key Components

### File Extractors (`extractors/`)
- **DocxExtractor**: Extracts tables from Microsoft Word documents using python-docx
- **PdfExtractor**: Multi-method PDF table extraction using pdfplumber, tabula, and camelot
- **ImageExtractor**: OCR-based table extraction from images using OpenCV, Tesseract, and PIL

### Utilities (`utils/`)
- **DataProcessor**: Converts extracted table data to CSV format with data cleaning
- **FileValidator**: Validates uploaded files for security and format compliance

### Web Interface
- **Main Interface**: File upload form with drag-and-drop functionality
- **API Documentation**: Comprehensive API documentation with examples
- **Result Display**: Real-time progress tracking and downloadable results

## Data Flow

1. **File Upload**: Users upload files through web interface or API
2. **Validation**: Files are validated for type, size, and security
3. **Processing**: Appropriate extractor processes the file based on type
4. **Data Extraction**: Tables and structured data are extracted using multiple methods
5. **Data Processing**: Extracted data is cleaned and formatted
6. **CSV Generation**: Processed data is converted to CSV format
7. **Result Delivery**: CSV files are made available for download

## External Dependencies

### Core Libraries
- **Flask**: Web framework and routing
- **python-docx**: DOCX file processing
- **pdfplumber/tabula/camelot**: PDF table extraction
- **OpenCV**: Image processing and computer vision
- **pytesseract**: OCR text recognition
- **pandas**: Data manipulation and CSV generation
- **PIL (Pillow)**: Image handling

### Frontend Dependencies
- **Bootstrap 5**: UI framework with dark theme
- **Font Awesome**: Icon library
- **Prism.js**: Code syntax highlighting

## Deployment Strategy

### Configuration
- Environment-based configuration for secrets and paths
- Configurable file size limits (50MB default)
- Separate upload and output directories
- Proxy-aware deployment with ProxyFix middleware

### File Handling
- Secure filename handling with werkzeug
- Temporary file management for processing
- Automatic cleanup of processed files
- Support for both single file and batch processing

### Error Handling
- Comprehensive logging throughout the application
- Graceful error handling with user-friendly messages
- Multiple extraction method fallbacks for reliability
- Input validation and sanitization

### Scalability Considerations
- Modular extractor design allows for easy addition of new file types
- Stateless design suitable for horizontal scaling
- Separate processing and storage concerns
- API-first design enables multiple client interfaces