import os

file_path = 'c:/Users/ferza/OneDrive/Documents/ferdel/templates/bodega/dashboard.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Wrap the Header in a Premium Card for better grounding
header_old = """    <!-- Encabezado Principal -->
    <div class="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-4">
        <div>
            <h3 class="fw-bold text-slate-800 mb-1">
                <i class="fas fa-warehouse text-primary me-2"></i>Centro de Control de Bodega
            </h3>
            <p class="text-muted small mb-0">Métricas operativas en tiempo real, recepción de cargas y preparación de despachos - {{ fecha_hoy }}</p>
        </div>
        <div class="d-flex flex-wrap gap-2">
            <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=entrada" class="btn btn-outline-success rounded-3 px-3 py-2 fw-semibold">
                <i class="fas fa-arrow-down me-1"></i>Entrada
            </a>
            <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=salida" class="btn btn-outline-danger rounded-3 px-3 py-2 fw-semibold">
                <i class="fas fa-arrow-up me-1"></i>Salida
            </a>
            <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=transferencia" class="btn btn-outline-primary rounded-3 px-3 py-2 fw-semibold">
                <i class="fas fa-exchange-alt me-1"></i>Transferir
            </a>
            <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=carga_ruta" class="btn btn-primary rounded-3 px-3 py-2 fw-semibold shadow-sm">
                <i class="fas fa-truck-loading me-1"></i>Cargar Ruta
            </a>
            <button type="button" class="btn btn-outline-secondary rounded-3 px-3 py-2 fw-semibold" onclick="window.location.reload()" title="Refrescar">
                <i class="fas fa-sync-alt"></i>
            </button>
        </div>
    </div>"""

header_new = """    <!-- Encabezado Principal -->
    <div class="card-premium-section mb-4 shadow-sm border-0 bg-white">
        <div class="card-body p-4 d-flex flex-wrap justify-content-between align-items-center gap-4">
            <div>
                <h3 class="fw-bold text-slate-800 mb-1">
                    <i class="fas fa-warehouse text-primary me-2"></i>Centro de Control de Bodega
                </h3>
                <p class="text-muted small mb-0">Métricas operativas en tiempo real, recepción de cargas y preparación de despachos - {{ fecha_hoy }}</p>
            </div>
            <div class="d-flex flex-wrap gap-2">
                <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=entrada" class="btn btn-outline-success rounded-3 px-3 py-2 fw-semibold">
                    <i class="fas fa-arrow-down me-1"></i> Entrada
                </a>
                <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=salida" class="btn btn-outline-danger rounded-3 px-3 py-2 fw-semibold">
                    <i class="fas fa-arrow-up me-1"></i> Salida
                </a>
                <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=transferencia" class="btn btn-outline-primary rounded-3 px-3 py-2 fw-semibold">
                    <i class="fas fa-exchange-alt me-1"></i> Transferir
                </a>
                <a href="{{ url_for('bodega.bodega_historial_movimientos') }}?tipo=carga_ruta" class="btn btn-primary rounded-3 px-3 py-2 fw-semibold shadow-sm">
                    <i class="fas fa-truck-loading me-1"></i> Cargar Ruta
                </a>
                <button type="button" class="btn btn-outline-secondary rounded-3 px-3 py-2 fw-semibold" onclick="window.location.reload()" title="Refrescar">
                    <i class="fas fa-sync-alt"></i>
                </button>
            </div>
        </div>
    </div>"""
content = content.replace(header_old, header_new)

# 2. Change KPI grid gap from 3 to 4 for better breathing room
content = content.replace('<div class="row g-3 mb-4">', '<div class="row g-4 mb-4">')

# 3. Clean up the tabs content to span full width (edge-to-edge tables)
content = content.replace('<div class="tab-content p-4" id="dashboardTabsContent">', '<div class="tab-content" id="dashboardTabsContent">')

# 4. Add padding to the search bars so they aren't touching the edge now that p-4 is removed
content = content.replace('<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">', '<div class="d-flex justify-content-between align-items-center flex-wrap gap-2 p-3 pb-2 border-bottom">')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Layout spacing and margins adjusted.")
