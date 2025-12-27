document.addEventListener('DOMContentLoaded', function() {
    // ========== ELEMENTOS PRINCIPALES ==========
    const sidebar = document.getElementById('mainSidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    const overlay = document.getElementById('sidebarOverlay');
    const mainContent = document.getElementById('mainContent');
    
    // ========== FUNCIONES BÁSICAS ==========
    
    // 1. Verificar si es móvil
    function isMobile() {
        return window.innerWidth < 992;
    }
    
    // 2. Abrir/cerrar sidebar en móvil
    function toggleMobileSidebar() {
        const isOpening = !sidebar.classList.contains('show');
        
        sidebar.classList.toggle('show');
        overlay.classList.toggle('show');
        
        // Prevenir scroll del body cuando sidebar está abierto
        if (isOpening) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
    }
    
    // 3. Colapsar/expandir sidebar en desktop
    function toggleDesktopSidebar() {
        sidebar.classList.toggle('collapsed');
        mainContent.classList.toggle('expanded');
        
        // Guardar preferencia
        const isCollapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', isCollapsed);
        
        // Cerrar todos los submenús cuando se colapsa
        if (isCollapsed) {
            closeAllSubmenus();
        }
    }
    
    // 4. Cerrar todos los submenús
    function closeAllSubmenus() {
        const openSubmenus = document.querySelectorAll('.submenu.show');
        const activeParents = document.querySelectorAll('.has-submenu.active');
        
        openSubmenus.forEach(menu => menu.classList.remove('show'));
        activeParents.forEach(parent => {
            parent.classList.remove('active');
            const icon = parent.querySelector('.submenu-toggle');
            if (icon) icon.style.transform = '';
        });
    }
    
    // ========== EVENT LISTENERS PRINCIPALES ==========
    
    // 1. Botón hamburguesa
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (isMobile()) {
                toggleMobileSidebar();
            } else {
                toggleDesktopSidebar();
            }
        });
    }
    
    // 2. Overlay para cerrar en móvil
    if (overlay) {
        overlay.addEventListener('click', function() {
            if (isMobile() && sidebar.classList.contains('show')) {
                toggleMobileSidebar();
            }
        });
    }
    
    // ========== MANEJO DE SUBMENÚS ==========
    
    function setupSubmenus() {
        const toggleButtons = document.querySelectorAll('.submenu-toggle-btn');
        
        toggleButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const targetId = this.getAttribute('href');
                if (!targetId || targetId === '#') return;
                
                const submenu = document.querySelector(targetId);
                const parent = this.closest('.has-submenu');
                if (!submenu || !parent) return;
                
                // En móvil: si el sidebar está cerrado, abrirlo primero
                if (isMobile() && !sidebar.classList.contains('show')) {
                    toggleMobileSidebar();
                    setTimeout(() => toggleSubmenu(parent, submenu, this), 300);
                    return;
                }
                
                toggleSubmenu(parent, submenu, this);
            });
        });
        
        function toggleSubmenu(parent, submenu, button) {
            const isOpening = !parent.classList.contains('active');
            
            // En desktop: si estamos abriendo un submenú y el sidebar está colapsado, expandirlo
            if (!isMobile() && isOpening && sidebar.classList.contains('collapsed')) {
                sidebar.classList.remove('collapsed');
                mainContent.classList.remove('expanded');
                localStorage.setItem('sidebarCollapsed', false);
            }
            
            // Alternar estado
            parent.classList.toggle('active');
            submenu.classList.toggle('show');
            
            // Rotar ícono
            const icon = button.querySelector('.submenu-toggle');
            if (icon) {
                icon.style.transform = parent.classList.contains('active') ? 'rotate(90deg)' : '';
            }
            
            // En desktop: cerrar otros submenús del mismo nivel
            if (!isMobile() && isOpening) {
                const allParents = parent.parentNode.querySelectorAll('.has-submenu');
                allParents.forEach(otherParent => {
                    if (otherParent !== parent && otherParent.classList.contains('active')) {
                        otherParent.classList.remove('active');
                        const otherSubmenu = otherParent.querySelector('.submenu');
                        if (otherSubmenu) otherSubmenu.classList.remove('show');
                        
                        const otherIcon = otherParent.querySelector('.submenu-toggle');
                        if (otherIcon) otherIcon.style.transform = '';
                    }
                });
            }
        }
    }
    
    // ========== MANEJO DE ENLACES DE NAVEGACIÓN ==========
    // ¡ESTA ES LA PARTE MÁS IMPORTANTE QUE CORRIGE EL PROBLEMA!
    
    function setupNavLinks() {
        // Solo aplicar a enlaces dentro del sidebar
        const navLinks = sidebar.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                // Si es un botón de toggle de submenú, ya lo manejamos arriba
                if (this.classList.contains('submenu-toggle-btn')) {
                    return;
                }
                
                const href = this.getAttribute('href');
                
                // Si el enlace es javascript:void(0) o está vacío, no hacer nada
                if (!href || href === 'javascript:void(0)' || href === '#') {
                    e.preventDefault();
                    return;
                }
                
                // En móvil, cerrar sidebar después de un pequeño delay
                if (isMobile() && sidebar.classList.contains('show')) {
                    // Pequeño delay para mejor UX
                    setTimeout(() => {
                        toggleMobileSidebar();
                    }, 200);
                }
                
                // En desktop, si el sidebar está colapsado, expandirlo al hacer clic
                if (!isMobile() && sidebar.classList.contains('collapsed') && 
                    href && href !== 'javascript:void(0)') {
                    sidebar.classList.remove('collapsed');
                    mainContent.classList.remove('expanded');
                    localStorage.setItem('sidebarCollapsed', false);
                }
            });
        });
    }
    
    // ========== INICIALIZACIÓN ==========
    
    function initialize() {
        // 1. Fecha actual
        const dateElement = document.getElementById('current-date');
        if (dateElement && !dateElement.textContent.trim()) {
            dateElement.textContent = new Date().toLocaleDateString('es-ES');
        }
        
        // 2. Cargar estado del sidebar en desktop
        if (!isMobile()) {
            const savedState = localStorage.getItem('sidebarCollapsed');
            if (savedState === 'true') {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
            }
        }
        
        // 3. Submenús activos según URL actual
        activateCurrentMenu();
        
        // 4. Configurar submenús y enlaces
        setupSubmenus();
        setupNavLinks();
        
        // 5. Auto-cerrar alertas
        setupAutoCloseAlerts();
        
        // 6. Manejar redimensionamiento
        window.addEventListener('resize', handleResize);
        
        // 7. Cerrar sidebar con ESC en móvil
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && isMobile() && sidebar.classList.contains('show')) {
                toggleMobileSidebar();
            }
        });
    }
    
    // Activar menú actual según URL
    function activateCurrentMenu() {
        const path = window.location.pathname;
        
        // Mapeo de rutas a submenús
        const menuMap = {
            '/admin/usuarios': '#catalogos-submenu',
            '/admin/empresas': '#catalogos-submenu',
            '/admin/clientes': '#catalogos-submenu',
            '/admin/proveedores': '#catalogos-submenu',
            '/admin/unidades_medidas': '#catalogos-submenu',
            '/admin/categorias': '#catalogos-submenu',
            '/admin/metodos_pago': '#catalogos-submenu',
            '/admin/movimientos_inventario': '#catalogos-submenu',
            '/admin/productos': '#productos-submenu',
            '/admin/bodega': '#bodega-submenu',
            '/admin/historial_movimientos': '#bodega-submenu',
            '/admin/ventas_salidas': '#ventas-submenu',
            '/admin/cuentascobrar': '#ventas-submenu',
            '/admin/compras_entradas': '#compras-submenu',
            '/admin/cuentas_por_pagar': '#compras-submenu',
            '/admin/bitacora': '#herramientas-submenu'
        };
        
        // Buscar coincidencia
        for (const [route, submenuId] of Object.entries(menuMap)) {
            if (path.includes(route)) {
                const submenu = document.querySelector(submenuId);
                if (submenu) {
                    const parent = submenu.closest('.has-submenu');
                    submenu.classList.add('show');
                    if (parent) parent.classList.add('active');
                    
                    const icon = parent?.querySelector('.submenu-toggle');
                    if (icon) icon.style.transform = 'rotate(90deg)';
                }
                break;
            }
        }
    }
    
    // Manejar cambio de tamaño
    function handleResize() {
        if (isMobile()) {
            // En móvil: resetear sidebar
            sidebar.classList.remove('collapsed', 'show');
            mainContent.classList.remove('expanded');
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        } else {
            // En desktop: cargar estado guardado
            const savedState = localStorage.getItem('sidebarCollapsed');
            if (savedState === 'true') {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
            } else {
                sidebar.classList.remove('collapsed');
                mainContent.classList.remove('expanded');
            }
        }
    }
    
    // Auto-cerrar alertas
    function setupAutoCloseAlerts() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            setTimeout(() => {
                if (alert && alert.parentNode) {
                    try {
                        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
                        bsAlert.close();
                    } catch (e) {
                        // Fallback
                        alert.style.opacity = '0';
                        setTimeout(() => {
                            if (alert.parentNode) alert.parentNode.removeChild(alert);
                        }, 300);
                    }
                }
            }, 5000);
        });
    }
    
    // ========== EJECUTAR INICIALIZACIÓN ==========
    initialize();
});