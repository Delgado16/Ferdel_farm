from flask import render_template, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime, timedelta
from . import admin_bp
from auth.decorators import admin_required
from .utils import (
    obtener_metricas_kpis,
    obtener_ventas_mes,
    obtener_top_clientes_deudores,
    obtener_productos_bajo_stock,
    obtener_gastos_mes,
    obtener_ventas_vendedores,
    obtener_rutas_activas,
    obtener_ventas_7dias,
    obtener_movimientos_caja,
    obtener_proximos_vencimientos,
    preparar_datos_graficos
)

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Dashboard del administrador con KPIs y reportes"""
    try:
        # Obtener todas las métricas usando funciones centralizadas
        kpis = obtener_metricas_kpis()
        ventas_mes = obtener_ventas_mes()
        top_clientes = obtener_top_clientes_deudores()
        productos_stock = obtener_productos_bajo_stock()
        gastos_mes = obtener_gastos_mes()
        ventas_vendedores = obtener_ventas_vendedores()
        rutas_activas = obtener_rutas_activas()
        ventas_7dias = obtener_ventas_7dias()
        movimientos_caja = obtener_movimientos_caja()
        proximos_vencimientos = obtener_proximos_vencimientos()
        
        # Preparar datos para gráficos
        graficos = preparar_datos_graficos(
            ventas_mes, 
            ventas_7dias, 
            gastos_mes, 
            movimientos_caja
        )
        
        now = datetime.now()
        
        return render_template('admin/dashboard.html',
                             # KPIs
                             usuarios_count=kpis['usuarios_count'],
                             empresas_count=kpis['empresas_count'],
                             ventas_hoy=kpis['ventas_hoy'],
                             cobros_hoy=kpis['cobros_hoy'],
                             saldo_pendiente=kpis['saldo_pendiente'],
                             facturas_vencidas=kpis['facturas_vencidas'],
                             productos_bajo_stock=kpis['productos_bajo_stock'],
                             # Tablas
                             top_clientes=top_clientes,
                             productos_stock=productos_stock,
                             ventas_vendedores=ventas_vendedores,
                             rutas_activas=rutas_activas,
                             movimientos_caja=movimientos_caja,
                             proximos_vencimientos=proximos_vencimientos,
                             # Datos para gráficos
                             ventas_mes_json=graficos['ventas_mes_json'],
                             ventas_7dias_json=graficos['ventas_7dias_json'],
                             gastos_mes_json=graficos['gastos_mes_json'],
                             now=now)
                             
    except Exception as e:
        import traceback
        error_msg = f"Error al cargar dashboard: {e}\n\n{traceback.format_exc()}"
        print(error_msg)
        return f"<h1>Error al cargar dashboard</h1><pre>{error_msg}</pre>", 500
