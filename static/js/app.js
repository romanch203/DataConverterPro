// File Converter API - Frontend JavaScript
class FileConverterApp {
    constructor() {
        this.apiBaseUrl = '/api';
        this.init();
    }

    init() {
        this.bindEventListeners();
        this.checkApiStatus();
    }

    bindEventListeners() {
        // Single file form submission
        const singleFileForm = document.getElementById('singleFileForm');
        if (singleFileForm) {
            singleFileForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSingleFileConversion();
            });
        }

        // Batch file form submission
        const batchFileForm = document.getElementById('batchFileForm');
        if (batchFileForm) {
            batchFileForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleBatchFileConversion();
            });
        }

        // File input change handlers for validation
        const singleFileInput = document.getElementById('singleFile');
        if (singleFileInput) {
            singleFileInput.addEventListener('change', (e) => {
                this.validateFileInput(e.target);
            });
        }

        const batchFilesInput = document.getElementById('batchFiles');
        if (batchFilesInput) {
            batchFilesInput.addEventListener('change', (e) => {
                this.validateFileInput(e.target, true);
            });
        }
    }

    async checkApiStatus() {
        const statusElement = document.getElementById('apiStatus');
        if (!statusElement) return;

        try {
            const response = await fetch(`${this.apiBaseUrl}/status`);
            const data = await response.json();

            if (response.ok && data.status === 'operational') {
                statusElement.innerHTML = `
                    <i class="fas fa-check-circle text-success me-2"></i>
                    <span class="text-success">API Online - ${data.version}</span>
                    <small class="text-muted ms-2">(${data.supported_formats.length} formats supported)</small>
                `;
            } else {
                throw new Error('API not operational');
            }
        } catch (error) {
            statusElement.innerHTML = `
                <i class="fas fa-exclamation-circle text-danger me-2"></i>
                <span class="text-danger">API Offline</span>
                <small class="text-muted ms-2">(Unable to connect)</small>
            `;
        }
    }

    validateFileInput(input, multiple = false) {
        const files = multiple ? input.files : [input.files[0]];
        const allowedTypes = [
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/pdf',
            'image/png',
            'image/jpeg',
            'image/bmp',
            'image/tiff'
        ];
        const maxSize = 50 * 1024 * 1024; // 50MB
        
        let validFiles = [];
        let errors = [];

        Array.from(files).forEach(file => {
            if (!file) return;

            // Check file type
            const fileName = file.name.toLowerCase();
            const hasValidExtension = ['.docx', '.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff']
                .some(ext => fileName.endsWith(ext));
            
            if (!hasValidExtension) {
                errors.push(`${file.name}: Unsupported file format`);
                return;
            }

            // Check file size
            if (file.size > maxSize) {
                errors.push(`${file.name}: File too large (max 50MB)`);
                return;
            }

            if (file.size === 0) {
                errors.push(`${file.name}: File is empty`);
                return;
            }

            validFiles.push(file);
        });

        // Display validation feedback
        const feedbackElement = input.parentElement.querySelector('.validation-feedback') || 
                               this.createValidationFeedback(input);

        if (errors.length > 0) {
            feedbackElement.className = 'validation-feedback text-danger mt-2';
            feedbackElement.innerHTML = `
                <i class="fas fa-exclamation-triangle me-1"></i>
                ${errors.join('<br>')}
            `;
        } else if (validFiles.length > 0) {
            const fileList = validFiles.map(file => 
                `${file.name} (${this.formatFileSize(file.size)})`
            ).join(', ');
            
            feedbackElement.className = 'validation-feedback text-success mt-2';
            feedbackElement.innerHTML = `
                <i class="fas fa-check-circle me-1"></i>
                Ready to convert: ${fileList}
            `;
        } else {
            feedbackElement.innerHTML = '';
        }

        return validFiles.length > 0 && errors.length === 0;
    }

    createValidationFeedback(input) {
        const feedback = document.createElement('div');
        feedback.className = 'validation-feedback';
        input.parentElement.appendChild(feedback);
        return feedback;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async handleSingleFileConversion() {
        const fileInput = document.getElementById('singleFile');
        const convertBtn = document.getElementById('singleConvertBtn');
        
        if (!fileInput.files[0]) {
            this.showAlert('Please select a file to convert.', 'warning');
            return;
        }

        if (!this.validateFileInput(fileInput)) {
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        try {
            this.showProgress(true);
            this.setButtonLoading(convertBtn, true);

            const response = await fetch(`${this.apiBaseUrl}/convert`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok && result.success) {
                this.displayConversionResults([result], false);
                this.showAlert('File converted successfully!', 'success');
            } else {
                throw new Error(result.message || 'Conversion failed');
            }

        } catch (error) {
            console.error('Conversion error:', error);
            this.showAlert(`Conversion failed: ${error.message}`, 'danger');
            this.displayError(error.message);
        } finally {
            this.showProgress(false);
            this.setButtonLoading(convertBtn, false);
        }
    }

    async handleBatchFileConversion() {
        const filesInput = document.getElementById('batchFiles');
        const convertBtn = document.getElementById('batchConvertBtn');
        
        if (!filesInput.files.length) {
            this.showAlert('Please select files to convert.', 'warning');
            return;
        }

        if (!this.validateFileInput(filesInput, true)) {
            return;
        }

        const formData = new FormData();
        Array.from(filesInput.files).forEach(file => {
            formData.append('files', file);
        });

        try {
            this.showProgress(true);
            this.setButtonLoading(convertBtn, true);

            const response = await fetch(`${this.apiBaseUrl}/batch-convert`, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.ok && result.success) {
                this.displayBatchResults(result);
                this.showAlert(
                    `Batch conversion completed: ${result.successful_conversions}/${result.total_files} files converted successfully.`, 
                    result.failed_conversions > 0 ? 'warning' : 'success'
                );
            } else {
                throw new Error(result.message || 'Batch conversion failed');
            }

        } catch (error) {
            console.error('Batch conversion error:', error);
            this.showAlert(`Batch conversion failed: ${error.message}`, 'danger');
            this.displayError(error.message);
        } finally {
            this.showProgress(false);
            this.setButtonLoading(convertBtn, false);
        }
    }

    showProgress(show, text = 'Processing...') {
        const progressContainer = document.getElementById('progressContainer');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');

        if (show) {
            progressContainer.style.display = 'block';
            progressBar.style.width = '100%';
            progressText.textContent = text;
        } else {
            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressBar.style.width = '0%';
            }, 500);
        }
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            const originalText = button.innerHTML;
            button.setAttribute('data-original-text', originalText);
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                Processing...
            `;
        } else {
            button.disabled = false;
            const originalText = button.getAttribute('data-original-text');
            if (originalText) {
                button.innerHTML = originalText;
            }
        }
    }

    displayConversionResults(results, isBatch = false) {
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsContent = document.getElementById('resultsContent');

        resultsContainer.style.display = 'block';
        resultsContent.innerHTML = '';

        results.forEach((result, index) => {
            const resultCard = this.createResultCard(result, index, isBatch);
            resultsContent.appendChild(resultCard);
        });

        // Scroll to results
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    displayBatchResults(batchResult) {
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsContent = document.getElementById('resultsContent');

        resultsContainer.style.display = 'block';
        resultsContent.innerHTML = '';

        // Add batch summary
        const summaryCard = document.createElement('div');
        summaryCard.className = 'card mb-3';
        summaryCard.innerHTML = `
            <div class="card-header">
                <h6 class="mb-0">
                    <i class="fas fa-layer-group me-2"></i>
                    Batch Conversion Summary
                </h6>
            </div>
            <div class="card-body">
                <div class="row text-center">
                    <div class="col-md-3">
                        <div class="fs-4 fw-bold text-primary">${batchResult.total_files}</div>
                        <small class="text-muted">Total Files</small>
                    </div>
                    <div class="col-md-3">
                        <div class="fs-4 fw-bold text-success">${batchResult.successful_conversions}</div>
                        <small class="text-muted">Successful</small>
                    </div>
                    <div class="col-md-3">
                        <div class="fs-4 fw-bold text-danger">${batchResult.failed_conversions}</div>
                        <small class="text-muted">Failed</small>
                    </div>
                    <div class="col-md-3">
                        <div class="fs-4 fw-bold text-info">${batchResult.batch_id.split('_')[1].substring(0, 8)}</div>
                        <small class="text-muted">Batch ID</small>
                    </div>
                </div>
            </div>
        `;
        resultsContent.appendChild(summaryCard);

        // Add individual results
        batchResult.results.forEach((result, index) => {
            const resultCard = this.createBatchResultCard(result, index);
            resultsContent.appendChild(resultCard);
        });

        // Scroll to results
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    createResultCard(result, index, isBatch = false) {
        const card = document.createElement('div');
        card.className = `card mb-3 fade-in ${result.success ? 'success-state' : 'error-state'}`;

        const stats = result.conversion_stats || {};
        const quality = result.quality_metrics || {};

        card.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-center">
                <h6 class="mb-0">
                    <i class="fas ${result.success ? 'fa-check-circle text-success' : 'fa-exclamation-circle text-danger'} me-2"></i>
                    ${result.original_filename || `File ${index + 1}`}
                </h6>
                ${result.success ? `
                    <a href="${result.download_url}" class="btn btn-sm btn-outline-success download-btn">
                        <i class="fas fa-download me-1"></i>
                        Download CSV
                    </a>
                ` : ''}
            </div>
            <div class="card-body">
                ${result.success ? `
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <h6 class="text-muted mb-2">Conversion Statistics</h6>
                            <ul class="list-unstyled mb-0">
                                <li><i class="fas fa-table me-2 text-info"></i>Tables Found: <strong>${stats.tables_found || 0}</strong></li>
                                <li><i class="fas fa-list me-2 text-info"></i>Total Rows: <strong>${stats.total_rows || 0}</strong></li>
                                <li><i class="fas fa-columns me-2 text-info"></i>Total Columns: <strong>${stats.total_columns || 0}</strong></li>
                                <li><i class="fas fa-clock me-2 text-info"></i>Processing Time: <strong>${(stats.processing_time || 0).toFixed(2)}s</strong></li>
                            </ul>
                        </div>
                        <div class="col-md-6">
                            <h6 class="text-muted mb-2">Quality Metrics</h6>
                            <div class="d-flex flex-wrap gap-2">
                                ${this.createQualityBadge('Accuracy', stats.accuracy_score || 0)}
                                ${quality.completeness ? this.createQualityBadge('Completeness', quality.completeness) : ''}
                                ${quality.consistency ? this.createQualityBadge('Consistency', quality.consistency) : ''}
                            </div>
                        </div>
                    </div>
                    ${result.warnings && result.warnings.length > 0 ? `
                        <div class="alert alert-warning py-2">
                            <small>
                                <i class="fas fa-exclamation-triangle me-1"></i>
                                <strong>Warnings:</strong> ${result.warnings.join(', ')}
                            </small>
                        </div>
                    ` : ''}
                ` : `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>Error:</strong> ${result.error || result.message || 'Conversion failed'}
                    </div>
                `}
            </div>
        `;

        return card;
    }

    createBatchResultCard(result, index) {
        const card = document.createElement('div');
        card.className = `card mb-2 ${result.success ? 'success-state' : 'error-state'}`;

        card.innerHTML = `
            <div class="card-body py-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <i class="fas ${result.success ? 'fa-check-circle text-success' : 'fa-times-circle text-danger'} me-2"></i>
                        <strong>${result.filename}</strong>
                        ${result.success && result.stats ? `
                            <small class="text-muted ms-2">
                                (${result.stats.tables_found} tables, ${result.stats.total_rows} rows)
                            </small>
                        ` : ''}
                        ${!result.success ? `
                            <small class="text-danger ms-2">- ${result.error}</small>
                        ` : ''}
                    </div>
                    ${result.success ? `
                        <a href="${result.download_url}" class="btn btn-sm btn-outline-success">
                            <i class="fas fa-download me-1"></i>
                            Download
                        </a>
                    ` : ''}
                </div>
            </div>
        `;

        return card;
    }

    createQualityBadge(label, score) {
        const percentage = Math.round(score * 100);
        let badgeClass = 'low';
        
        if (percentage >= 80) badgeClass = 'high';
        else if (percentage >= 60) badgeClass = 'medium';

        return `
            <span class="quality-metric ${badgeClass}">
                ${label}: ${percentage}%
            </span>
        `;
    }

    displayError(message) {
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsContent = document.getElementById('resultsContent');

        resultsContainer.style.display = 'block';
        resultsContent.innerHTML = `
            <div class="card error-state">
                <div class="card-body">
                    <div class="alert alert-danger mb-0">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>Conversion Failed</strong>
                        <p class="mb-0 mt-2">${message}</p>
                    </div>
                </div>
            </div>
        `;

        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    showAlert(message, type = 'info') {
        // Create alert if it doesn't exist
        let alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) {
            alertContainer = document.createElement('div');
            alertContainer.id = 'alertContainer';
            alertContainer.className = 'position-fixed top-0 end-0 p-3';
            alertContainer.style.zIndex = '9999';
            document.body.appendChild(alertContainer);
        }

        // Create alert
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        alertContainer.appendChild(alert);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.classList.remove('show');
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 150);
            }
        }, 5000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new FileConverterApp();
});

// Utility functions for external use
window.FileConverterAPI = {
    // Function to programmatically convert a file
    convertFile: async function(file) {
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            return result;
        } catch (error) {
            throw new Error(`Conversion failed: ${error.message}`);
        }
    },

    // Function to download a converted file
    downloadFile: function(downloadUrl, filename = 'converted_data.csv') {
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }
};
