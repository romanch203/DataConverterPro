import os
import logging
from flask import Flask, request, jsonify, render_template, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
import tempfile
import shutil
from datetime import datetime
import traceback

from extractors.docx_extractor import DocxExtractor
from extractors.pdf_extractor import PdfExtractor
from extractors.image_extractor import ImageExtractor
from utils.data_processor import DataProcessor
from utils.validators import FileValidator

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Initialize extractors
docx_extractor = DocxExtractor()
pdf_extractor = PdfExtractor()
image_extractor = ImageExtractor()
data_processor = DataProcessor()
file_validator = FileValidator()

@app.route('/')
def index():
    """Main page with file upload interface"""
    return render_template('index.html')

@app.route('/api/docs')
def api_docs():
    """API documentation page"""
    return render_template('api_docs.html')

@app.route('/api/convert', methods=['POST'])
def convert_file():
    """
    Convert uploaded file to CSV format
    Returns JSON response with conversion results
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded',
                'message': 'Please select a file to upload'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected',
                'message': 'Please select a valid file'
            }), 400

        # Validate file
        validation_result = file_validator.validate_file(file)
        if not validation_result['valid']:
            return jsonify({
                'success': False,
                'error': 'Invalid file',
                'message': validation_result['message']
            }), 400

        # Generate unique filename
        file_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        file_extension = validation_result['extension']
        temp_filename = f"{file_id}{file_extension}"
        temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

        # Save uploaded file
        file.save(temp_filepath)
        logger.info(f"File saved: {temp_filepath}")

        # Extract data based on file type
        extraction_result = None
        if file_extension == '.docx':
            extraction_result = docx_extractor.extract_tables(temp_filepath)
        elif file_extension == '.pdf':
            extraction_result = pdf_extractor.extract_tables(temp_filepath)
        elif file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            extraction_result = image_extractor.extract_tables(temp_filepath)

        if not extraction_result or not extraction_result.get('success'):
            return jsonify({
                'success': False,
                'error': 'Extraction failed',
                'message': extraction_result.get('message', 'Failed to extract data from file'),
                'details': extraction_result.get('details', {})
            }), 500

        # Process and convert to CSV
        csv_result = data_processor.convert_to_csv(
            extraction_result['tables'],
            original_filename
        )

        if not csv_result.get('success'):
            return jsonify({
                'success': False,
                'error': 'CSV conversion failed',
                'message': csv_result.get('message', 'Failed to convert data to CSV'),
                'details': csv_result.get('details', {})
            }), 500

        # Save CSV file
        output_filename = f"{file_id}_converted.csv"
        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        with open(output_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            csvfile.write(csv_result['csv_content'])

        # Clean up temporary file
        try:
            os.remove(temp_filepath)
        except Exception as e:
            logger.warning(f"Failed to remove temp file: {e}")

        # Prepare response
        response_data = {
            'success': True,
            'message': 'File converted successfully',
            'file_id': file_id,
            'original_filename': original_filename,
            'download_url': f'/api/download/{file_id}',
            'conversion_stats': {
                'tables_found': extraction_result.get('table_count', 0),
                'total_rows': csv_result.get('row_count', 0),
                'total_columns': csv_result.get('column_count', 0),
                'accuracy_score': extraction_result.get('accuracy_score', 0.0),
                'processing_time': extraction_result.get('processing_time', 0.0)
            },
            'quality_metrics': extraction_result.get('quality_metrics', {}),
            'warnings': extraction_result.get('warnings', [])
        }

        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Conversion error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred during conversion',
            'details': str(e) if app.debug else 'Enable debug mode for details'
        }), 500

@app.route('/api/download/<file_id>')
def download_file(file_id):
    """Download converted CSV file"""
    try:
        output_filename = f"{file_id}_converted.csv"
        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        
        if not os.path.exists(output_filepath):
            return jsonify({
                'success': False,
                'error': 'File not found',
                'message': 'The requested file does not exist or has expired'
            }), 404

        return send_file(
            output_filepath,
            as_attachment=True,
            download_name=f"converted_{file_id}.csv",
            mimetype='text/csv'
        )

    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Download failed',
            'message': 'Failed to download file'
        }), 500

@app.route('/api/batch-convert', methods=['POST'])
def batch_convert():
    """
    Convert multiple files in batch
    """
    try:
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'error': 'No files uploaded',
                'message': 'Please select files to upload'
            }), 400

        results = []
        batch_id = str(uuid.uuid4())
        
        for i, file in enumerate(files):
            if file.filename == '':
                continue
                
            try:
                # Validate file
                validation_result = file_validator.validate_file(file)
                if not validation_result['valid']:
                    results.append({
                        'filename': file.filename,
                        'success': False,
                        'error': validation_result['message']
                    })
                    continue

                # Process individual file (similar to single file conversion)
                file_id = f"{batch_id}_{i}"
                original_filename = secure_filename(file.filename)
                file_extension = validation_result['extension']
                temp_filename = f"{file_id}{file_extension}"
                temp_filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)

                file.save(temp_filepath)

                # Extract and convert
                extraction_result = None
                if file_extension == '.docx':
                    extraction_result = docx_extractor.extract_tables(temp_filepath)
                elif file_extension == '.pdf':
                    extraction_result = pdf_extractor.extract_tables(temp_filepath)
                elif file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
                    extraction_result = image_extractor.extract_tables(temp_filepath)

                if extraction_result and extraction_result.get('success'):
                    csv_result = data_processor.convert_to_csv(
                        extraction_result['tables'],
                        original_filename
                    )
                    
                    if csv_result.get('success'):
                        output_filename = f"{file_id}_converted.csv"
                        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        
                        with open(output_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                            csvfile.write(csv_result['csv_content'])

                        results.append({
                            'filename': original_filename,
                            'success': True,
                            'file_id': file_id,
                            'download_url': f'/api/download/{file_id}',
                            'stats': {
                                'tables_found': extraction_result.get('table_count', 0),
                                'total_rows': csv_result.get('row_count', 0)
                            }
                        })
                    else:
                        results.append({
                            'filename': original_filename,
                            'success': False,
                            'error': 'CSV conversion failed'
                        })
                else:
                    results.append({
                        'filename': original_filename,
                        'success': False,
                        'error': 'Data extraction failed'
                    })

                # Clean up
                try:
                    os.remove(temp_filepath)
                except:
                    pass

            except Exception as e:
                logger.error(f"Batch conversion error for {file.filename}: {str(e)}")
                results.append({
                    'filename': file.filename,
                    'success': False,
                    'error': 'Processing failed'
                })

        successful_conversions = sum(1 for r in results if r['success'])
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'total_files': len(files),
            'successful_conversions': successful_conversions,
            'failed_conversions': len(files) - successful_conversions,
            'results': results
        }), 200

    except Exception as e:
        logger.error(f"Batch conversion error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Batch conversion failed',
            'message': str(e)
        }), 500

@app.route('/api/status')
def api_status():
    """API health check endpoint"""
    return jsonify({
        'status': 'operational',
        'version': '1.0.0',
        'supported_formats': ['.docx', '.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff'],
        'max_file_size': '50MB',
        'features': [
            'table_extraction',
            'ocr_processing',
            'batch_conversion',
            'quality_metrics',
            'data_validation'
        ]
    })

@app.errorhandler(413)
def too_large(e):
    return jsonify({
        'success': False,
        'error': 'File too large',
        'message': 'File size exceeds the maximum limit of 50MB'
    }), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Not found',
        'message': 'The requested resource was not found'
    }), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
