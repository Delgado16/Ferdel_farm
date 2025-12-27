document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('mainSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const mainContent = document.getElementById('mainContent');

    // Función para inicializar la fecha actual
    function initializeCurrentDate() {
        const dateElement = document.getElementById('current-date');
        if (dateElement && !dateElement.textContent.trim()) {
            const now = new Date();
            const options = { day: '2-digit', month: '2-digit', year: 'numeric' };
            dateElement.textContent = now.toLocaleDateString('es-ES', options);
        }
    }

    // Inicializar fecha actual
    initializeCurrentDate();

    // Manejar el toggle del sidebar en móviles
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('show');
            }
            // Prevenir scroll del body cuando el sidebar está abierto en móvil
            document.body.style.overflow = sidebar.classList.contains('show') ? 'hidden' : '';
        });
    }

    // Manejar colapso/expansión del sidebar en desktop
    if (sidebarCollapse) {
        sidebarCollapse.addEventListener('click', function () {
            sidebar.classList.toggle('collapsed');
            if (mainContent) {
                mainContent.classList.toggle('expanded');
            }
        });
    }

    // Cerrar sidebar al hacer clic en el overlay
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function () {
            sidebar.classList.remove('show');
            this.classList.remove('show');
            document.body.style.overflow = '';
        });
    }

    // Manejar submenús
    const submenuToggleButtons = document.querySelectorAll('.submenu-toggle-btn');

    submenuToggleButtons.forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const targetId = this.getAttribute('href');
            if (!targetId) return;

            const targetSubmenu = document.querySelector(targetId);
            if (!targetSubmenu) return;

            const parent = this.closest('.has-submenu');
            if (!parent) return;

            // Alternar el submenú actual
            const isActive = parent.classList.contains('active');
            
            // Cerrar todos los submenús primero (opcional)
            // document.querySelectorAll('.submenu.show').forEach(menu => menu.classList.remove('show'));
            // document.querySelectorAll('.has-submenu.active').forEach(menu => menu.classList.remove('active'));
            
            // Alternar estado
            parent.classList.toggle('active');
            targetSubmenu.classList.toggle('show');

            // Rotar ícono del toggle
            const toggleIcon = this.querySelector('.submenu-toggle');
            if (toggleIcon) {
                toggleIcon.style.transform = parent.classList.contains('active') ? 'rotate(90deg)' : '';
            }
        });
    });

    // Inicializar submenús según la página actual
    function initializeActiveSubmenus() {
        const currentPath = window.location.pathname;
        
        // Para el menú de Catálogos
        if (currentPath.includes('/admin/usuarios') || 
            currentPath.includes('/admin/empresas') || 
            currentPath.includes('/admin/clientes') ||
            currentPath.includes('/admin/proveedores') ||
            currentPath.includes('/admin/unidades_medidas') ||
            currentPath.includes('/admin/categorias') ||
            currentPath.includes('/admin/metodos_pago') ||
            currentPath.includes('/admin/movimientos_inventario')) {
            
            const catalogosSubmenu = document.querySelector('#catalogos-submenu');
            if (catalogosSubmenu) {
                const catalogosMenu = catalogosSubmenu.closest('.has-submenu');
                catalogosSubmenu.classList.add('show');
                catalogosMenu.classList.add('active');
                
                // Rotar ícono
                const toggleIcon = catalogosMenu.querySelector('.submenu-toggle');
                if (toggleIcon) {
                    toggleIcon.style.transform = 'rotate(90deg)';
                }
            }
        }

        // Para el menú de Productos
        if (currentPath.includes('/admin/productos') || 
            currentPath.includes('/admin/tipo_productos') ||
            currentPath.includes('/admin/familias')) {
            
            const productosSubmenu = document.querySelector('#productos-submenu');
            if (productosSubmenu) {
                const productosMenu = productosSubmenu.closest('.has-submenu');
                productosSubmenu.classList.add('show');
                productosMenu.classList.add('active');
                
                // Rotar ícono
                const toggleIcon = productosMenu.querySelector('.submenu-toggle');
                if (toggleIcon) {
                    toggleIcon.style.transform = 'rotate(90deg)';
                }
            }
        }

        // Para el menú de Bodega
        if (currentPath.includes('/admin/bodega') || 
            currentPath.includes('/admin/inventario') ||
            currentPath.includes('/admin/movimientos')) {
            
            const bodegaSubmenu = document.querySelector('#bodega-submenu');
            if (bodegaSubmenu) {
                const bodegaMenu = bodegaSubmenu.closest('.has-submenu');
                bodegaSubmenu.classList.add('show');
                bodegaMenu.classList.add('active');
                
                // Rotar ícono
                const toggleIcon = bodegaMenu.querySelector('.submenu-toggle');
                if (toggleIcon) {
                    toggleIcon.style.transform = 'rotate(90deg)';
                }
            }
        }
    }

    // Inicializar submenús activos
    initializeActiveSubmenus();

    // Mejoras para formularios: validación y feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            // Solo aplicar validación si el formulario no tiene novalidate
            if (form.hasAttribute('novalidate')) {
                return;
            }

            // Validación básica de campos requeridos
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('is-invalid');

                    // Crear mensaje de error si no existe
                    const feedbackDiv = field.parentNode.querySelector('.invalid-feedback');
                    if (!feedbackDiv) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'invalid-feedback';
                        errorDiv.textContent = field.dataset.errorMessage || 'Este campo es obligatorio';
                        field.parentNode.appendChild(errorDiv);
                    } else {
                        feedbackDiv.style.display = 'block';
                    }
                } else {
                    field.classList.remove('is-invalid');
                    const feedbackDiv = field.parentNode.querySelector('.invalid-feedback');
                    if (feedbackDiv) {
                        feedbackDiv.style.display = 'none';
                    }
                }
            });

            if (!isValid) {
                e.preventDefault();
                e.stopPropagation();
                
                // Enfocar el primer campo inválido
                const firstInvalidField = form.querySelector('.is-invalid');
                if (firstInvalidField) {
                    firstInvalidField.focus();
                }
            }
        });

        // Limpiar errores al escribir
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('input', function () {
                if (this.classList.contains('is-invalid')) {
                    this.classList.remove('is-invalid');
                    const feedbackDiv = this.parentNode.querySelector('.invalid-feedback');
                    if (feedbackDiv) {
                        feedbackDiv.style.display = 'none';
                    }
                }
            });
        });
    });

    // Auto-ocultar mensajes de alerta después de 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Cerrar alertas al hacer clic en cualquier lugar
    document.addEventListener('click', function(e) {
        if (e.target.closest('.alert')) {
            const closeButton = e.target.closest('.alert').querySelector('.btn-close');
            if (closeButton) {
                const bsAlert = new bootstrap.Alert(e.target.closest('.alert'));
                bsAlert.close();
            }
        }
    });

    // Manejar el cierre del sidebar al hacer clic fuera de él en móvil
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 768 && sidebar && sidebar.classList.contains('show')) {
            if (!sidebar.contains(e.target) && 
                !sidebarToggle.contains(e.target) && 
                sidebarOverlay && 
                sidebarOverlay.classList.contains('show')) {
                
                sidebar.classList.remove('show');
                sidebarOverlay.classList.remove('show');
                document.body.style.overflow = '';
            }
        }
    });

    // Manejar tecla ESC para cerrar sidebar en móvil
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('show')) {
            sidebar.classList.remove('show');
            if (sidebarOverlay) {
                sidebarOverlay.classList.remove('show');
            }
            document.body.style.overflow = '';
        }
    });
});