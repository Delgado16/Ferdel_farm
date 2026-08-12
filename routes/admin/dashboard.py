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
        
        # Calcular alertas
        alertas = []
        if kpis['productos_bajo_stock'] > 0:
            alertas.append({
                'tipo': 'warning',
                'titulo': 'Stock Crítico',
                'mensaje': f"Hay {kpis['productos_bajo_stock']} productos con existencias por debajo del stock mínimo.",
                'icono': 'bi-exclamation-triangle-fill',
                'enlace': url_for('admin.admin_productos')
            })
        if kpis['facturas_vencidas'] > 0:
            alertas.append({
                'tipo': 'danger',
                'titulo': 'Cartera Vencida',
                'mensaje': f"Existen {kpis['facturas_vencidas']} facturas vencidas en el sistema.",
                'icono': 'bi-flag-fill',
                'enlace': url_for('admin.admin_cuentascobrar', estado='vencidas')
            })

        # Alertas de seguros de vehículos por vencer (14 días)
        try:
            from config.database import get_db_cursor
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT ID_Vehiculo, Placa, Marca, Modelo, Fecha_Vencimiento_Seguro,
                           DATEDIFF(Fecha_Vencimiento_Seguro, CURDATE()) AS Dias_Restantes
                    FROM vehiculos
                    WHERE Estado != 'Inactivo'
                      AND Fecha_Vencimiento_Seguro IS NOT NULL
                      AND Fecha_Vencimiento_Seguro <= DATE_ADD(CURDATE(), INTERVAL 14 DAY)
                    ORDER BY Fecha_Vencimiento_Seguro ASC
                """)
                seguros_por_vencer = cursor.fetchall()
                
                for v in seguros_por_vencer:
                    dias = v['Dias_Restantes']
                    placa = v['Placa']
                    vehiculo_str = f"{v['Marca']} {v['Modelo']} ({placa})" if v['Marca'] else f"Vehículo ({placa})"
                    
                    if dias < 0:
                        mensaje = f"La póliza de seguro del vehículo {vehiculo_str} está VENCIDA (venció el {v['Fecha_Vencimiento_Seguro'].strftime('%d/%m/%Y')})."
                        tipo = 'danger'
                    elif dias == 0:
                        mensaje = f"La póliza de seguro del vehículo {vehiculo_str} vence HOY."
                        tipo = 'danger'
                    elif dias == 1:
                        mensaje = f"La póliza de seguro del vehículo {vehiculo_str} vence MAÑANA."
                        tipo = 'danger'
                    else:
                        mensaje = f"La póliza de seguro del vehículo {vehiculo_str} vence en {dias} días (el {v['Fecha_Vencimiento_Seguro'].strftime('%d/%m/%Y')})."
                        tipo = 'warning'
                        
                    alertas.append({
                        'tipo': tipo,
                        'titulo': 'Seguro por Vencer',
                        'mensaje': mensaje,
                        'icono': 'bi-shield-exclamation',
                        'enlace': url_for('admin.admin_vehiculos')
                    })
        except Exception as db_err:
            print(f"⚠️ Error al consultar vencimientos de seguros de vehículos: {db_err}")
        
        return render_template('admin/dashboard.html',
                             # KPIs
                             usuarios_count=kpis['usuarios_count'],
                             empresas_count=kpis['empresas_count'],
                             ventas_hoy=kpis['ventas_hoy'],
                             cobros_hoy=kpis['cobros_hoy'],
                             saldo_pendiente=kpis['saldo_pendiente'],
                             facturas_vencidas=kpis['facturas_vencidas'],
                             productos_bajo_stock=kpis['productos_bajo_stock'],
                             # Alertas
                             alertas=alertas,
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
