// Global application JavaScript for Business Management System

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeFeatherIcons();
    initializeTooltips();
    initializeAlerts();
    setupGlobalEventListeners();
});

// Initialize Feather icons
function initializeFeatherIcons() {
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
}

// Initialize Bootstrap tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Auto-hide alerts after 5 seconds
function initializeAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
}

// Setup global event listeners
function setupGlobalEventListeners() {
    // Form validation
    setupFormValidation();
    
    // Search functionality
    setupSearchFunctionality();
    
    // Loading states
    setupLoadingStates();
    
    // Confirmation dialogs
    setupConfirmationDialogs();
}

// Form validation
function setupFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
}

// Search functionality
function setupSearchFunctionality() {
    const searchInputs = document.querySelectorAll('[data-search-target]');
    
    searchInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            const target = document.querySelector(input.dataset.searchTarget);
            const searchTerm = input.value.toLowerCase();
            
            if (target) {
                const rows = target.querySelectorAll('tbody tr');
                rows.forEach(function(row) {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchTerm) ? '' : 'none';
                });
            }
        });
    });
}

// Loading states
function setupLoadingStates() {
    const loadingButtons = document.querySelectorAll('[data-loading]');
    
    loadingButtons.forEach(function(button) {
        button.addEventListener('click', function() {
            showLoading(button);
        });
    });
}

// Show loading state
function showLoading(element) {
    element.classList.add('loading');
    element.disabled = true;
    
    const originalText = element.innerHTML;
    element.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Chargement...';
    
    // Reset after form submission or 10 seconds
    setTimeout(function() {
        hideLoading(element, originalText);
    }, 10000);
}

// Hide loading state
function hideLoading(element, originalText) {
    element.classList.remove('loading');
    element.disabled = false;
    element.innerHTML = originalText;
    initializeFeatherIcons();
}

// Confirmation dialogs
function setupConfirmationDialogs() {
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    
    confirmButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            const message = button.dataset.confirm;
            if (!confirm(message)) {
                event.preventDefault();
                return false;
            }
        });
    });
}

// Utility functions
const Utils = {
    // Format currency
    formatCurrency: function(amount) {
        return new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: 'EUR'
        }).format(amount);
    },
    
    // Format date
    formatDate: function(date, options = {}) {
        const defaultOptions = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        };
        
        return new Intl.DateTimeFormat('fr-FR', {...defaultOptions, ...options}).format(new Date(date));
    },
    
    // Format time
    formatTime: function(date) {
        return new Intl.DateTimeFormat('fr-FR', {
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    },
    
    // Show toast notification
    showToast: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(function() {
            toast.remove();
        }, 5000);
    },
    
    // Debounce function
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Get CSRF token for AJAX requests
    getCSRFToken: function() {
        const csrfInput = document.querySelector('input[name="csrf_token"]');
        return csrfInput ? csrfInput.value : null;
    },
    
    // Make API request
    apiRequest: function(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            }
        };
        
        return fetch(url, {...defaultOptions, ...options})
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .catch(error => {
                console.error('API request failed:', error);
                this.showToast('Une erreur est survenue lors de la requête', 'danger');
                throw error;
            });
    }
};

// Table utilities
const TableUtils = {
    // Sort table by column
    sortTable: function(table, columnIndex, ascending = true) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const aText = a.cells[columnIndex].textContent.trim();
            const bText = b.cells[columnIndex].textContent.trim();
            
            // Try to parse as numbers first
            const aNum = parseFloat(aText.replace(/[^\d.-]/g, ''));
            const bNum = parseFloat(bText.replace(/[^\d.-]/g, ''));
            
            if (!isNaN(aNum) && !isNaN(bNum)) {
                return ascending ? aNum - bNum : bNum - aNum;
            }
            
            // Fall back to string comparison
            return ascending ? aText.localeCompare(bText) : bText.localeCompare(aText);
        });
        
        // Re-append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    },
    
    // Filter table rows
    filterTable: function(table, filterFunction) {
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            row.style.display = filterFunction(row) ? '' : 'none';
        });
    },
    
    // Export table to CSV
    exportTableToCSV: function(table, filename = 'export.csv') {
        const rows = Array.from(table.querySelectorAll('tr'));
        const csvContent = rows.map(row => {
            const cells = Array.from(row.querySelectorAll('th, td'));
            return cells.map(cell => {
                let text = cell.textContent.trim();
                // Escape quotes and wrap in quotes if necessary
                if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                    text = '"' + text.replace(/"/g, '""') + '"';
                }
                return text;
            }).join(',');
        }).join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    }
};

