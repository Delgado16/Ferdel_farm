import os

file_path = 'c:/Users/ferza/OneDrive/Documents/ferdel/templates/bodega/dashboard.html'

premium_dashboard = """{% extends "layout.html" %}

{% block title %}Dashboard de Bodega - FerDel{% endblock %}

{% block extra_css %}
<!-- Chart.js para Analítica Interactiva -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>

<style>
/* Estilos extraídos de reportes_avanzados para consistencia premium */
.card-premium-section {
    background: #ffffff;
    border-radius: 12px;
    border: 1px solid rgba(226, 232, 240, 0.8);
    transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
}
.card-premium-section:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.05) !important;
}
.nav-pills .nav-link {
    color: #495057;
    border: 1px solid #dee2e6;
    transition: all 0.2s ease;
}
.nav-pills .nav-link:hover {
    background-color: #f8f9fa;
    color: var(--primary-color);
}
.nav-pills .nav-link.active {
    background-color: var(--primary-color);
    color: #fff;
    border-color: var(--primary-color);
    box-shadow: 0 2px 4px rgba(44, 94, 46, 0.25);
}
.table-modern thead th {
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #495057;
    font-weight: 700;
    border-bottom: 2px solid #dee2e6;
    background-color: #f8fafc;
}
.fade-in-up {
    animation: fadeInUp 0.4s ease-out;
}
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>
{% endblock %}

{% block content %}
<div class="container-fluid py-4 fade-in-up">
    <!-- Encabezado Principal -->
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
    </div>

    <!-- KPIs Estadísticos (Diseño Premium) -->
    <div class="row g-3 mb-4">
        <!-- Movimientos -->
        <div class="col-xl-3 col-md-6">
            <div class="card-premium-section h-100 border-start border-4 border-primary shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="text-muted text-uppercase fw-bold" style="font-size: 0.75rem;">Movimientos Hoy</span>
                            <h3 class="fw-bold text-slate-800 mb-1 mt-1">{{ resumen_dia_total.total_movimientos if resumen_dia_total else 0 }}</h3>
                            <small class="text-primary fw-semibold">Transacciones totales</small>
                        </div>
                        <div class="bg-primary bg-opacity-10 text-primary p-3 rounded-circle">
                            <i class="fas fa-exchange-alt fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Entradas -->
        <div class="col-xl-3 col-md-6">
            <div class="card-premium-section h-100 border-start border-4 border-success shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="text-muted text-uppercase fw-bold" style="font-size: 0.75rem;">Total Entradas</span>
                            <h3 class="fw-bold text-success mb-1 mt-1">{{ resumen_dia_entradas.total_entradas if resumen_dia_entradas else 0 }}</h3>
                            <small class="text-muted">Unidades recibidas hoy</small>
                        </div>
                        <div class="bg-success bg-opacity-10 text-success p-3 rounded-circle">
                            <i class="fas fa-arrow-circle-down fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Salidas -->
        <div class="col-xl-3 col-md-6">
            <div class="card-premium-section h-100 border-start border-4 border-danger shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="text-muted text-uppercase fw-bold" style="font-size: 0.75rem;">Total Salidas</span>
                            <h3 class="fw-bold text-danger mb-1 mt-1">{{ resumen_dia_salidas.total_salidas if resumen_dia_salidas else 0 }}</h3>
                            <small class="text-muted">Unidades despachadas hoy</small>
                        </div>
                        <div class="bg-danger bg-opacity-10 text-danger p-3 rounded-circle">
                            <i class="fas fa-arrow-circle-up fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Cargas Pendientes -->
        <div class="col-xl-3 col-md-6">
            <div class="card-premium-section h-100 border-start border-4 border-warning shadow-sm">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <span class="text-muted text-uppercase fw-bold" style="font-size: 0.75rem;">Cargas Pendientes</span>
                            <h3 class="fw-bold text-warning mb-1 mt-1">{{ cargas_pendientes_recepcion|length if cargas_pendientes_recepcion else 0 }}</h3>
                            <small class="text-muted">Pendientes de recepción</small>
                        </div>
                        <div class="bg-warning bg-opacity-10 text-warning p-3 rounded-circle">
                            <i class="fas fa-truck-loading fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Contenido Principal: Gráficos y Tablas -->
    <div class="row g-4 mb-4">
        <!-- Columna Izquierda: Gráfico Flujo Horario y Tablas Operativas -->
        <div class="col-xl-8 col-lg-7">
            <!-- Gráfico de Flujo -->
            <div class="card-premium-section h-100 shadow-sm mb-4">
                <div class="card-header bg-transparent border-0 d-flex justify-content-between align-items-center py-3">
                    <div>
                        <h6 class="fw-bold text-slate-800 mb-0">
                            <i class="fas fa-chart-area text-primary me-2"></i>Flujo Horario de Movimientos Hoy
                        </h6>
                        <small class="text-muted">Entradas vs Salidas por Hora</small>
                    </div>
                </div>
                <div class="card-body p-3">
                    <div style="height: 250px; position: relative;">
                        <canvas id="chartFlujoHoras"></canvas>
                    </div>
                </div>
            </div>

            <!-- Tablas Operativas (Pills Tabs) -->
            <div class="card-premium-section shadow-sm mb-4">
                <div class="card-header border-bottom border-light bg-transparent py-3">
                    <ul class="nav nav-pills gap-2" id="dashboardTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active rounded-pill px-3 py-2 small fw-bold" id="cargas-tab" data-bs-toggle="tab" data-bs-target="#cargas-pane" type="button" role="tab" aria-controls="cargas-pane" aria-selected="true">
                                <i class="fas fa-truck-loading me-1.5"></i> Cargas
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link rounded-pill px-3 py-2 small fw-bold" id="pedidos-tab" data-bs-toggle="tab" data-bs-target="#pedidos-pane" type="button" role="tab" aria-controls="pedidos-pane" aria-selected="false">
                                <i class="fas fa-dolly text-primary me-1.5"></i> Pedidos
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link rounded-pill px-3 py-2 small fw-bold" id="kardex-tab" data-bs-toggle="tab" data-bs-target="#kardex-pane" type="button" role="tab" aria-controls="kardex-pane" aria-selected="false">
                                <i class="fas fa-history text-secondary me-1.5"></i> Kardex en Vivo
                            </button>
                        </li>
                    </ul>
                </div>

                <div class="card-body p-0">
                    <div class="tab-content p-4" id="dashboardTabsContent">
                        <!-- CARGAS -->
                        <div class="tab-pane fade show active" id="cargas-pane" role="tabpanel" aria-labelledby="cargas-tab">
                            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
                                <h6 class="fw-bold text-slate-800 mb-0">Cargas Pendientes de Recepción</h6>
                                <div class="input-group" style="max-width: 250px;">
                                    <span class="input-group-text bg-white border-end-0 py-1"><i class="fas fa-search text-muted small"></i></span>
                                    <input type="text" class="form-control form-control-sm border-start-0 py-1" id="searchCargas" placeholder="Buscar...">
                                </div>
                            </div>
                            <div class="table-responsive" style="max-height: 400px;">
                                <table class="table table-hover table-modern align-middle mb-0" id="tablaCargas">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th>Fecha / Referencia</th>
                                            <th>Proveedor / Vendedor</th>
                                            <th>Ruta</th>
                                            <th>Estado</th>
                                            <th class="text-end">Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% if cargas_pendientes_recepcion %}
                                        {% for carga in cargas_pendientes_recepcion %}
                                        <tr>
                                            <td>
                                                <div class="fw-bold">{{ carga.Fecha_Formateada or carga.Fecha_Carga }}</div>
                                                <small class="text-muted font-monospace">{{ carga.ID_Carga }}</small>
                                            </td>
                                            <td>{{ carga.Usuario_Vendedor or carga.Proveedor }}</td>
                                            <td>{{ carga.Ruta or 'N/A' }}</td>
                                            <td><span class="badge bg-warning bg-opacity-10 text-warning border border-warning rounded-pill px-2 py-1">{{ carga.Estado }}</span></td>
                                            <td class="text-end">
                                                <a href="{{ url_for('bodega.bodega_recibir_carga', id=carga.ID_Carga) }}" class="btn btn-sm btn-outline-primary rounded-3">Ver</a>
                                            </td>
                                        </tr>
                                        {% endfor %}
                                        {% else %}
                                        <tr><td colspan="5" class="text-center text-muted py-4">No hay cargas pendientes</td></tr>
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- PEDIDOS -->
                        <div class="tab-pane fade" id="pedidos-pane" role="tabpanel" aria-labelledby="pedidos-tab">
                            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
                                <h6 class="fw-bold text-slate-800 mb-0">Pedidos a Despachar</h6>
                                <div class="input-group" style="max-width: 250px;">
                                    <span class="input-group-text bg-white border-end-0 py-1"><i class="fas fa-search text-muted small"></i></span>
                                    <input type="text" class="form-control form-control-sm border-start-0 py-1" id="searchPedidos" placeholder="Buscar...">
                                </div>
                            </div>
                            <div class="table-responsive" style="max-height: 400px;">
                                <table class="table table-hover table-modern align-middle mb-0" id="tablaPedidos">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th>Pedido</th>
                                            <th>Cliente</th>
                                            <th>Ruta</th>
                                            <th>Estado</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% if tabla_pedidos_pendientes %}
                                        {% for pedido in tabla_pedidos_pendientes %}
                                        <tr>
                                            <td>
                                                <div class="fw-bold font-monospace">#{{ pedido.ID_Venta }}</div>
                                                <small class="text-muted">{{ pedido.Fecha_Formateada }}</small>
                                            </td>
                                            <td>{{ pedido.Cliente_Nombre }}</td>
                                            <td>{{ pedido.Ruta }}</td>
                                            <td><span class="badge bg-danger bg-opacity-10 text-danger border border-danger rounded-pill px-2 py-1">{{ pedido.Estado_Entrega }}</span></td>
                                        </tr>
                                        {% endfor %}
                                        {% else %}
                                        <tr><td colspan="4" class="text-center text-muted py-4">No hay pedidos pendientes</td></tr>
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- KARDEX EN VIVO -->
                        <div class="tab-pane fade" id="kardex-pane" role="tabpanel" aria-labelledby="kardex-tab">
                            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3">
                                <h6 class="fw-bold text-slate-800 mb-0">Kardex en Vivo (Últimos Movimientos)</h6>
                                <div class="input-group" style="max-width: 250px;">
                                    <span class="input-group-text bg-white border-end-0 py-1"><i class="fas fa-search text-muted small"></i></span>
                                    <input type="text" class="form-control form-control-sm border-start-0 py-1" id="searchKardex" placeholder="Buscar...">
                                </div>
                            </div>
                            <div class="table-responsive" style="max-height: 400px;">
                                <table class="table table-hover table-modern align-middle mb-0" id="tablaKardex">
                                    <thead class="table-light sticky-top">
                                        <tr>
                                            <th>Hora</th>
                                            <th>Producto</th>
                                            <th>Tipo</th>
                                            <th class="text-end">Cant.</th>
                                            <th>Responsable</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {% if kardex_hoy %}
                                        {% for mov in kardex_hoy %}
                                        <tr>
                                            <td class="text-muted small font-monospace">{{ mov.Hora }}</td>
                                            <td>
                                                <span class="fw-bold d-block text-primary cursor-pointer text-truncate" style="max-width: 150px;" onclick="abrirKardexModal('{{ mov.ID_Producto }}', '{{ mov.Producto }}')">{{ mov.Producto }}</span>
                                                <small class="text-muted">{{ mov.Bodega }}</small>
                                            </td>
                                            <td>
                                                {% if mov.Adicion == '+' %}
                                                <span class="badge bg-success bg-opacity-10 text-success border border-success px-2 py-1 rounded-pill">{{ mov.Tipo }}</span>
                                                {% else %}
                                                <span class="badge bg-danger bg-opacity-10 text-danger border border-danger px-2 py-1 rounded-pill">{{ mov.Tipo }}</span>
                                                {% endif %}
                                            </td>
                                            <td class="text-end font-monospace fw-bold {% if mov.Adicion == '+' %}text-success{% else %}text-danger{% endif %}">
                                                {{ mov.Adicion }}{{ "%.2f"|format(mov.Cantidad|float) }}
                                            </td>
                                            <td><small class="text-muted">{{ mov.Usuario }}</small></td>
                                        </tr>
                                        {% endfor %}
                                        {% else %}
                                        <tr><td colspan="5" class="text-center text-muted py-4">Sin movimientos</td></tr>
                                        {% endif %}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Columna Derecha: Alertas y Bodegas -->
        <div class="col-xl-4 col-lg-5">
            
            <!-- Alertas de Stock Bajo (Diseño Premium) -->
            <div class="card-premium-section shadow-sm mb-4">
                <div class="card-header bg-transparent border-0 d-flex justify-content-between align-items-center py-3">
                    <div>
                        <h6 class="fw-bold text-slate-800 mb-0">
                            <i class="fas fa-exclamation-triangle text-warning me-2"></i>Alertas de Stock
                        </h6>
                    </div>
                    <span class="badge bg-warning text-dark rounded-pill">{{ productos_stock_bajo|length }}</span>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive" style="max-height: 350px;">
                        <table class="table table-hover table-modern align-middle mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Producto</th>
                                    <th class="text-center">Stock</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if productos_stock_bajo %}
                                {% for prod in productos_stock_bajo %}
                                <tr class="{% if prod.Nivel_Alerta == 'AGOTADO' %}bg-danger bg-opacity-10{% endif %}">
                                    <td>
                                        <div class="fw-bold cursor-pointer text-truncate" style="max-width: 150px;" onclick="abrirKardexModal('{{ prod.ID_Producto }}', '{{ prod.Producto }}')" title="{{ prod.Producto }}">
                                            {{ prod.Producto }}
                                        </div>
                                        <small class="text-muted font-monospace">{{ prod.Bodega }}</small>
                                    </td>
                                    <td class="text-center font-monospace">
                                        <span class="badge {% if prod.Nivel_Alerta == 'AGOTADO' %}bg-danger{% else %}bg-warning text-dark{% endif %} bg-opacity-10 border {% if prod.Nivel_Alerta == 'AGOTADO' %}border-danger text-danger{% else %}border-warning{% endif %} rounded-pill px-2 py-1 fw-bold">
                                            {{ prod.Stock_Actual_Formateado }}
                                        </span>
                                    </td>
                                </tr>
                                {% endfor %}
                                {% else %}
                                <tr>
                                    <td colspan="2" class="text-center py-4 text-success">
                                        <i class="fas fa-check-circle fa-2x mb-2 d-block"></i>
                                        ¡Niveles óptimos!
                                    </td>
                                </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Gráfico: Existencias por Bodega -->
            <div class="card-premium-section shadow-sm mb-4">
                <div class="card-header bg-transparent border-0 d-flex justify-content-between align-items-center py-3">
                    <div>
                        <h6 class="fw-bold text-slate-800 mb-0">
                            <i class="fas fa-boxes text-secondary me-2"></i>Existencias por Bodega
                        </h6>
                    </div>
                </div>
                <div class="card-body p-3">
                    <div style="height: 220px; position: relative;">
                        <canvas id="chartBodegasStock"></canvas>
                    </div>
                </div>
            </div>

        </div>
    </div>
</div>

<!-- MODAL INTERACTIVO: KARDEX RÁPIDO -->
<div class="modal fade" id="modalKardexRapido" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content rounded-4 border-0 shadow">
            <div class="modal-header bg-light border-bottom py-3">
                <div>
                    <h5 class="modal-title fw-bold text-slate-800 mb-0" id="modalKardexLabel">
                        <i class="fas fa-history text-primary me-2"></i>Kardex Rápido
                    </h5>
                    <small class="text-muted" id="modalKardexSubtitulo">Cargando...</small>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body p-4">
                <div id="modalKardexLoading" class="text-center py-5">
                    <div class="spinner-border text-primary" role="status"></div>
                </div>
                <div id="modalKardexContenido" style="display: none;">
                    <div class="row g-2 mb-4">
                        <div class="col-sm-4">
                            <div class="p-2.5 bg-light rounded-3 border text-center">
                                <small class="text-muted d-block fw-bold">STOCK TOTAL</small>
                                <h5 class="fw-bold text-primary font-monospace mb-0" id="modalStockTotal">-</h5>
                            </div>
                        </div>
                        <div class="col-sm-4">
                            <div class="p-2.5 bg-light rounded-3 border text-center">
                                <small class="text-muted d-block fw-bold">PRECIO MERCADO</small>
                                <h5 class="fw-bold text-success font-monospace mb-0" id="modalPrecioVenta">-</h5>
                            </div>
                        </div>
                        <div class="col-sm-4">
                            <div class="p-2.5 bg-light rounded-3 border text-center">
                                <small class="text-muted d-block fw-bold">CATEGORÍA</small>
                                <h6 class="fw-bold text-slate-800 mt-1 mb-0" id="modalCategoriaUnidad">-</h6>
                            </div>
                        </div>
                    </div>

                    <h6 class="fw-bold text-slate-800 mb-2 small text-uppercase"><i class="fas fa-warehouse text-secondary me-1"></i>Stock por Bodega</h6>
                    <div id="modalStockBodegasContainer" class="d-flex flex-wrap gap-2 mb-4"></div>

                    <h6 class="fw-bold text-slate-800 mb-2 small text-uppercase"><i class="fas fa-exchange-alt text-primary me-1"></i>Últimos Movimientos</h6>
                    <div class="table-responsive border rounded-3" style="max-height: 250px;">
                        <table class="table table-sm table-hover table-modern align-middle mb-0">
                            <thead class="table-light sticky-top">
                                <tr>
                                    <th>Fecha</th>
                                    <th>Tipo</th>
                                    <th>Bodega</th>
                                    <th class="text-end">Cant.</th>
                                    <th>Usuario</th>
                                </tr>
                            </thead>
                            <tbody id="modalMovimientosBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div class="modal-footer bg-light py-2 border-top">
                <button type="button" class="btn btn-secondary rounded-3 px-3 py-1.5 fw-semibold" data-bs-dismiss="modal">Cerrar</button>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function () {
    inicializarGraficosDashboard();
    configurarBuscador('searchCargas', 'tablaCargas');
    configurarBuscador('searchPedidos', 'tablaPedidos');
    configurarBuscador('searchKardex', 'tablaKardex');
    setTimeout(() => window.location.reload(), 300000);
});

function inicializarGraficosDashboard() {
    const ctxFlujo = document.getElementById('chartFlujoHoras');
    if (ctxFlujo) {
        new Chart(ctxFlujo, {
            type: 'line',
            data: {
                labels: {{ chart_horas|safe if chart_horas else "['Sin actividad']" }},
                datasets: [
                    { 
                        label: 'Entradas', 
                        data: {{ chart_entradas_hora|safe if chart_entradas_hora else "[0]" }}, 
                        borderColor: '#10b981', 
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.3
                    },
                    { 
                        label: 'Salidas', 
                        data: {{ chart_salidas_hora|safe if chart_salidas_hora else "[0]" }}, 
                        borderColor: '#ef4444', 
                        backgroundColor: 'transparent',
                        borderDash: [5, 5],
                        tension: 0.3
                    }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' } } }
        });
    }

    const ctxBodegas = document.getElementById('chartBodegasStock');
    if (ctxBodegas) {
        new Chart(ctxBodegas, {
            type: 'bar',
            data: {
                labels: {{ chart_bodegas_nombres|safe if chart_bodegas_nombres else "['Sin bodegas']" }},
                datasets: [{ 
                    label: 'Existencias', 
                    data: {{ chart_bodegas_existencias|safe if chart_bodegas_existencias else "[0]" }}, 
                    backgroundColor: 'rgba(44, 94, 46, 0.85)', 
                    borderRadius: 6 
                }]
            },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
        });
    }
}

function configurarBuscador(inputId, tableId) {
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);
    if (!input || !table) return;
    input.addEventListener('keyup', function() {
        const filter = this.value.toLowerCase().trim();
        table.querySelectorAll('tbody tr').forEach(row => {
            row.style.display = row.textContent.toLowerCase().includes(filter) ? '' : 'none';
        });
    });
}

function abrirKardexModal(productoId, productoNombre) {
    if (!productoId) return;
    const modalEl = document.getElementById('modalKardexRapido');
    const modal = window.bootstrap && bootstrap.Modal ? bootstrap.Modal.getOrCreateInstance(modalEl) : new bootstrap.Modal(modalEl);
    
    document.getElementById('modalKardexSubtitulo').textContent = productoNombre + ' (ID: #' + productoId + ')';
    document.getElementById('modalKardexLoading').style.display = 'block';
    document.getElementById('modalKardexContenido').style.display = 'none';
    modal.show();

    fetch(`/bodega/api/producto/${productoId}/kardex-rapido`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('modalKardexLoading').style.display = 'none';
            if (data.success) {
                document.getElementById('modalKardexContenido').style.display = 'block';
                const p = data.producto;
                document.getElementById('modalStockTotal').textContent = (p.Stock_Total || 0) + ' ' + (p.Unidad_Abrev || '');
                document.getElementById('modalPrecioVenta').textContent = 'C$ ' + parseFloat(p.Precio_Mercado || 0).toFixed(2);
                document.getElementById('modalCategoriaUnidad').textContent = (p.Categoria || 'S/C');

                const bodegasContainer = document.getElementById('modalStockBodegasContainer');
                bodegasContainer.innerHTML = data.stock_bodegas?.length ? 
                    data.stock_bodegas.map(b => `<span class="badge bg-light text-dark border px-2 py-1"><strong>${b.Bodega}:</strong> ${parseFloat(b.Existencias).toFixed(2)}</span>`).join('') 
                    : '<span class="text-muted small">Sin existencias</span>';

                const movBody = document.getElementById('modalMovimientosBody');
                movBody.innerHTML = data.movimientos?.length ? 
                    data.movimientos.map(m => {
                        const esEntrada = m.Letra === 'E' || m.Adicion === '+';
                        const cls = esEntrada ? 'text-success' : 'text-danger';
                        const badgeTipo = esEntrada 
                            ? `<span class="badge bg-success bg-opacity-10 text-success border border-success px-2 py-1 rounded-pill">${m.Tipo_Movimiento}</span>`
                            : `<span class="badge bg-danger bg-opacity-10 text-danger border border-danger px-2 py-1 rounded-pill">${m.Tipo_Movimiento}</span>`;
                        return `<tr>
                            <td class="font-monospace small text-slate-800">${m.Fecha_Formateada || m.Fecha}</td>
                            <td>${badgeTipo}</td>
                            <td><small>${m.Bodega_Origen || m.Bodega_Destino || 'N/A'}</small></td>
                            <td class="text-end fw-bold font-monospace ${cls}">${esEntrada?'+':'-'}${parseFloat(m.Cantidad).toFixed(2)}</td>
                            <td><small>${m.Usuario || 'Sistema'}</small></td>
                        </tr>`;
                    }).join('') : `<tr><td colspan="5" class="text-center text-muted">Sin movimientos</td></tr>`;
            } else {
                alert(data.message || 'Error');
            }
        }).catch(err => {
            document.getElementById('modalKardexLoading').style.display = 'none';
            alert('Error al consultar kardex');
        });
}
</script>
{% endblock %}
"""

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(premium_dashboard)

print("Dashboard rewritten using premium report style!")
