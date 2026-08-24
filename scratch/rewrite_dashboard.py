import re
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

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem;
    }

    @media (min-width: 768px) {
        .stats-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }
    
    @media (min-width: 1200px) {
        .stats-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
    }

    .table-card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        border: 1px solid rgba(226, 232, 240, 0.85);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
        overflow: hidden;
        margin-bottom: 1.5rem;
        transition: box-shadow 0.3s ease;
    }
    
    .table-card:hover {
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.07);
    }

    .chart-container-box {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        border: 1px solid rgba(226, 232, 240, 0.85);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.04);
        padding: 1.5rem;
        height: 100%;
        transition: box-shadow 0.3s ease;
    }
    
    .chart-container-box:hover {
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.07);
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
    
    .quick-action-btn-side::after {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        height: 100%;
        width: 4px;
        background: var(--primary-color);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .quick-action-btn-side.qa-secondary::after {
        background: var(--secondary-color);
    }
    
    .quick-action-btn-side:hover::after {
        opacity: 1;
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

content = content.replace("    /* Design Tokens & Premium Dashboard Styles */\n", css_updates + "\n    /* Design Tokens & Premium Dashboard Styles */\n")

# To re-layout, we can extract the HTML parts and reconstruct the template body
# Parts to extract:
# Header: 221 to 247 -> let's grab it via regex
header = re.search(r'(<!-- 1\. ENCABEZADO DEL DASHBOARD\s*-->.*?</div>\s*</div>)', content, re.DOTALL).group(1)

# Quick Actions
quick_actions = re.search(r'(<!-- 2\. ACCIONES RÁPIDAS OPERATIVAS\s*-->.*?</div>\s*</div>)', content, re.DOTALL).group(1)

# Summary
summary = re.search(r'(<!-- 3\. RESUMEN EJECUTIVO - 8 KPI CARDS\s*-->.*?</div>\s*</div>\s*</div>)', content, re.DOTALL).group(1)

# Charts
charts = re.search(r'(<!-- 4\. ANALÍTICA VISUAL DEL DÍA \(GRÁFICOS\)\s*-->.*?</div>\s*</div>\s*</div>)', content, re.DOTALL).group(1)

# Tabs
tabs = re.search(r'(<!-- Pestañas Operativas -->.*?</div>\s*</div>\s*</div>)', content, re.DOTALL).group(1)

# Kardex
kardex = re.search(r'(<!-- KARDEX DEL DÍA \(HISTORIAL EN VIVO\) -->.*?</div>\s*</div>)', content, re.DOTALL).group(1)

# Bodegas
bodegas = re.search(r'(<!-- Estado de Bodegas -->.*?</div>\s*</div>)', content, re.DOTALL).group(1)

# Alertas
alertas = re.search(r'(<!-- Alertas de Stock Bajo -->.*?</div>\s*</div>)', content, re.DOTALL).group(1)

# We want the KPIs to be top. But wait, summary has 8 KPI cards in a 2/4/8 grid. Let's keep it but it will be 4 columns. 
# We'll just place it below the header.
# We'll place Quick actions inside a new card in the right column.

new_quick_actions = """
            <!-- Acciones Rápidas (Panel de Control) -->
            <div class="table-card mb-4 border-top-primary">
                <div class="table-header-styled bg-white border-bottom-0 pb-0">
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

# Now assemble the body
body_start = """<div class="container-fluid py-3 py-md-4">"""
body_end = "</div>\n\n<!-- ============================================ -->\n<!-- MODAL"

new_layout = f"""
{header}

{summary}

<div class="row g-3 g-md-4">
    <!-- COLUMNA IZQUIERDA (70%) -->
    <div class="col-xl-8 col-lg-7">
        {charts}
        
        {tabs}
        
        {kardex}
    </div>
    
    <!-- COLUMNA DERECHA (30%) -->
    <div class="col-xl-4 col-lg-5">
        {new_quick_actions}
        
        {alertas}
        
        {bodegas}
    </div>
</div>
"""

# Replace in content
# Find everything between <div class="container-fluid py-3 py-md-4"> and the modal
match = re.search(r'(<div class="container-fluid py-3 py-md-4">).*?(<!-- MODAL DE KARDEX)', content, re.DOTALL)
if match:
    content = content[:match.start(1)] + '<div class="container-fluid py-3 py-md-4">\n' + new_layout + '\n</div>\n\n' + match.group(2) + content[match.end(2):]
    
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Structural Redesign Complete!")
