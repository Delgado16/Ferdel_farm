document.addEventListener('DOMContentLoaded', function () {
    // Elementos del sidebar
    const sidebar = document.getElementById('mainSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarCollapse = document.getElementById('sidebarCollapse');
    const mainContent = document.getElementById('mainContent');

    // Manejar el toggle del sidebar en móviles
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('show');
            }
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
        });
    }

    // Manejar submenús
    const submenuToggleButtons = document.querySelectorAll('.submenu-toggle-btn');

    submenuToggleButtons.forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const targetId = this.getAttribute('href');
            if (!targetId || targetId === '#') return;

            const targetSubmenu = document.querySelector(targetId);
            const parent = this.closest('.has-submenu');

            if (targetSubmenu && parent) {
                // Alternar el submenú actual
                const isActive = parent.classList.contains('active');
                
                // Cerrar otros submenús si es necesario
                if (!isActive) {
                    document.querySelectorAll('.has-submenu.active').forEach(activeMenu => {
                        if (activeMenu !== parent) {
                            activeMenu.classList.remove('active');
                            const activeSubmenu = activeMenu.querySelector('.submenu');
                            if (activeSubmenu) {
                                activeSubmenu.classList.remove('show');
                            }
                        }
                    });
                }
                
                parent.classList.toggle('active');
                targetSubmenu.classList.toggle('show');
            }
        });
    });

    // Inicializar submenús según la página actual
    function initializeActiveSubmenus() {
        const currentPath = window.location.pathname;
        
        // Para el menú de Ventas
        if (currentPath.includes('/admin/ventas')) {
            activateSubmenu('#ventas-submenu');
        }
        
        // Para el menú de Compras
        if (currentPath.includes('/admin/compras')) {
            activateSubmenu('#compras-submenu');
        }
        
        // Para el menú de Catálogos
        if (currentPath.includes('/admin/usuarios') || 
            currentPath.includes('/admin/empresas') || 
            currentPath.includes('/admin/clientes') ||
            currentPath.includes('/admin/proveedores') ||
            currentPath.includes('/admin/unidades') ||
            currentPath.includes('/admin/categorias') ||
            currentPath.includes('/admin/metodos') ||
            currentPath.includes('/admin/movimientos')) {
            activateSubmenu('#catalogos-submenu');
        }
        
        // Para el menú de Productos
        if (currentPath.includes('/admin/productos')) {
            activateSubmenu('#productos-submenu');
        }
        
        // Para el menú de Bodega
        if (currentPath.includes('/admin/bodega') || 
            currentPath.includes('/admin/inventario') ||
            currentPath.includes('/admin/historial')) {
            activateSubmenu('#bodega-submenu');
        }
        
        // Para el menú de Herramientas
        if (currentPath.includes('/admin/bitacora')) {
            activateSubmenu('#herramientas-submenu');
        }
    }

    function activateSubmenu(submenuId) {
        const submenu = document.querySelector(submenuId);
        if (submenu) {
            const menu = submenu.closest('.has-submenu');
            submenu.classList.add('show');
            if (menu) {
                menu.classList.add('active');
            }
        }
    }

    // Ejecutar inicialización
    initializeActiveSubmenus();

    // Mejoras para formularios: validación y feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        // Remover validación automática que causa problemas
        // Esta validación se manejará en el backend
    });

    // Auto-ocultar mensajes de alerta después de 5 segundos
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.parentNode) {
                const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Actualizar fecha actual
    function updateCurrentDate() {
        const dateElement = document.getElementById('current-date');
        if (dateElement) {
            const now = new Date();
            const formattedDate = now.toLocaleDateString('es-ES', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric'
            });
            dateElement.textContent = formattedDate;
        }
    }
    
    updateCurrentDate();

    // Cerrar sidebar al hacer clic fuera en móvil
    document.addEventListener('click', function (e) {
        if (window.innerWidth <= 767.98) {
            if (sidebar && sidebar.classList.contains('show') && 
                !sidebar.contains(e.target) && 
                e.target !== sidebarToggle && 
                !sidebarToggle.contains(e.target)) {
                sidebar.classList.remove('show');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('show');
                }
            }
        }
    });
});