// Modal utilities
const ModalUtils = {
    // Show modal with dynamic content
    showModal: function(modalId, content) {
        const modal = document.getElementById(modalId);
        if (modal) {
            const modalBody = modal.querySelector('.modal-body');
            if (modalBody) {
                modalBody.innerHTML = content;
            }
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
        }
    },
    
    // Close modal
    closeModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    },
    
    // Show confirmation modal
    showConfirmation: function(title, message, callback) {
        const modalHtml = `
            <div class="modal fade" id="confirmationModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                            <button type="button" class="btn btn-primary" id="confirmButton">Confirmer</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal
        const existingModal = document.getElementById('confirmationModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = document.getElementById('confirmationModal');
        const confirmButton = modal.querySelector('#confirmButton');
        
        confirmButton.addEventListener('click', function() {
            callback();
            const bsModal = bootstrap.Modal.getInstance(modal);
            bsModal.hide();
        });
        
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        
        // Clean up when modal is hidden
        modal.addEventListener('hidden.bs.modal', function() {
            modal.remove();
        });
    }
};

// Form utilities
const FormUtils = {
    // Serialize form data
    serializeForm: function(form) {
        const formData = new FormData(form);
        const data = {};
        
        for (let [key, value] of formData.entries()) {
            if (data[key]) {
                // Handle multiple values
                if (Array.isArray(data[key])) {
                    data[key].push(value);
                } else {
                    data[key] = [data[key], value];
                }
            } else {
                data[key] = value;
            }
        }
        
        return data;
    },
    
    // Reset form
    resetForm: function(form) {
        form.reset();
        form.classList.remove('was-validated');
        
        // Clear custom validation messages
        const invalidFeedbacks = form.querySelectorAll('.invalid-feedback');
        invalidFeedbacks.forEach(feedback => feedback.style.display = 'none');
        
        // Remove validation classes
        const formControls = form.querySelectorAll('.form-control, .form-select');
        formControls.forEach(control => {
            control.classList.remove('is-valid', 'is-invalid');
        });
    },
    
    // Validate form field
    validateField: function(field, rules) {
        const value = field.value.trim();
        let isValid = true;
        let message = '';
        
        for (const rule of rules) {
            switch (rule.type) {
                case 'required':
                    if (!value) {
                        isValid = false;
                        message = rule.message || 'Ce champ est requis';
                    }
                    break;
                    
                case 'email':
                    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                    if (value && !emailRegex.test(value)) {
                        isValid = false;
                        message = rule.message || 'Adresse email invalide';
                    }
                    break;
                    
                case 'minLength':
                    if (value && value.length < rule.value) {
                        isValid = false;
                        message = rule.message || `Minimum ${rule.value} caractères`;
                    }
                    break;
                    
                case 'maxLength':
                    if (value && value.length > rule.value) {
                        isValid = false;
                        message = rule.message || `Maximum ${rule.value} caractères`;
                    }
                    break;
                    
                case 'pattern':
                    if (value && !rule.value.test(value)) {
                        isValid = false;
                        message = rule.message || 'Format invalide';
                    }
                    break;
            }
            
            if (!isValid) break;
        }
        
        // Update field appearance
        field.classList.toggle('is-valid', isValid);
        field.classList.toggle('is-invalid', !isValid);
        
        // Show/hide feedback
        const feedback = field.parentNode.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.textContent = message;
            feedback.style.display = isValid ? 'none' : 'block';
        }
        
        return isValid;
    }
};

// Export utilities for global use
window.Utils = Utils;
window.TableUtils = TableUtils;
window.ModalUtils = ModalUtils;
window.FormUtils = FormUtils;
