// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    // Inicialización
    initTheme();
    initSidebar();
    initSubmenus();
    initDateTime();
    initPasswordToggle();
    initFormValidation();
    initAutoCloseAlerts();
    initMobileGestures();
    initKeyboardShortcuts();
    
    // Mostrar hora actual en tiempo real
    if (document.getElementById('currentTime')) {
        updateCurrentTime();
        setInterval(updateCurrentTime, 60000); // Actualizar cada minuto
    }
});

// ===== FUNCIONES PRINCIPALES =====

// Tema claro/oscuro
function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    // Aplicar tema guardado
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
    
    if (themeToggle) {
        updateThemeToggle(savedTheme);
        
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            // Cambiar tema
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            
            // Actualizar botón
            updateThemeToggle(newTheme);
            
            // Animación suave
            document.body.style.transition = 'background-color 0.3s ease';
            setTimeout(() => {
                document.body.style.transition = '';
            }, 300);
        });
    }
}

function updateThemeToggle(theme) {
    const themeToggle = document.getElementById('themeToggle');
    if (!themeToggle) return;
    
    const icon = themeToggle.querySelector('i');
    const text = themeToggle.querySelector('span');
    
    if (theme === 'dark') {
        icon.className = 'bi bi-sun';
        text.textContent = 'Modo Claro';
        themeToggle.classList.remove('btn-outline-secondary');
        themeToggle.classList.add('btn-outline-light');
    } else {
        icon.className = 'bi bi-moon';
        text.textContent = 'Modo Oscuro';
        themeToggle.classList.remove('btn-outline-light');
        themeToggle.classList.add('btn-outline-secondary');
    }
}

// Sidebar
function initSidebar() {
    const sidebar = document.getElementById('appSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mobileToggle = document.getElementById('mobileToggle');
    const overlay = document.getElementById('sidebarOverlay');
    
    // Toggle sidebar en desktop
    if (sidebarToggle && sidebar) {
        const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        
        if (sidebarCollapsed) {
            sidebar.classList.add('collapsed');
        }
        
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
            
            // Animación del ícono
            const icon = this.querySelector('i');
            icon.style.transition = 'transform 0.3s ease';
            
            if (sidebar.classList.contains('collapsed')) {
                icon.className = 'bi bi-chevron-right';
            } else {
                icon.className = 'bi bi-chevron-left';
            }
        });
    }
    
    // Toggle sidebar en móvil
    if (mobileToggle && overlay && sidebar) {
        mobileToggle.addEventListener('click', function() {
            sidebar.classList.add('show');
            overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        });
        
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('show');
            this.classList.remove('show');
            document.body.style.overflow = '';
        });
        
        // Cerrar sidebar al hacer clic en un enlace en móvil
        const navLinks = sidebar.querySelectorAll('.nav-link, .submenu-link');
        navLinks.forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth < 992) {
                    sidebar.classList.remove('show');
                    overlay.classList.remove('show');
                    document.body.style.overflow = '';
                }
            });
        });
    }
    
    // Cerrar sidebar al redimensionar
    window.addEventListener('resize', function() {
        const overlay = document.getElementById('sidebarOverlay');
        const sidebar = document.getElementById('appSidebar');
        
        if (window.innerWidth >= 992 && overlay && sidebar) {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    });
}

// Submenús
function initSubmenus() {
    const submenuToggles = document.querySelectorAll('.submenu-toggle');
    
    submenuToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            
            const parent = this.closest('.has-submenu');
            const submenu = parent.querySelector('.submenu');
            
            // Cerrar otros submenús en el mismo nivel
            const siblingSubmenus = parent.parentElement.querySelectorAll('.has-submenu.active');
            siblingSubmenus.forEach(sibling => {
                if (sibling !== parent) {
                    sibling.classList.remove('active');
                    sibling.querySelector('.submenu').classList.remove('show');
                }
            });
            
            // Alternar submenu actual
            parent.classList.toggle('active');
            submenu.classList.toggle('show');
        });
    });
    
    // Ajustar submenús al colapsar sidebar
    const sidebar = document.getElementById('appSidebar');
    if (sidebar) {
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.attributeName === 'class' && 
                    sidebar.classList.contains('collapsed')) {
                    // Cerrar todos los submenús al colapsar
                    document.querySelectorAll('.has-submenu.active').forEach(item => {
                        item.classList.remove('active');
                        item.querySelector('.submenu')?.classList.remove('show');
                    });
                }
            });
        });
        
        observer.observe(sidebar, { attributes: true });
    }
}

// Fecha y hora
function initDateTime() {
    const dateElement = document.getElementById('currentDate');
    const timeElement = document.getElementById('currentTime');
    
    if (dateElement && !dateElement.textContent.trim()) {
        const now = new Date();
        const options = { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric',
            timeZone: 'America/Guatemala'
        };
        dateElement.textContent = now.toLocaleDateString('es-GT', options);
    }
}

function updateCurrentTime() {
    const timeElement = document.getElementById('currentTime');
    if (timeElement) {
        const now = new Date();
        const hours = now.getHours().toString().padStart(2, '0');
        const minutes = now.getMinutes().toString().padStart(2, '0');
        timeElement.textContent = `${hours}:${minutes}`;
    }
}

