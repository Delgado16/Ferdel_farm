import os

file_path = 'c:/Users/ferza/OneDrive/Documents/ferdel/templates/bodega/dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update CSS
css_updates = """
    /* Premium Dashboard Restructure */
    .dashboard-stat-card {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.6);
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(31, 38, 135, 0.05);
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }

    .dashboard-stat-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(31, 38, 135, 0.1);
        border-color: rgba(44, 94, 46, 0.2);
    }

    /* Quick Actions Sidebar Layout */
    .quick-actions-stack {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .quick-action-btn-side {
        border-radius: 16px;
        background: white;
        border: 1px solid rgba(226, 232, 240, 0.85);
        padding: 1rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        text-decoration: none;
        color: var(--text-main);
        position: relative;
        overflow: hidden;
    }

    .quick-action-btn-side:hover {
        transform: translateX(6px);
        box-shadow: 0 10px 25px rgba(44, 94, 46, 0.08) !important;
        border-color: rgba(44, 94, 46, 0.3);
        color: var(--text-main);
    }

    .qa-icon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 1.25rem;
        transition: transform 0.3s ease;
    }

    .quick-action-btn-side:hover .qa-icon {
        transform: scale(1.1) rotate(5deg);
    }
"""
content = content.replace("</style>", css_updates + "\n</style>")

# Update Theme colors
content = content.replace("border-top: 4px solid #3b82f6 !important;", "border-top: 4px solid var(--primary-color) !important;")
content = content.replace("border-top: 4px solid #10b981 !important;", "border-top: 4px solid var(--secondary-color) !important;")
content = content.replace("background-color: rgba(59, 130, 246, 0.12); color: #3b82f6;", "background-color: rgba(44, 94, 46, 0.12); color: var(--primary-color);")
content = content.replace("background-color: rgba(16, 185, 129, 0.12); color: #10b981;", "background-color: rgba(16, 185, 129, 0.12); color: var(--secondary-color);")
content = content.replace("'rgba(16, 185, 129, 0.85)'", "'#10b981'")
content = content.replace("'rgba(59, 130, 246, 0.85)'", "'#2c5e2e'")
content = content.replace("text-primary", "text-success")


new_quick_actions = """
            <!-- Acciones Rápidas (Panel de Control) -->
            <div class="table-card mb-4 border-top-primary">
                <div class="table-header-styled bg-white border-bottom-0 pb-0 pt-3 px-3">
                    <h5 class="fw-bold mb-0 text-dark">
                        <i class="fas fa-bolt me-2 text-primary"></i>Panel de Control
                    </h5>
                </div>
                <div class="card-body p-3">
                    <div class="quick-actions-stack">
                        <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=entrada" class="quick-action-btn-side qa-secondary">
                            <div class="qa-icon bg-success bg-opacity-10 text-success"><i class="fas fa-arrow-circle-down"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Registrar Entrada</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Recepcionar productos</small>
                            </div>
                        </a>
                        
                        <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=salida" class="quick-action-btn-side">
                            <div class="qa-icon bg-primary bg-opacity-10 text-primary"><i class="fas fa-arrow-circle-up"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Registrar Salida</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Despachos rápidos</small>
                            </div>
                        </a>
                        
                        <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=transferencia" class="quick-action-btn-side">
                            <div class="qa-icon bg-primary bg-opacity-10 text-primary"><i class="fas fa-exchange-alt"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Transferir</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Movimiento entre bodegas</small>
                            </div>
                        </a>
                        
                        <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=carga_ruta" class="quick-action-btn-side qa-secondary">
                            <div class="qa-icon bg-warning bg-opacity-10 text-warning"><i class="fas fa-truck-loading"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Carga a Ruta</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Asignar inventario a camión</small>
                            </div>
                        </a>
                        
                        <a href="{{ url_for('bodega.bodega_auditoria_inventario') }}" class="quick-action-btn-side">
                            <div class="qa-icon bg-secondary bg-opacity-10 text-secondary"><i class="fas fa-clipboard-check"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Auditoría</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Revisión de inventario</small>
                            </div>
                        </a>
                        
                        <a href="{{ url_for('bodega.bodega_reportes_avanzados') }}" class="quick-action-btn-side">
                            <div class="qa-icon bg-info bg-opacity-10 text-info"><i class="fas fa-chart-line"></i></div>
                            <div>
                                <h6 class="fw-bold mb-0 text-dark">Reportes</h6>
                                <small class="text-muted" style="font-size: 0.7rem;">Análisis avanzado</small>
                            </div>
                        </a>
                    </div>
                </div>
            </div>
"""

# Re-assemble
parts = content.split('<!-- ============================================ -->')

# Part 4 is Quick Actions HTML. We will empty Part 3 and Part 4 to remove it from the top.
parts[3] = ""
parts[4] = ""

# Part 8 is the Main Content (Row with 2 columns).
# We inject the `new_quick_actions` into Part 8, exactly after `<div class="col-xl-4 col-lg-5">`
if '<div class="col-xl-4 col-lg-5">' in parts[8]:
    parts[8] = parts[8].replace('<div class="col-xl-4 col-lg-5">', '<div class="col-xl-4 col-lg-5">\n' + new_quick_actions)

new_content = '<!-- ============================================ -->'.join(parts)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Dashboard safely restructured!")