// Toggle de contraseña
function initPasswordToggle() {
    const toggleBtn = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('password');
    
    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', function() {
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            
            const icon = this.querySelector('i');
            icon.className = type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
        });
    }
}

// Validación de formularios
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
            
            // Mostrar loading en botón submit
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && form.checkValidity()) {
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Procesando...
                `;
                submitBtn.disabled = true;
                
                // Restaurar después de 3 segundos (fallback)
                setTimeout(() => {
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }, 3000);
            }
        }, false);
    });
}

// Auto-cierre de alertas
function initAutoCloseAlerts() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.parentNode) {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }
        }, 5000);
        
        // Animación al cerrar
        alert.addEventListener('closed.bs.alert', function() {
            this.style.transition = 'opacity 0.3s ease';
            this.style.opacity = '0';
        });
    });
}

// Gestos para móvil
function initMobileGestures() {
    if (window.innerWidth >= 992) return;
    
    let touchStartX = 0;
    let touchEndX = 0;
    
    document.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        const swipeDistance = touchEndX - touchStartX;
        
        const sidebar = document.getElementById('appSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        
        // Swipe derecho para abrir sidebar (si se inicia desde el borde izquierdo)
        if (touchStartX < 20 && swipeDistance > 50 && sidebar && !sidebar.classList.contains('show')) {
            sidebar.classList.add('show');
            if (overlay) overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
        
        // Swipe izquierdo para cerrar sidebar
        if (sidebar && sidebar.classList.contains('show') && swipeDistance < -50) {
            sidebar.classList.remove('show');
            if (overlay) overlay.classList.remove('show');
            document.body.style.overflow = '';
        }
    }, { passive: true });
}

// Atajos de teclado
function initKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + B: Alternar sidebar
        if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
            e.preventDefault();
            const sidebarToggle = document.getElementById('sidebarToggle');
            const mobileToggle = document.getElementById('mobileToggle');
            
            if (window.innerWidth >= 992 && sidebarToggle) {
                sidebarToggle.click();
            } else if (mobileToggle) {
                mobileToggle.click();
            }
        }
        
        // Escape: Cerrar sidebar móvil
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('appSidebar');
            const overlay = document.getElementById('sidebarOverlay');
            
            if (sidebar && sidebar.classList.contains('show')) {
                sidebar.classList.remove('show');
                if (overlay) overlay.classList.remove('show');
                document.body.style.overflow = '';
            }
        }
    });
}

// ===== FUNCIONES UTILITARIAS =====

// Loading overlay
function showLoading(message = 'Cargando...') {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <p class="text-muted">${message}</p>
        </div>
    `;
    document.body.appendChild(overlay);
    return overlay;
}

function hideLoading(overlay) {
    if (overlay && overlay.parentNode) {
        overlay.style.transition = 'opacity 0.3s ease';
        overlay.style.opacity = '0';
        setTimeout(() => {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
        }, 300);
    }
}

// Notificaciones toast
function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toastContainer') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-bg-${type} border-0 fade`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${getToastIcon(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', function() {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    });
}

function getToastIcon(type) {
    const icons = {
        success: 'bi-check-circle-fill',
        danger: 'bi-exclamation-circle-fill',
        warning: 'bi-exclamation-triangle-fill',
        info: 'bi-info-circle-fill'
    };
    return icons[type] || 'bi-info-circle-fill';
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
}

// Confirmación de acciones
function confirmAction(message, callback) {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.setAttribute('tabindex', '-1');
    modal.setAttribute('aria-hidden', 'true');
    
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Confirmar acción</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p>${message}</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="button" class="btn btn-primary" id="confirmBtn">Confirmar</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    modal.querySelector('#confirmBtn').addEventListener('click', function() {
        bsModal.hide();
        if (callback) callback();
    });
    
    modal.addEventListener('hidden.bs.modal', function() {
        if (modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    });
}

// Formatear números
function formatNumber(number, decimals = 2) {
    return new Intl.NumberFormat('es-GT', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(number);
}

function formatCurrency(amount, currency = 'GTQ') {
    return new Intl.NumberFormat('es-GT', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(amount);
}

// Formatear fechas
function formatDate(date, format = 'short') {
    const d = new Date(date);
    const options = {
        short: { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric' 
        },
        long: { 
            day: '2-digit', 
            month: 'long', 
            year: 'numeric' 
        },
        datetime: {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }
    };
    
    return d.toLocaleDateString('es-GT', options[format] || options.short);
}

// Detectar dispositivo
function isMobile() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function isTablet() {
    return window.matchMedia('(min-width: 769px) and (max-width: 1024px)').matches;
}

function isDesktop() {
    return window.matchMedia('(min-width: 1025px)').matches;
}

// Copiar al portapapeles
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copiado al portapapeles', 'success');
        return true;
    } catch (err) {
        console.error('Error al copiar:', err);
        showToast('Error al copiar', 'danger');
        return false;
    }
}

// Exportar funciones globalmente
window.appUtils = {
    showLoading,
    hideLoading,
    showToast,
    confirmAction,
    formatNumber,
    formatCurrency,
    formatDate,
    copyToClipboard,
    isMobile,
    isTablet,
    isDesktop
};

// Inicializar tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl, {
        trigger: 'hover'
    });
});

// Inicializar popovers
const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
});