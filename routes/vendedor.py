"""
Blueprint de rutas del vendedor (dashboard, ventas, cobros)
"""
from datetime import datetime, timedelta
import traceback

from flask import Blueprint, json, jsonify, render_template, flash, redirect, request, url_for, session
from flask_login import login_required, current_user
from config.database import get_db_cursor
from auth.decorators import vendedor_required

vendedor_bp = Blueprint('vendedor', __name__, url_prefix='/vendedor')

def convertir_hora_db(hora_db):
    """Convierte hora de la base de datos (timedelta, time, o string) a string HH:MM"""
    if not hora_db:
        return None
    
    try:
        # Si es timedelta (MySQL devuelve TIME como timedelta)
        if hasattr(hora_db, 'seconds'):
            total_seconds = hora_db.seconds
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        
        # Si es datetime.time
        elif hasattr(hora_db, 'hour'):
            return f"{hora_db.hour:02d}:{hora_db.minute:02d}"
        
        # Si es datetime.datetime
        elif hasattr(hora_db, 'strftime'):
            return hora_db.strftime('%H:%M')
        
        # Si ya es string
        elif isinstance(hora_db, str):
            # Limpiar string si tiene segundos
            if ':' in hora_db:
                parts = hora_db.split(':')
                return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
            return hora_db
        
        # Otro tipo
        else:
            return str(hora_db)
            
    except Exception as e:
        print(f"Error convirtiendo hora: {hora_db}, tipo: {type(hora_db)}, error: {e}")
        return None

def procesar_asignacion(asignacion_raw):
    """Procesa una asignación para convertir fechas y horas a strings"""
    if not asignacion_raw:
        return None
    
    if isinstance(asignacion_raw, dict):
        asignacion = asignacion_raw
    else:
        asignacion = dict(asignacion_raw)
    
    # Convertir horas
    asignacion['Hora_Inicio_str'] = convertir_hora_db(asignacion.get('Hora_Inicio'))
    asignacion['Hora_Fin_str'] = convertir_hora_db(asignacion.get('Hora_Fin'))
    
    # Convertir fechas a strings para el template
    if asignacion.get('Fecha_Asignacion'):
        if hasattr(asignacion['Fecha_Asignacion'], 'strftime'):
            asignacion['Fecha_Asignacion_str'] = asignacion['Fecha_Asignacion'].strftime('%d/%m/%Y')
        else:
            asignacion['Fecha_Asignacion_str'] = str(asignacion['Fecha_Asignacion'])
    
    if asignacion.get('Fecha_Finalizacion'):
        if hasattr(asignacion['Fecha_Finalizacion'], 'strftime'):
            asignacion['Fecha_Finalizacion_str'] = asignacion['Fecha_Finalizacion'].strftime('%d/%m/%Y')
        else:
            asignacion['Fecha_Finalizacion_str'] = str(asignacion['Fecha_Finalizacion'])
    
    return asignacion

def procesar_lista_asignaciones(asignaciones_raw):
    """Procesa una lista de asignaciones"""
    return [procesar_asignacion(a) for a in asignaciones_raw if a]


@vendedor_bp.route('/vendedor/dashboard')
@login_required
def vendedor_dashboard():
    # Obtener el ID del usuario logueado (asumiendo que está en session)
    user_id = current_user.id
    empresa_id = session.get('empresa_id', 1)
    
    if not user_id:
        flash('Usuario no autenticado', 'danger')
        return redirect(url_for('auth.login'))
    
    with get_db_cursor() as cursor:
        # 1. Obtener asignaciones activas del vendedor
        cursor.execute("""
            SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta, av.Fecha_Asignacion,
                   av.Estado, av.Hora_Inicio, av.Hora_Fin
            FROM asignacion_vendedores av
            JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
            WHERE av.ID_Usuario = %s 
              AND av.Estado = 'Activa'
              AND DATE(av.Fecha_Asignacion) = CURDATE()
        """, (user_id,))
        asignacion_activa = cursor.fetchone()
        
        # ID de asignación actual (si existe)
        asignacion_id = asignacion_activa['ID_Asignacion'] if asignacion_activa else None
        
        # 2. Tarjeta: Ventas de Contado (Hoy) - EFECTIVO QUE ENTRA
        cursor.execute("""
            SELECT COALESCE(SUM(dfr.Total), 0) AS Total_Ventas_Contado_Hoy
            FROM facturacion_ruta fr
            JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND DATE(fr.Fecha) = CURDATE()
              AND fr.Estado = 'Activa'
              AND fr.Credito_Contado = 1
        """, (user_id,))
        result = cursor.fetchone()
        total_ventas_contado_hoy = result['Total_Ventas_Contado_Hoy'] if result else 0
        
        # 3. Tarjeta: Ventas a Crédito (Hoy) - FIADO
        cursor.execute("""
            SELECT COALESCE(SUM(dfr.Total), 0) AS Total_Ventas_Credito_Hoy
            FROM facturacion_ruta fr
            JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND DATE(fr.Fecha) = CURDATE()
              AND fr.Estado = 'Activa'
              AND fr.Credito_Contado = 2
        """, (user_id,))
        result = cursor.fetchone()
        total_ventas_credito_hoy = result['Total_Ventas_Credito_Hoy'] if result else 0
        
        # 4. Tarjeta: Total Ventas (Contado + Crédito)
        total_ventas_hoy = total_ventas_contado_hoy + total_ventas_credito_hoy
        
        # 5. Tarjeta: Cobros Realizados (Hoy) - ABONOS A CRÉDITO
        cursor.execute("""
            SELECT COALESCE(SUM(ad.Monto_Aplicado), 0) AS Total_Cobrado_Hoy
            FROM abonos_detalle ad
            WHERE ad.ID_Usuario = %s
              AND DATE(ad.Fecha) = CURDATE()
        """, (user_id,))
        result = cursor.fetchone()
        total_cobrado_hoy = result['Total_Cobrado_Hoy'] if result else 0
        
        # 6. Tarjeta: Saldo de Caja (Actual)
        saldo_caja = 0
        if asignacion_id:
            cursor.execute("""
                SELECT Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s
                  AND ID_Asignacion = %s
                  AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC, ID_Movimiento DESC
                LIMIT 1
            """, (user_id, asignacion_id))
            resultado_saldo = cursor.fetchone()
            if resultado_saldo:
                saldo_caja = resultado_saldo['Saldo_Acumulado']
        
        # 7. Tarjeta: Cobros por Vencer (Próximos 7 días)
        cursor.execute("""
            SELECT COUNT(*) AS Cobros_Proximos,
                   COALESCE(SUM(cxc.Saldo_Pendiente), 0) AS Monto_Proximo
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
              AND cxc.Fecha_Vencimiento BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """, (user_id,))
        result = cursor.fetchone()
        cobros_proximos = result['Cobros_Proximos'] if result else 0
        monto_proximo = result['Monto_Proximo'] if result else 0
        
        # 8. Gráfico: Ventas Diarias (Últimos 30 días)
        cursor.execute("""
            SELECT 
                DATE(fr.Fecha) as Dia,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 1 THEN dfr.Total ELSE 0 END), 0) as Ventas_Contado,
                COALESCE(SUM(CASE WHEN fr.Credito_Contado = 2 THEN dfr.Total ELSE 0 END), 0) as Ventas_Credito,
                COALESCE(SUM(dfr.Total), 0) as Total_Ventas
            FROM facturacion_ruta fr
            LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Fecha BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND CURDATE()
              AND fr.Estado = 'Activa'
            GROUP BY DATE(fr.Fecha)
            ORDER BY Dia
        """, (user_id,))
        ventas_diarias = cursor.fetchall()
        
        # Preparar datos para gráfico
        ventas_fechas = [v['Dia'].strftime('%Y-%m-%d') for v in ventas_diarias] if ventas_diarias else []
        ventas_contado = [float(v['Ventas_Contado']) for v in ventas_diarias] if ventas_diarias else []
        ventas_credito = [float(v['Ventas_Credito']) for v in ventas_diarias] if ventas_diarias else []
        
        # 9. Gráfico: Top 5 Productos Más Vendidos
        cursor.execute("""
            SELECT p.Descripcion as Producto, SUM(dfr.Cantidad) as Cantidad_Total,
                   SUM(dfr.Total) as Total_Vendido
            FROM detalle_facturacion_ruta dfr
            JOIN facturacion_ruta fr ON dfr.ID_FacturaRuta = fr.ID_FacturaRuta
            JOIN productos p ON dfr.ID_Producto = p.ID_Producto
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Fecha BETWEEN DATE_SUB(CURDATE(), INTERVAL 30 DAY) AND CURDATE()
              AND fr.Estado = 'Activa'
            GROUP BY p.Descripcion
            ORDER BY Cantidad_Total DESC
            LIMIT 5
        """, (user_id,))
        top_productos = cursor.fetchall()
        
        productos_nombres = [p['Producto'] for p in top_productos] if top_productos else []
        productos_cantidades = [float(p['Cantidad_Total']) for p in top_productos] if top_productos else []
        productos_totales = [float(p['Total_Vendido']) for p in top_productos] if top_productos else []
        
        # 10. Tabla: clientes con Cartera Vencida
        cursor.execute("""
            SELECT c.ID_Cliente, c.Nombre, c.Telefono, cxc.Num_Documento, 
                   cxc.Saldo_Pendiente, cxc.Fecha_Vencimiento,
                   DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
              AND cxc.Fecha_Vencimiento < CURDATE()
            ORDER BY cxc.Fecha_Vencimiento ASC
            LIMIT 10
        """, (user_id,))
        clientes_vencidos = cursor.fetchall()
        
        # 11. Tabla: Movimientos Recientes de Caja
        movimientos_caja = []
        if asignacion_id:
            cursor.execute("""
                SELECT ID_Movimiento, Fecha, Tipo, Concepto, Monto, Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s
                  AND ID_Asignacion = %s
                  AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC
                LIMIT 10
            """, (user_id, asignacion_id))
            movimientos_caja = cursor.fetchall()
        
        # 12. Tabla: Ventas Recientes
        cursor.execute("""
            SELECT fr.ID_FacturaRuta, fr.Fecha, c.Nombre as Cliente, 
                   fr.Credito_Contado,
                   COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                   COUNT(dfr.ID_DetalleRuta) as Num_Productos
            FROM facturacion_ruta fr
            JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
            LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
            WHERE fr.ID_Usuario_Creacion = %s
              AND fr.Estado = 'Activa'
            GROUP BY fr.ID_FacturaRuta, fr.Fecha, c.Nombre, fr.Credito_Contado
            ORDER BY fr.Fecha_Creacion DESC
            LIMIT 10
        """, (user_id,))
        ventas_recientes = cursor.fetchall()
        
        # 13. Resumen de Inventario en Ruta
        inventario_ruta = []
        if asignacion_id:
            cursor.execute("""
                SELECT p.ID_Producto, p.Descripcion, p.COD_Producto, 
                       ir.Cantidad, p.Stock_Minimo,
                       CASE 
                           WHEN ir.Cantidad <= p.Stock_Minimo THEN 'critico'
                           WHEN ir.Cantidad <= p.Stock_Minimo * 2 THEN 'bajo'
                           ELSE 'ok' 
                       END as Nivel_Stock
                FROM inventario_ruta ir
                JOIN productos p ON ir.ID_Producto = p.ID_Producto
                WHERE ir.ID_Asignacion = %s
                ORDER BY Nivel_Stock ASC, p.Descripcion ASC
                LIMIT 20
            """, (asignacion_id,))
            inventario_ruta = cursor.fetchall()
        
        # 14. Resumen de Cartera por Cobrar Total
        cursor.execute("""
            SELECT 
                COUNT(*) as Total_Creditos,
                COALESCE(SUM(Saldo_Pendiente), 0) as Total_Cartera,
                COALESCE(AVG(Saldo_Pendiente), 0) as Promedio_Credito
            FROM cuentas_por_cobrar cxc
            JOIN clientes c ON cxc.ID_Cliente = c.ID_Cliente
            WHERE c.ID_Ruta IN (
                SELECT ID_Ruta FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            )
              AND cxc.Estado = 'Pendiente'
        """, (user_id,))
        resumen_cartera = cursor.fetchone()


        
    return render_template('vendedor/dashboard.html',
                         asignacion_activa=asignacion_activa,
                         asignacion_id=asignacion_id,
                         total_ventas_hoy=total_ventas_hoy,
                         total_ventas_contado_hoy=total_ventas_contado_hoy,
                         total_ventas_credito_hoy=total_ventas_credito_hoy,
                         total_cobrado_hoy=total_cobrado_hoy,
                         saldo_caja=saldo_caja,
                         cobros_proximos=cobros_proximos,
                         monto_proximo=monto_proximo,
                         ventas_fechas=ventas_fechas,
                         ventas_contado=ventas_contado,
                         ventas_credito=ventas_credito,
                         productos_nombres=productos_nombres,
                         productos_cantidades=productos_cantidades,
                         productos_totales=productos_totales,
                         clientes_vencidos=clientes_vencidos,
                         movimientos_caja=movimientos_caja,
                         ventas_recientes=ventas_recientes,
                         inventario_ruta=inventario_ruta,
                         resumen_cartera=resumen_cartera)


# ==============================================
# RUTAS PARA VENDEDORES
# ==============================================
@vendedor_bp.route('/vendedor/mis-rutas')
@vendedor_required
def vendedor_mis_rutas():
    """Vista principal para que el vendedor vea y gestione sus rutas asignadas"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener las asignaciones del vendedor actual
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    ua.NombreUsuario AS Asignado_Por
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
                AND a.Estado IN ('Activa', 'Finalizada', 'Suspendida')
                ORDER BY 
                    CASE 
                        WHEN a.Estado = 'Activa' THEN 1
                        WHEN a.Estado = 'Finalizada' THEN 2
                        WHEN a.Estado = 'Suspendida' THEN 3
                        ELSE 4
                    END,
                    a.Fecha_Asignacion DESC
            """, (usuario_id, empresa_id))
            asignaciones_raw = cursor.fetchall()
            
            # Procesar asignaciones para convertir horas
            asignaciones = procesar_lista_asignaciones(asignaciones_raw)
            
        return render_template(
            'vendedor/rutas/rutas.html',
            asignaciones=asignaciones,
            hoy=datetime.now().strftime('%Y-%m-%d'),
            hora_actual=datetime.now().strftime('%H:%M')
        )
        
    except Exception as e:
        flash(f'Error al cargar rutas: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/vendedor/ruta/iniciar/<int:id>', methods=['POST'])
@vendedor_required
def vendedor_iniciar_ruta(id):
    """Permite al vendedor iniciar su ruta asignada"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        # Verificar que la asignación pertenezca al usuario actual
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT Estado, Hora_Inicio 
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o no pertenece a usted', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Estado'] != 'Activa':
                flash('Solo puede iniciar rutas en estado "Activa"', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Hora_Inicio']:
                flash('La ruta ya ha sido iniciada', 'warning')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
        
        # Obtener la hora de inicio del formulario o usar la actual
        hora_inicio = request.form.get('hora_inicio')
        if not hora_inicio:
            hora_inicio = datetime.now().strftime('%H:%M')
        
        # Actualizar la asignación (solo agregar hora inicio, mantener estado "Activa")
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Hora_Inicio = %s
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (hora_inicio, id, usuario_id, empresa_id))
            
        flash('Ruta iniciada exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al iniciar ruta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_mis_rutas'))

@vendedor_bp.route('/vendedor/ruta/finalizar/<int:id>', methods=['POST'])
@vendedor_required
def vendedor_finalizar_ruta(id):
    """Permite al vendedor finalizar su ruta"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        # Verificar que la asignación pertenezca al usuario actual
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT Estado, Hora_Inicio, Hora_Fin, ID_Vehiculo
                FROM asignacion_vendedores 
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('Asignación no encontrada o no pertenece a usted', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Estado'] != 'Activa':
                flash('Solo puede finalizar rutas en estado "Activa"', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            if asignacion['Hora_Fin']:
                flash('La ruta ya ha sido finalizada', 'warning')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
        
        # Obtener datos del formulario
        hora_fin = request.form.get('hora_fin')
        comentario = request.form.get('comentario', '')
        
        if not hora_fin:
            hora_fin = datetime.now().strftime('%H:%M')
        
        # Actualizar la asignación
        with get_db_cursor(commit=True) as cursor:
            # Actualizar hora de fin y estado
            cursor.execute("""
                UPDATE asignacion_vendedores 
                SET Estado = 'Finalizada',
                    Hora_Fin = %s,
                    Fecha_Finalizacion = CURDATE()
                WHERE ID_Asignacion = %s 
                AND ID_Usuario = %s 
                AND ID_Empresa = %s
            """, (hora_fin, id, usuario_id, empresa_id))
            
            # Liberar el vehículo si estaba asignado
            if asignacion['ID_Vehiculo']:
                cursor.execute("""
                    UPDATE vehiculos 
                    SET Estado = 'Disponible' 
                    WHERE ID_Vehiculo = %s
                """, (asignacion['ID_Vehiculo'],))
            
        flash('Ruta finalizada exitosamente', 'success')
        
    except Exception as e:
        flash(f'Error al finalizar ruta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_mis_rutas'))

@vendedor_bp.route('/vendedor/ruta/detalle/<int:id>')
@vendedor_required
def vendedor_detalle_ruta(id):
    """Detalle de una ruta específica del vendedor"""
    try:
        empresa_id = session.get('id_empresa', 1)
        usuario_id = current_user.id
        
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT 
                    a.ID_Asignacion,
                    r.Nombre_Ruta,
                    r.Descripcion AS Descripcion_Ruta,
                    v.Placa,
                    v.Marca,
                    v.Modelo,
                    a.Fecha_Asignacion,
                    a.Fecha_Finalizacion,
                    a.Estado,
                    a.Hora_Inicio,
                    a.Hora_Fin,
                    ua.NombreUsuario AS Asignado_Por,
                    a.Fecha_Creacion
                FROM asignacion_vendedores a
                LEFT JOIN rutas r ON a.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON a.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios ua ON a.ID_Usuario_Asigna = ua.ID_Usuario
                WHERE a.ID_Asignacion = %s 
                AND a.ID_Usuario = %s 
                AND a.ID_Empresa = %s
            """, (id, usuario_id, empresa_id))
            
            asignacion_raw = cursor.fetchone()
            
            if not asignacion_raw:
                flash('Ruta no encontrada o no tiene acceso', 'error')
                return redirect(url_for('vendedor.vendedor_mis_rutas'))
            
            # Procesar la asignación para convertir horas
            asignacion = procesar_asignacion(asignacion_raw)
            
        return render_template('vendedor/rutas/detalle_ruta.html', asignacion=asignacion)
        
    except Exception as e:
        flash(f'Error al cargar detalle: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_mis_rutas'))

## Inventario ruta:
@vendedor_bp.route('/vendedor/inventario')
@vendedor_required
def vendedor_inventario():
    """
    Muestra el inventario actual del vendedor basado en su asignación activa de hoy
    """
    try:
        with get_db_cursor(True) as cursor:
            # ============================================
            # 1. OBTENER ASIGNACIÓN ACTIVA DEL VENDEDOR HOY
            # ============================================
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    av.ID_Ruta,
                    r.Nombre_Ruta,
                    av.Fecha_Asignacion,
                    av.Hora_Inicio,
                    av.Hora_Fin,
                    v.Marca as Vehiculo,
                    v.Placa
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return render_template('vendedor/inventario/inventario.html', 
                                     asignacion=None,
                                     inventario=[],
                                     totales={})
            
            # ============================================
            # 2. OBTENER INVENTARIO DEL VENDEDOR
            # ============================================
            cursor.execute("""
                SELECT 
                    ir.ID_Inventario_Ruta,
                    ir.ID_Producto,
                    ir.Cantidad,
                    ir.Fecha_Actualizacion,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Ruta as Precio_Venta,
                    p.Stock_Minimo,
                    um.Descripcion as Unidad,
                    um.Abreviatura as Unidad_Abrev,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            # ============================================
            # 3. CALCULAR TOTALES
            # ============================================
            total_productos = len(inventario)
            total_unidades = sum(float(item['Cantidad']) for item in inventario)
            total_valor = sum(float(item['Cantidad']) * float(item['Precio_Venta']) for item in inventario)
            
            # Productos con stock bajo (menor al mínimo)
            stock_bajo = []
            for item in inventario:
                if float(item['Cantidad']) <= float(item['Stock_Minimo'] or 0):
                    stock_bajo.append(item)
            
            # ============================================
            # 4. OBTENER VENTAS DEL DÍA USANDO movimientos_ruta_cabecera (CORREGIDO)
            # ============================================
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(Total_Subtotal), 0) as total_vendido,
                    COALESCE(SUM(Total_Items), 0) as total_items,
                    COALESCE(SUM(Total_Productos), 0) as total_productos_vendidos
                FROM movimientos_ruta_cabecera
                WHERE ID_Asignacion = %s
                AND ID_TipoMovimiento = 3  -- Tipo Venta
                AND DATE(Fecha_Movimiento) = CURDATE()
                AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            ventas_hoy = cursor.fetchone()
            
            totales = {
                'total_productos': total_productos,
                'total_unidades': total_unidades,
                'total_valor': total_valor,
                'stock_bajo': len(stock_bajo),
                'ventas_hoy': ventas_hoy['total_ventas'] if ventas_hoy else 0,
                'vendido_hoy': float(ventas_hoy['total_vendido']) if ventas_hoy else 0,
                'items_vendidos': int(ventas_hoy['total_items']) if ventas_hoy else 0,
                'productos_vendidos': int(ventas_hoy['total_productos_vendidos']) if ventas_hoy else 0
            }
            
            return render_template('vendedor/inventario/inventario.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 stock_bajo=stock_bajo,
                                 totales=totales,
                                 now=datetime.now())
            
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar inventario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/api/vendedor/inventario')
@login_required
def api_vendedor_inventario():
    """
    API para consultar inventario del vendedor (formato JSON)
    Utiliza current_user.id para identificar al vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                AND Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({
                    'success': False,
                    'message': 'No tienes asignación activa hoy',
                    'data': []
                })
            
            # Obtener inventario
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad,
                    p.Descripcion as producto,
                    p.COD_Producto as codigo,
                    p.Precio_Ruta as precio,
                    um.Abreviatura as unidad
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'data': inventario
            })
            
    except Exception as e:
        print(f"Error en API inventario: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'data': []
        }), 500

@vendedor_bp.route('/vendedor/producto/<int:id_producto>')
@login_required
def vendedor_producto_detalle(id_producto):
    """
    Muestra el detalle de un producto específico en el inventario del vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                AND Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener detalle del producto
            cursor.execute("""
                SELECT 
                    ir.ID_Inventario_Ruta,
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    ir.Fecha_Actualizacion,
                    p.Descripcion as Nombre_Producto,
                    p.COD_Producto,
                    p.Precio_Ruta as Precio_Venta,
                    p.Stock_Minimo,
                    um.Descripcion as Unidad,
                    um.Abreviatura as Unidad_Abrev,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.ID_Producto = %s
                LIMIT 1
            """, (asignacion['ID_Asignacion'], id_producto))
            
            producto = cursor.fetchone()
            
            if not producto:
                flash('Producto no encontrado en tu inventario', 'error')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener historial de movimientos de este producto (CORREGIDO)
            cursor.execute("""
                SELECT 
                    mrc.ID_Movimiento,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    mrc.Total_Subtotal,
                    mrd.Cantidad,
                    mrd.Precio_Unitario,
                    mrd.Subtotal,
                    cm.Descripcion as Tipo_Movimiento
                FROM movimientos_ruta_detalle mrd
                INNER JOIN movimientos_ruta_cabecera mrc ON mrd.ID_Movimiento = mrc.ID_Movimiento
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mrc.ID_Asignacion = %s
                AND mrd.ID_Producto = %s
                ORDER BY mrc.Fecha_Movimiento DESC
                LIMIT 20
            """, (asignacion['ID_Asignacion'], id_producto))
            
            historial = cursor.fetchall()
            
            return render_template('vendedor/inventario/producto_detalle.html',
                                 producto=producto,
                                 historial=historial,
                                 now=datetime.now(),
                                 current_user=current_user)
            
    except Exception as e:
        print(f"Error en vendedor_producto_detalle: {str(e)}")
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))

@vendedor_bp.route('/vendedor/refrescar-inventario', methods=['POST'])
@login_required
def vendedor_refrescar_inventario():
    """
    Refresca el inventario del vendedor (útil después de una venta)
    Utiliza current_user.id para identificar al vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # Obtener asignación activa del usuario actual
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s
                AND Estado = 'Activa'
                AND Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({
                    'success': False,
                    'message': 'No tienes asignación activa hoy'
                })
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_productos,
                    COALESCE(SUM(Cantidad), 0) as total_unidades,
                    COALESCE(SUM(Cantidad * p.Precio_Ruta), 0) as total_valor
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                WHERE ir.ID_Asignacion = %s
            """, (asignacion['ID_Asignacion'],))
            
            totales = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'data': {
                    'total_productos': int(totales['total_productos']),
                    'total_unidades': float(totales['total_unidades']),
                    'total_valor': float(totales['total_valor'])
                }
            })
            
    except Exception as e:
        print(f"Error en refrescar inventario: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ============================================
# RUTAS PARA GESTIÓN DE MOVIMIENTOS DE INVENTARIO
# ============================================

@vendedor_bp.route('/vendedor/movimientos/entrada-bodega', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_entrada_bodega():
    """
    Registra una entrada de inventario desde bodega central
    Usando ID_TipoMovimiento = 13 (Traslado Entrada)
    """

    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    AND av.Fecha_Asignacion = CURDATE()
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPO DE MOVIMIENTO (Traslado Entrada)
                # ============================================
                ID_TIPO_ENTRADA = 1  # Traslado Entrada
                
                # ============================================
                # 3. PROCESAR PRODUCTOS Y CALCULAR TOTALES
                # ============================================
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                productos_procesar = []
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Obtener precio del producto
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio': precio,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_entrada_bodega'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO CABECERA
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_ENTRADA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa
                ))
                
                id_movimiento = cursor.lastrowid
                
                # ============================================
                # 5. CREAR DETALLES Y ACTUALIZAR INVENTARIO
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio'], 
                        prod['subtotal']
                    ))
                    
                    # Actualizar inventario (SUMAR cantidad)
                    cursor.execute("""
                        INSERT INTO inventario_ruta 
                        (ID_Asignacion, ID_Producto, Cantidad)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Cantidad = Cantidad + VALUES(Cantidad)
                    """, (id_asignacion, prod['id_producto'], prod['cantidad']))
                
                flash('Entrada de inventario registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento))
                    
        except Exception as e:
            print(f"Error en movimiento entrada: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar entrada: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener productos activos
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE p.Estado = 'activo'
                ORDER BY c.Descripcion, p.Descripcion
            """)
            
            productos = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_entrada_bodega.html',
                                 asignacion=asignacion,
                                 productos=productos,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))

@vendedor_bp.route('/vendedor/movimientos/devolucion-bodega', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_devolucion_bodega():
    """
    Registra una devolución de productos no vendidos a bodega central
    Usando ID_TipoMovimiento = 11 (Devolucion Ruta)
    """

    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            observacion = request.form.get('observacion', '')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    AND av.Fecha_Asignacion = CURDATE()
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPOS DE MOVIMIENTO
                # ============================================
                ID_TIPO_DEVOLUCION_RUTA = 11  # Devolucion Ruta (para tabla de rutas)
                ID_TIPO_ENTRADA_BODEGA = 11    # Entrada a bodega por devolución (ajusta según tu catálogo)
                ID_BODEGA_CENTRAL = 1          # ID de la bodega central según tu tabla bodegas
                
                # ============================================
                # 3. VALIDAR STOCK Y CALCULAR TOTALES
                # ============================================
                productos_procesar = []
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Verificar stock actual en ruta
                        cursor.execute("""
                            SELECT Cantidad 
                            FROM inventario_ruta 
                            WHERE ID_Asignacion = %s AND ID_Producto = %s
                        """, (id_asignacion, id_producto))
                        
                        stock = cursor.fetchone()
                        if not stock or float(stock['Cantidad']) < cantidad:
                            flash(f'Stock insuficiente para devolución. Stock actual: {float(stock["Cantidad"]) if stock else 0}', 'error')
                            return redirect(url_for('vendedor.vendedor_movimiento_devolucion_bodega'))
                        
                        # Obtener precio del producto (Precio_Ruta)
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio_ruta = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio_ruta
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio_ruta': precio_ruta,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_devolucion_bodega'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO EN movimientos_ruta_cabecera
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_DEVOLUCION_RUTA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa
                ))
                
                id_movimiento_ruta = cursor.lastrowid
                
                # ============================================
                # 5. CREAR MOVIMIENTO EN movimientos_inventario (TABLA GENERAL)
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (ID_TipoMovimiento, N_Factura_Externa, Fecha, Observacion, 
                     ID_Empresa, ID_Bodega, ID_Usuario_Creacion, Estado)
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, 'Activa')
                """, (
                    ID_TIPO_ENTRADA_BODEGA,
                    documento,
                    f"Devolución de ruta: {asignacion['Nombre_Ruta']} - {observacion}" if observacion else f"Devolución de ruta: {asignacion['Nombre_Ruta']}",
                    id_empresa,
                    ID_BODEGA_CENTRAL,
                    current_user.id
                ))
                
                id_movimiento_inventario = cursor.lastrowid
                
                # ============================================
                # 6. CREAR DETALLES Y ACTUALIZAR INVENTARIOS
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle en movimientos_ruta_detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_ruta, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio_ruta'], 
                        prod['subtotal']
                    ))
                    
                    # Insertar detalle en detalle_movimientos_inventario (tabla general)
                    # Nota: Como no tenemos precio de costo, usamos Precio_Ruta como referencia
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_inventario,
                        prod['id_producto'],
                        prod['cantidad'],
                        prod['precio_ruta'],  # Precio_Unitario
                        prod['subtotal'],      # Subtotal
                        current_user.id
                    ))
                    
                    # Actualizar inventario_ruta (RESTAR cantidad)
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], id_asignacion, prod['id_producto']))
                    
                    # Actualizar inventario_bodega (SUMAR cantidad)
                    cursor.execute("""
                        INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Existencias = Existencias + %s
                    """, (
                        ID_BODEGA_CENTRAL,
                        prod['id_producto'],
                        prod['cantidad'],
                        prod['cantidad']
                    ))
                
                flash('Devolución a bodega registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento_ruta))
                    
        except Exception as e:
            print(f"Error en devolución: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar devolución: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener inventario actual (solo productos con stock)
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_devolucion_bodega.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))

@vendedor_bp.route('/vendedor/movimientos/merma', methods=['GET', 'POST'])
@vendedor_required
def vendedor_movimiento_merma():
    """
    Registra una salida por merma/pérdida de productos
    Usando ID_TipoMovimiento = 7 (Merma)
    """
    id_empresa = session.get('id_empresa', 1)

    if request.method == 'POST':
        try:
            productos = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            documento = request.form.get('documento_numero', '')
            
            with get_db_cursor(True) as cursor:
                # ============================================
                # 1. VERIFICAR ASIGNACIÓN ACTIVA
                # ============================================
                cursor.execute("""
                    SELECT 
                        av.ID_Asignacion,
                        av.ID_Ruta,
                        r.Nombre_Ruta
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    WHERE av.ID_Usuario = %s
                    AND av.Estado = 'Activa'
                    AND av.Fecha_Asignacion = CURDATE()
                    LIMIT 1
                """, (current_user.id,))
                
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una asignación activa para hoy', 'error')
                    return redirect(url_for('vendedor.vendedor_inventario'))
                
                id_asignacion = asignacion['ID_Asignacion']
                
                # ============================================
                # 2. DEFINIR TIPO DE MOVIMIENTO (Merma)
                # ============================================
                ID_TIPO_MERMA = 7  # Merma
                
                # ============================================
                # 3. VALIDAR STOCK Y CALCULAR TOTALES
                # ============================================
                productos_procesar = []
                total_productos = 0
                total_items = 0
                total_subtotal = 0
                
                for i in range(len(productos)):
                    if productos[i] and cantidades[i] and float(cantidades[i]) > 0:
                        id_producto = int(productos[i])
                        cantidad = float(cantidades[i])
                        
                        # Verificar stock actual
                        cursor.execute("""
                            SELECT Cantidad 
                            FROM inventario_ruta 
                            WHERE ID_Asignacion = %s AND ID_Producto = %s
                        """, (id_asignacion, id_producto))
                        
                        stock = cursor.fetchone()
                        if not stock or float(stock['Cantidad']) < cantidad:
                            flash(f'Stock insuficiente para merma. Stock actual: {float(stock["Cantidad"]) if stock else 0}', 'error')
                            return redirect(url_for('vendedor.vendedor_movimiento_merma'))
                        
                        # Obtener precio del producto
                        cursor.execute("""
                            SELECT Precio_Ruta 
                            FROM productos 
                            WHERE ID_Producto = %s
                        """, (id_producto,))
                        
                        producto_info = cursor.fetchone()
                        if not producto_info:
                            continue
                            
                        precio = float(producto_info['Precio_Ruta'])
                        subtotal = cantidad * precio
                        
                        productos_procesar.append({
                            'id_producto': id_producto,
                            'cantidad': cantidad,
                            'precio': precio,
                            'subtotal': subtotal
                        })
                        
                        total_productos += 1
                        total_items += 1
                        total_subtotal += subtotal
                
                if not productos_procesar:
                    flash('Debe agregar al menos un producto', 'error')
                    return redirect(url_for('vendedor.vendedor_movimiento_merma'))
                
                # ============================================
                # 4. CREAR MOVIMIENTO CABECERA
                # ============================================
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera 
                    (ID_Asignacion, ID_TipoMovimiento, ID_Usuario_Registra, 
                     Documento_Numero, Total_Productos, Total_Items, Total_Subtotal,
                     ID_Empresa, Estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    id_asignacion, 
                    ID_TIPO_MERMA, 
                    current_user.id,
                    documento, 
                    total_productos, 
                    total_items, 
                    total_subtotal,
                    id_empresa, 
                ))
                
                id_movimiento = cursor.lastrowid
                
                # ============================================
                # 5. CREAR DETALLES Y ACTUALIZAR INVENTARIO
                # ============================================
                for prod in productos_procesar:
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        prod['id_producto'], 
                        prod['cantidad'], 
                        prod['precio'], 
                        prod['subtotal']
                    ))
                    
                    # Actualizar inventario (RESTAR cantidad)
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], id_asignacion, prod['id_producto']))
                
                flash('Merma registrada exitosamente', 'success')
                return redirect(url_for('vendedor.vendedor_movimiento_detalle', id_movimiento=id_movimiento))
                    
        except Exception as e:
            print(f"Error en merma: {str(e)}")
            traceback.print_exc()
            flash(f'Error al registrar merma: {str(e)}', 'error')
            return redirect(url_for('vendedor.vendedor_inventario'))
    
    # ============================================
    # MÉTODO GET - MOSTRAR FORMULARIO
    # ============================================
    try:
        with get_db_cursor(True) as cursor:
            # Verificar asignación
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    r.Nombre_Ruta
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # Obtener inventario actual (solo productos con stock)
            cursor.execute("""
                SELECT 
                    ir.ID_Producto,
                    ir.Cantidad as Stock_Actual,
                    p.COD_Producto,
                    p.Descripcion as Nombre_Producto,
                    p.Precio_Ruta,
                    um.Abreviatura as Unidad,
                    c.Descripcion as Categoria
                FROM inventario_ruta ir
                INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                WHERE ir.ID_Asignacion = %s
                AND ir.Cantidad > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            return render_template('vendedor/inventario/movimiento_merma.html',
                                 asignacion=asignacion,
                                 inventario=inventario,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar formulario: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))

@vendedor_bp.route('/vendedor/movimientos/historial')
@vendedor_required
def vendedor_movimientos_historial():
    """
    Muestra el historial de movimientos de inventario del vendedor
    """
    try:
        with get_db_cursor(True) as cursor:
            # ============================================
            # 1. OBTENER ASIGNACIÓN ACTIVA
            # ============================================
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    av.ID_Ruta,
                    r.Nombre_Ruta,
                    av.ID_Empresa,
                    av.Fecha_Asignacion,
                    av.Fecha_Finalizacion
                FROM asignacion_vendedores av
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND CURDATE() BETWEEN av.Fecha_Asignacion AND COALESCE(av.Fecha_Finalizacion, CURDATE())
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una asignación activa para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_inventario'))
            
            # ============================================
            # 2. OBTENER MOVIMIENTOS (CON Total_Items)
            # ============================================
            cursor.execute("""
                SELECT 
                    mrc.ID_Movimiento,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra as Tipo_Letra,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    CAST(COALESCE(mrc.Total_Productos, 0) AS DECIMAL(12,2)) as Total_Productos,
                    CAST(COALESCE(mrc.Total_Subtotal, 0) AS DECIMAL(12,2)) as Total_Subtotal,
                    COALESCE(mrc.Total_Items, 0) as Total_Items,
                    mrc.Estado,
                    u.NombreUsuario as Usuario_Registra,
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Carga de Productos'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolución'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        ELSE 'Otro'
                    END as Descripcion_Detallada
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm 
                    ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN usuarios u 
                    ON mrc.ID_Usuario_Registra = u.ID_Usuario
                WHERE mrc.ID_Asignacion = %s
                    AND mrc.ID_TipoMovimiento IN (1, 2, 7, 11, 13)
                    AND mrc.Estado = 'ACTIVO'
                ORDER BY mrc.Fecha_Movimiento DESC
            """, (asignacion['ID_Asignacion'],))
            
            movimientos = cursor.fetchall()
            
            # Convertir valores numéricos
            for mov in movimientos:
                if 'Total_Productos' in mov:
                    mov['Total_Productos'] = float(mov['Total_Productos']) if mov['Total_Productos'] else 0.0
                if 'Total_Subtotal' in mov:
                    mov['Total_Subtotal'] = float(mov['Total_Subtotal']) if mov['Total_Subtotal'] else 0.0
                if 'Total_Items' in mov:
                    mov['Total_Items'] = int(mov['Total_Items']) if mov['Total_Items'] else 0
            
            # ============================================
            # 3. RESUMEN SIMPLIFICADO
            # ============================================
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Carga de Productos'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolución'
                        ELSE cm.Descripcion
                    END as Tipo_Movimiento,
                    COUNT(*) as Cantidad_Movimientos,
                    CAST(SUM(COALESCE(mrc.Total_Productos, 0)) AS DECIMAL(12,2)) as Total_Productos
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mrc.ID_Asignacion = %s
                AND mrc.ID_TipoMovimiento IN (1, 2, 7, 11, 13)
                AND mrc.Estado = 'ACTIVO'
                GROUP BY Tipo_Movimiento
                ORDER BY Cantidad_Movimientos DESC
            """, (asignacion['ID_Asignacion'],))
            
            resumen_movimientos = cursor.fetchall()
            
            # Convertir valores del resumen
            for res in resumen_movimientos:
                if 'Total_Productos' in res:
                    res['Total_Productos'] = float(res['Total_Productos']) if res['Total_Productos'] else 0.0
            
            return render_template('vendedor/inventario/historial_movimientos.html',
                                 movimientos=movimientos,
                                 resumen_movimientos=resumen_movimientos,
                                 asignacion=asignacion,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error en vendedor_movimientos_historial: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar historial: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_inventario'))

@vendedor_bp.route('/vendedor/movimientos/detalle/<int:id_movimiento>')
@vendedor_required
def vendedor_movimiento_detalle(id_movimiento):
    """
    Muestra el detalle de un movimiento específico
    """
    try:
        print(f"\n=== DEPURACIÓN DETALLE MOVIMIENTO ===")
        print(f"ID Movimiento solicitado: {id_movimiento}")
        print(f"Usuario actual ID: {current_user.id}")
        print(f"Usuario actual nombre: {current_user.username if hasattr(current_user, 'username') else 'N/A'}")
        
        with get_db_cursor(True) as cursor:
            # ============================================
            # PRUEBA 1: Verificar si el movimiento existe
            # ============================================
            print("\n--- PRUEBA 1: Verificar existencia del movimiento ---")
            cursor.execute("""
                SELECT ID_Movimiento, ID_Asignacion, Estado, ID_TipoMovimiento
                FROM movimientos_ruta_cabecera 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento_raw = cursor.fetchone()
            
            if not movimiento_raw:
                print(f"ERROR: El movimiento {id_movimiento} NO existe en la base de datos")
                flash(f'Movimiento #{id_movimiento} no existe en el sistema', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            print(f"Movimiento encontrado: ID={movimiento_raw['ID_Movimiento']}, Asignacion={movimiento_raw['ID_Asignacion']}, Estado={movimiento_raw['Estado']}")
            
            # ============================================
            # PRUEBA 2: Verificar la asignación del movimiento
            # ============================================
            print("\n--- PRUEBA 2: Verificar asignación del movimiento ---")
            cursor.execute("""
                SELECT 
                    av.ID_Asignacion,
                    av.ID_Usuario,
                    av.Estado as Estado_Asignacion,
                    u.NombreUsuario
                FROM asignacion_vendedores av
                LEFT JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Asignacion = %s
            """, (movimiento_raw['ID_Asignacion'],))
            
            asignacion_mov = cursor.fetchone()
            
            if not asignacion_mov:
                print(f"ERROR: La asignación {movimiento_raw['ID_Asignacion']} NO existe")
                flash('El movimiento no tiene una asignación válida', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            print(f"Asignación encontrada: ID={asignacion_mov['ID_Asignacion']}, Usuario={asignacion_mov['ID_Usuario']}, Estado={asignacion_mov['Estado_Asignacion']}")
            print(f"¿Coincide con usuario actual? {asignacion_mov['ID_Usuario'] == current_user.id}")
            
            # ============================================
            # PRUEBA 3: Verificar asignación activa del vendedor actual
            # ============================================
            print("\n--- PRUEBA 3: Verificar asignación activa del vendedor ---")
            cursor.execute("""
                SELECT 
                    ID_Asignacion, 
                    ID_Ruta, 
                    Estado,
                    Fecha_Asignacion,
                    Fecha_Finalizacion
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND Estado = 'Activa'
                AND CURDATE() BETWEEN Fecha_Asignacion AND COALESCE(Fecha_Finalizacion, CURDATE())
                ORDER BY Fecha_Asignacion DESC
                LIMIT 1
            """, (current_user.id,))
            
            asignacion_activa = cursor.fetchone()
            
            if asignacion_activa:
                print(f"Asignación activa encontrada: ID={asignacion_activa['ID_Asignacion']}, Ruta={asignacion_activa['ID_Ruta']}")
            else:
                print("No se encontró asignación activa para el vendedor actual")
            
            # ============================================
            # CONSULTA FINAL CON PERMISOS FLEXIBLES
            # ============================================
            print("\n--- CONSULTA FINAL: Obteniendo datos completos ---")
            
            # Construir condición de permisos
            condiciones = []
            params = [id_movimiento]
            
            condiciones.append("av.ID_Usuario = %s")
            params.append(current_user.id)
            
            condiciones.append("mrc.ID_Usuario_Registra = %s")
            params.append(current_user.id)
            
            if asignacion_activa:
                condiciones.append("mrc.ID_Asignacion = %s")
                params.append(asignacion_activa['ID_Asignacion'])
            
            where_permisos = " OR ".join(condiciones)
            
            query = f"""
                SELECT 
                    mrc.ID_Movimiento,
                    mrc.ID_Asignacion,
                    mrc.ID_TipoMovimiento,
                    mrc.Fecha_Movimiento,
                    mrc.Documento_Numero,
                    mrc.Total_Productos,
                    mrc.Total_Subtotal,
                    mrc.Total_Items,
                    mrc.Estado,
                    mrc.ID_Cliente,
                    mrc.ID_Pedido,
                    cm.Descripcion as Tipo_Movimiento_Desc,
                    cm.Letra as Tipo_Letra,
                    u.NombreUsuario as Usuario_Registra,
                    r.Nombre_Ruta,
                    av.ID_Ruta as Ruta_Asignada,
                    av.ID_Usuario as ID_Vendedor_Asignado,
                    fr.Credito_Contado,
                    CASE 
                        WHEN mrc.ID_TipoMovimiento = 13 THEN 'Carga de Productos'
                        WHEN mrc.ID_TipoMovimiento = 1 THEN 'Compra'
                        WHEN mrc.ID_TipoMovimiento = 2 THEN 'Venta'
                        WHEN mrc.ID_TipoMovimiento = 7 THEN 'Merma'
                        WHEN mrc.ID_TipoMovimiento = 11 THEN 'Devolución'
                        ELSE cm.Descripcion
                    END as Descripcion_Detallada,
                    CAST(COALESCE(mrc.Total_Productos, 0) AS DECIMAL(12,2)) as Total_Productos_Num,
                    CAST(COALESCE(mrc.Total_Subtotal, 0) AS DECIMAL(12,2)) as Total_Subtotal_Num
                FROM movimientos_ruta_cabecera mrc
                INNER JOIN catalogo_movimientos cm ON mrc.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN usuarios u ON mrc.ID_Usuario_Registra = u.ID_Usuario
                LEFT JOIN asignacion_vendedores av ON mrc.ID_Asignacion = av.ID_Asignacion
                LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN facturacion_ruta fr ON mrc.ID_Movimiento = fr.ID_Movimiento
                WHERE mrc.ID_Movimiento = %s
                AND mrc.Estado = 'ACTIVO'
                AND ({where_permisos})
            """
            
            print(f"Query ejecutada: {query}")
            print(f"Parámetros: {params}")
            
            cursor.execute(query, params)
            movimiento = cursor.fetchone()
            
            if not movimiento:
                print("ERROR: No se encontró el movimiento con los permisos actuales")
                flash('Movimiento no encontrado o no tienes permiso para verlo', 'error')
                return redirect(url_for('vendedor.vendedor_movimientos_historial'))
            
            print(f"Movimiento encontrado exitosamente: #{movimiento['ID_Movimiento']}")
            
            # Convertir valores numéricos
            movimiento['Total_Productos'] = float(movimiento['Total_Productos_Num']) if movimiento.get('Total_Productos_Num') else 0
            movimiento['Total_Subtotal'] = float(movimiento['Total_Subtotal_Num']) if movimiento.get('Total_Subtotal_Num') else 0
            
            # ============================================
            # OBTENER DETALLES DEL MOVIMIENTO
            # ============================================
            print("\n--- Obteniendo detalles del movimiento ---")
            cursor.execute("""
                SELECT 
                    mrd.ID_Detalle,
                    mrd.Cantidad,
                    mrd.Precio_Unitario,
                    mrd.Subtotal,
                    mrd.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Nombre,
                    um.Abreviatura as Unidad_Medida,
                    CAST(COALESCE(mrd.Cantidad, 0) AS DECIMAL(12,2)) as Cantidad_Num,
                    CAST(COALESCE(mrd.Precio_Unitario, 0) AS DECIMAL(12,2)) as Precio_Unitario_Num,
                    CAST(COALESCE(mrd.Subtotal, 0) AS DECIMAL(12,2)) as Subtotal_Num
                FROM movimientos_ruta_detalle mrd
                INNER JOIN productos p ON mrd.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE mrd.ID_Movimiento = %s
                ORDER BY mrd.ID_Detalle ASC
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            print(f"Detalles encontrados: {len(detalles)}")
            
            # Convertir valores numéricos en detalles
            for detalle in detalles:
                detalle['Cantidad'] = float(detalle['Cantidad_Num']) if detalle.get('Cantidad_Num') else 0
                detalle['Precio_Unitario'] = float(detalle['Precio_Unitario_Num']) if detalle.get('Precio_Unitario_Num') else 0
                detalle['Subtotal'] = float(detalle['Subtotal_Num']) if detalle.get('Subtotal_Num') else 0
                
                # Limpiar campos temporales
                if 'Cantidad_Num' in detalle:
                    del detalle['Cantidad_Num']
                if 'Precio_Unitario_Num' in detalle:
                    del detalle['Precio_Unitario_Num']
                if 'Subtotal_Num' in detalle:
                    del detalle['Subtotal_Num']
            
            # ============================================
            # OBTENER INFORMACIÓN DEL CLIENTE
            # ============================================
            cliente_info = None
            if movimiento.get('ID_Cliente') and movimiento['ID_Cliente']:
                cursor.execute("""
                    SELECT ID_Cliente, Nombre, RUC_CEDULA as RUC, Direccion, Telefono
                    FROM clientes WHERE ID_Cliente = %s
                """, (movimiento['ID_Cliente'],))
                cliente_info = cursor.fetchone()
                print(f"Cliente encontrado: {cliente_info['Nombre'] if cliente_info else 'No'}")
            
            # ============================================
            # OBTENER INFORMACIÓN DE LA ASIGNACIÓN
            # ============================================
            asignacion_info = None
            if movimiento.get('ID_Asignacion'):
                cursor.execute("""
                    SELECT av.ID_Asignacion, av.Fecha_Asignacion, av.Fecha_Finalizacion,
                           av.Estado as Estado_Asignacion, r.Nombre_Ruta, u.NombreUsuario as Vendedor_Nombre
                    FROM asignacion_vendedores av
                    LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Asignacion = %s
                """, (movimiento['ID_Asignacion'],))
                asignacion_info = cursor.fetchone()
            
            print("=== DEPURACIÓN COMPLETADA ===\n")
            
            return render_template('vendedor/inventario/detalle_movimiento.html',
                                 movimiento=movimiento,
                                 detalles=detalles,
                                 cliente_info=cliente_info,
                                 asignacion_info=asignacion_info,
                                 now=datetime.now())
                                 
    except Exception as e:
        print(f"Error en vendedor_movimiento_detalle: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar detalle del movimiento: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_movimientos_historial'))

#ventas rutas
# =============================================
# RUTAS PARA VENTAS EN RUTA
# =============================================
@vendedor_bp.route('/vendedor/ventas')
@vendedor_required
def vendedor_ventas():
    """Visualizar listado de ventas realizadas por el vendedor (solo del día actual)
    """
    try:
        id_vendedor = current_user.id
        id_empresa = session.get('empresa_id')
        
        with get_db_cursor(True) as cursor:
            # Obtener asignaciones del vendedor para el filtro
            cursor.execute("""
                SELECT av.ID_Asignacion, r.Nombre_Ruta, 
                       av.Fecha_Asignacion,
                       av.Estado as Estado_Asignacion
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s 
                ORDER BY av.Fecha_Asignacion DESC
            """, (id_vendedor,))
            asignaciones_raw = cursor.fetchall()
            
            # Formatear fechas de asignaciones
            asignaciones = []
            from datetime import datetime
            for a in asignaciones_raw:
                a_dict = dict(a)
                if a_dict.get('Fecha_Asignacion'):
                    if isinstance(a_dict['Fecha_Asignacion'], datetime):
                        a_dict['Fecha_Asignacion'] = a_dict['Fecha_Asignacion'].strftime('%d/%m/%Y')
                    else:
                        try:
                            fecha_obj = datetime.strptime(str(a_dict['Fecha_Asignacion']), '%Y-%m-%d')
                            a_dict['Fecha_Asignacion'] = fecha_obj.strftime('%d/%m/%Y')
                        except:
                            a_dict['Fecha_Asignacion'] = 'Fecha no disponible'
                else:
                    a_dict['Fecha_Asignacion'] = 'Fecha no disponible'
                asignaciones.append(a_dict)
            
            # Obtener ventas del día actual del vendedor
            ventas = []
            if asignaciones_raw:
                ids_asignacion = [a['ID_Asignacion'] for a in asignaciones_raw]
                placeholders = ','.join(['%s'] * len(ids_asignacion))
                
                cursor.execute(f"""
                    SELECT fr.ID_FacturaRuta, 
                           fr.Fecha,
                           fr.Fecha_Creacion,
                           fr.Credito_Contado,
                           fr.Observacion, 
                           fr.Estado, 
                           c.Nombre as Cliente, 
                           c.RUC_CEDULA,
                           c.Telefono,
                           r.Nombre_Ruta,
                           COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                           CASE 
                               WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                               ELSE 'CRÉDITO'
                           END as Tipo_Venta,
                           CASE 
                               WHEN fr.Credito_Contado = 2 THEN (
                                   SELECT COALESCE(SUM(Saldo_Pendiente), 0)
                                   FROM cuentas_por_cobrar 
                                   WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                               )
                               ELSE 0
                           END as Saldo_Pendiente
                    FROM facturacion_ruta fr
                    INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                    INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                    WHERE fr.ID_Asignacion IN ({placeholders})
                      AND DATE(fr.Fecha) = CURDATE()
                    GROUP BY fr.ID_FacturaRuta
                    ORDER BY fr.Fecha DESC, fr.ID_FacturaRuta DESC
                    LIMIT 15
                """, tuple(ids_asignacion))
                ventas_raw = cursor.fetchall()
                
                # Formatear fechas de ventas
                for v in ventas_raw:
                    venta_dict = dict(v)
                    
                    # Formatear Fecha
                    if venta_dict.get('Fecha'):
                        if isinstance(venta_dict['Fecha'], datetime):
                            venta_dict['Fecha'] = venta_dict['Fecha'].strftime('%d/%m/%Y')
                        else:
                            try:
                                fecha_obj = datetime.strptime(str(venta_dict['Fecha']), '%Y-%m-%d')
                                venta_dict['Fecha'] = fecha_obj.strftime('%d/%m/%Y')
                            except:
                                venta_dict['Fecha'] = 'Fecha no disponible'
                    else:
                        venta_dict['Fecha'] = 'Fecha no disponible'
                    
                    # Formatear Fecha_Creacion y extraer Hora
                    if venta_dict.get('Fecha_Creacion'):
                        if isinstance(venta_dict['Fecha_Creacion'], datetime):
                            venta_dict['Hora'] = venta_dict['Fecha_Creacion'].strftime('%H:%M')
                            venta_dict['Fecha_Creacion'] = venta_dict['Fecha_Creacion'].strftime('%d/%m/%Y %H:%M')
                        else:
                            try:
                                fecha_obj = datetime.strptime(str(venta_dict['Fecha_Creacion']), '%Y-%m-%d %H:%M:%S')
                                venta_dict['Hora'] = fecha_obj.strftime('%H:%M')
                                venta_dict['Fecha_Creacion'] = fecha_obj.strftime('%d/%m/%Y %H:%M')
                            except:
                                try:
                                    fecha_obj = datetime.strptime(str(venta_dict['Fecha_Creacion']), '%Y-%m-%d')
                                    venta_dict['Hora'] = '00:00'
                                    venta_dict['Fecha_Creacion'] = fecha_obj.strftime('%d/%m/%Y') + ' 00:00'
                                except:
                                    venta_dict['Hora'] = 'Hora no disponible'
                                    venta_dict['Fecha_Creacion'] = 'Fecha no disponible'
                    else:
                        venta_dict['Hora'] = 'Hora no disponible'
                        venta_dict['Fecha_Creacion'] = 'Fecha no disponible'
                    
                    ventas.append(venta_dict)
            
            # Obtener fecha actual formateada para comparaciones
            ahora = datetime.now()
            fecha_actual = ahora.strftime('%d/%m/%Y')
            fecha_actual_iso = ahora.strftime('%Y-%m-%d')  # Para inputs date
            
        return render_template('vendedor/ventas/ventas.html', 
                             asignaciones=asignaciones,
                             ventas=ventas,
                             fecha_actual=fecha_actual,
                             fecha_actual_iso=fecha_actual_iso,  # IMPORTANTE: pasar esta variable
                             now=ahora)
                             
    except Exception as e:
        print(f"Error en vendedor_ventas: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar ventas: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/vendedor/venta/crear', methods=['GET', 'POST'])
@vendedor_required
def vendedor_venta_crear():
    """Crear una nueva venta en ruta con integración a caja, abonos y movimientos"""
    try:
        id_vendedor = int(current_user.id)
        id_empresa = session.get('empresa_id', 1)
        
        # Para GET - solo consultas
        if request.method == 'GET':
            with get_db_cursor() as cursor:
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                    FROM asignacion_vendedores av
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Usuario = %s 
                    AND av.Estado = 'Activa'
                    AND r.ID_Empresa = %s
                    LIMIT 1
                """, (id_vendedor, id_empresa))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una ruta activa asignada', 'warning')
                    return redirect(url_for('vendedor.vendedor_dashboard'))
                
                # Obtener clientes de la empresa (filtrados por ruta)
                cursor.execute("""
                    SELECT ID_Cliente, Nombre, RUC_CEDULA, Telefono, Direccion,
                           tipo_cliente, perfil_cliente, COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total
                    FROM clientes 
                    WHERE Estado = 'ACTIVO' 
                    AND ID_Empresa = %s
                    AND (ID_Ruta = %s OR ID_Ruta IS NULL)
                    ORDER BY Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
                clientes = cursor.fetchall()
                
                # Obtener inventario disponible con precios de ruta
                cursor.execute("""
                    SELECT ir.ID_Producto, 
                           p.COD_Producto, 
                           p.Descripcion as Nombre,
                           p.Precio_Ruta,
                           ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE ir.ID_Asignacion = %s 
                    AND ir.Cantidad > 0
                    AND p.Estado = 'activo'
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'],))
                inventario = cursor.fetchall()
                
                # Obtener métodos de pago
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM metodos_pago
                    ORDER BY Nombre
                """)
                metodos_pago = cursor.fetchall()
                
                # ===== VERIFICACIÓN DE CAJA MEJORADA =====
                # Verificar si hay caja abierta hoy
                cursor.execute("""
                    SELECT COUNT(*) as tiene_caja_hoy
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND DATE(Fecha) = CURDATE() 
                    AND Tipo = 'APERTURA'
                    AND Estado = 'ACTIVO'
                """, (asignacion['ID_Asignacion'],))
                tiene_caja_hoy = cursor.fetchone()['tiene_caja_hoy'] > 0
                
                # Verificar si hay una caja abierta de días anteriores SIN CIERRE
                cursor.execute("""
                    SELECT COUNT(*) as tiene_caja_activa
                    FROM movimientos_caja_ruta m1
                    WHERE m1.ID_Asignacion = %s 
                    AND m1.Tipo = 'APERTURA'
                    AND m1.Estado = 'ACTIVO'
                    AND NOT EXISTS (
                        SELECT 1 FROM movimientos_caja_ruta m2
                        WHERE m2.ID_Asignacion = m1.ID_Asignacion
                        AND m2.Tipo = 'CIERRE'
                        AND m2.Fecha > m1.Fecha
                        AND m2.Estado = 'ACTIVO'
                    )
                """, (asignacion['ID_Asignacion'],))
                tiene_caja_activa = cursor.fetchone()['tiene_caja_activa'] > 0
                
                # También verificar el último movimiento del día para asegurar que no haya cierre
                cursor.execute("""
                    SELECT Tipo, Estado, DATE(Fecha) as Fecha_Movimiento
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND DATE(Fecha) = CURDATE()
                    AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC
                    LIMIT 1
                """, (asignacion['ID_Asignacion'],))
                ultimo_movimiento_hoy = cursor.fetchone()
                
                # La caja está abierta si:
                # 1. Hay una apertura hoy, O
                # 2. Hay una apertura activa sin cierre de días anteriores, Y
                # 3. El último movimiento de hoy NO es un CIERRE
                caja_abierta = tiene_caja_hoy or (tiene_caja_activa and (not ultimo_movimiento_hoy or ultimo_movimiento_hoy['Tipo'] != 'CIERRE'))
                
                # Fecha actual para el template
                fecha_actual = datetime.now().strftime('%d/%m/%Y')
                
                print(f"📊 Estado de caja - ID_Asignacion: {asignacion['ID_Asignacion']}")
                print(f"  - Tiene caja hoy: {tiene_caja_hoy}")
                print(f"  - Tiene caja activa sin cierre: {tiene_caja_activa}")
                print(f"  - Último movimiento hoy: {ultimo_movimiento_hoy}")
                print(f"  - Caja abierta: {caja_abierta}")
                
            return render_template('vendedor/ventas/venta_crear.html',
                                 asignacion=asignacion,
                                 clientes=clientes,
                                 inventario=inventario,
                                 metodos_pago=metodos_pago,
                                 fecha_actual=fecha_actual,
                                 caja_abierta=caja_abierta)
        
        # Para POST - operaciones de escritura con commit
        if request.method == 'POST':
            # Usar get_db_cursor con commit=True
            with get_db_cursor(commit=True) as cursor:
                # Obtener asignación activa del vendedor
                cursor.execute("""
                    SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                    FROM asignacion_vendedores av
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                    WHERE av.ID_Usuario = %s 
                    AND av.Estado = 'Activa'
                    AND r.ID_Empresa = %s
                    LIMIT 1
                """, (id_vendedor, id_empresa))
                asignacion = cursor.fetchone()
                
                if not asignacion:
                    flash('No tienes una ruta activa asignada', 'warning')
                    return redirect(url_for('vendedor.vendedor_dashboard'))
                
                # Procesar creación de venta
                id_cliente = request.form.get('cliente')
                tipo_venta = request.form.get('tipo_venta')  # '1'=Contado, '2'=Crédito
                observacion = request.form.get('observacion', '')
                productos_json = request.form.get('productos', '[]')
                
                # Obtener datos del abono si existe
                abono_monto = float(request.form.get('abono_monto', '0'))
                abono_metodo_pago = request.form.get('abono_metodo_pago', '')
                procesar_abono = request.form.get('procesar_abono', '0') == '1'
                
                # Validar datos básicos
                if not id_cliente:
                    flash('Debe seleccionar un cliente', 'error')
                    return redirect(request.url)
                
                if not tipo_venta:
                    flash('Debe seleccionar el tipo de venta', 'error')
                    return redirect(request.url)
                
                # Parsear productos
                try:
                    productos = json.loads(productos_json)
                    print(f"Productos recibidos: {productos}")
                except Exception as e:
                    print(f"Error al parsear JSON: {e}")
                    productos = []
                
                if not productos:
                    flash('Debe agregar al menos un producto a la venta', 'error')
                    return redirect(request.url)
                
                # ===== SOLO PARA VENTAS DE CONTADO: VERIFICAR CAJA =====
                if tipo_venta == '1':  # Solo ventas de contado requieren caja
                    # Estrategia 1: Buscar apertura de hoy
                    cursor.execute("""
                        SELECT ID_Movimiento, Fecha, Saldo_Acumulado
                        FROM movimientos_caja_ruta 
                        WHERE ID_Asignacion = %s 
                        AND DATE(Fecha) = CURDATE() 
                        AND Tipo = 'APERTURA'
                        AND Estado = 'ACTIVO'
                        ORDER BY Fecha DESC 
                        LIMIT 1
                    """, (asignacion['ID_Asignacion'],))
                    caja = cursor.fetchone()
                    
                    # Estrategia 2: Si no hay apertura hoy, buscar la última apertura activa sin cierre
                    if not caja:
                        cursor.execute("""
                            SELECT m1.ID_Movimiento, m1.Fecha, m1.Saldo_Acumulado
                            FROM movimientos_caja_ruta m1
                            WHERE m1.ID_Asignacion = %s 
                            AND m1.Tipo = 'APERTURA'
                            AND m1.Estado = 'ACTIVO'
                            AND NOT EXISTS (
                                SELECT 1 FROM movimientos_caja_ruta m2
                                WHERE m2.ID_Asignacion = m1.ID_Asignacion
                                AND m2.Tipo = 'CIERRE'
                                AND m2.Fecha > m1.Fecha
                                AND m2.Estado = 'ACTIVO'
                            )
                            ORDER BY m1.Fecha DESC
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'],))
                        caja = cursor.fetchone()
                    
                    # Estrategia 3: Verificar si hay algún movimiento hoy (para asegurar que no haya cierre)
                    if caja:
                        cursor.execute("""
                            SELECT Tipo
                            FROM movimientos_caja_ruta 
                            WHERE ID_Asignacion = %s 
                            AND DATE(Fecha) = CURDATE()
                            AND Estado = 'ACTIVO'
                            ORDER BY Fecha DESC
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'],))
                        ultimo_hoy = cursor.fetchone()
                        
                        # Si el último movimiento de hoy es un CIERRE, la caja está cerrada
                        if ultimo_hoy and ultimo_hoy['Tipo'] == 'CIERRE':
                            caja = None
                            print("⚠️ La caja fue cerrada hoy, no se pueden realizar ventas de contado")
                    
                    # Si no hay caja válida, intentar crear una apertura automática
                    if not caja:
                        print("⚠️ No se encontró caja abierta, intentando crear apertura automática...")
                        
                        # Verificar si ya existe una apertura hoy (por si acaso)
                        cursor.execute("""
                            SELECT ID_Movimiento
                            FROM movimientos_caja_ruta 
                            WHERE ID_Asignacion = %s 
                            AND DATE(Fecha) = CURDATE() 
                            AND Tipo = 'APERTURA'
                            LIMIT 1
                        """, (asignacion['ID_Asignacion'],))
                        apertura_existente = cursor.fetchone()
                        
                        if apertura_existente:
                            # Si existe pero estaba inactiva, reactivarla
                            cursor.execute("""
                                UPDATE movimientos_caja_ruta 
                                SET Estado = 'ACTIVO'
                                WHERE ID_Movimiento = %s
                            """, (apertura_existente['ID_Movimiento'],))
                            caja = apertura_existente
                            print(f"✅ Apertura existente reactivada: {caja['ID_Movimiento']}")
                        else:
                            # Crear nueva apertura
                            try:
                                fecha_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
                                
                                cursor.execute("""
                                    INSERT INTO movimientos_caja_ruta
                                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                                     Tipo_Pago, Saldo_Acumulado, Estado)
                                    VALUES (%s, %s, 'APERTURA', %s, 0.00, NULL, 0.00, 'ACTIVO')
                                """, (
                                    asignacion['ID_Asignacion'],
                                    id_vendedor,
                                    f"Apertura automática - {fecha_hora}"
                                ))
                                
                                cursor.execute("SELECT LAST_INSERT_ID() as ID_Movimiento")
                                caja = cursor.fetchone()
                                print(f"✅ Apertura automática creada con ID: {caja['ID_Movimiento']}")
                                
                            except Exception as e:
                                print(f"❌ Error al crear apertura: {e}")
                                flash('No se pudo abrir la caja', 'error')
                                return redirect(url_for('vendedor.vendedor_dashboard'))
                    
                    if not caja:
                        flash('No se pudo verificar/crear la apertura de caja', 'error')
                        return redirect(url_for('vendedor.vendedor_dashboard'))
                    
                    print(f"✅ Caja verificada - ID Movimiento: {caja['ID_Movimiento']}")
                
                # ===== OBTENER SALDO ANTERIOR DEL CLIENTE (ANTES DE LA VENTA) =====
                cursor.execute("""
                    SELECT COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Anterior
                    FROM clientes 
                    WHERE ID_Cliente = %s AND ID_Empresa = %s
                """, (int(id_cliente), asignacion['ID_Empresa']))
                
                saldo_anterior_cliente = cursor.fetchone()
                saldo_anterior = float(saldo_anterior_cliente['Saldo_Anterior'] if saldo_anterior_cliente else 0)
                print(f"💰 Saldo anterior del cliente {id_cliente}: {saldo_anterior}")
                
                # Validar stock
                error_stock = False
                productos_sin_stock = []
                for prod in productos:
                    cursor.execute("""
                        SELECT Cantidad FROM inventario_ruta
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (asignacion['ID_Asignacion'], prod['id']))
                    stock = cursor.fetchone()
                    
                    if not stock or stock['Cantidad'] < prod['cantidad']:
                        cursor.execute("""
                            SELECT Descripcion FROM productos WHERE ID_Producto = %s
                        """, (prod['id'],))
                        prod_nombre = cursor.fetchone()
                        productos_sin_stock.append(prod_nombre["Descripcion"] if prod_nombre else f"Producto ID {prod['id']}")
                        error_stock = True
                
                if error_stock:
                    flash(f'Stock insuficiente para: {", ".join(productos_sin_stock)}', 'error')
                    return redirect(request.url)
                
                # Calcular total de la venta y subtotales
                total_venta = 0
                total_items = 0
                for prod in productos:
                    total_venta += prod['cantidad'] * prod['precio']
                    total_items += prod['cantidad']
                
                # ===== 1. INSERTAR FACTURA (INCLUYENDO SALDO ANTERIOR) =====
                cursor.execute("""
                    INSERT INTO facturacion_ruta 
                    (Fecha, ID_Cliente, ID_Asignacion, Credito_Contado, 
                     Observacion, Saldo_Anterior_Cliente, ID_Empresa, ID_Usuario_Creacion, Estado)
                    VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, 'Activa')
                """, (int(id_cliente), asignacion['ID_Asignacion'], int(tipo_venta), 
                      observacion, saldo_anterior, asignacion['ID_Empresa'], id_vendedor))
                
                id_factura = cursor.lastrowid
                print(f"✅ Factura de ruta creada con ID: {id_factura} (Saldo anterior guardado: {saldo_anterior})")
                
                ID_TIPO_MOVIMIENTO_VENTA = 2  
                
                documento_numero = f"VEN-{id_factura}" 
                
                cursor.execute("""
                    INSERT INTO movimientos_ruta_cabecera
                    (ID_Asignacion, ID_TipoMovimiento, Fecha_Movimiento, ID_Usuario_Registra,
                     Documento_Numero, ID_Cliente, Total_Productos, Total_Items,
                     Total_Subtotal, ID_Empresa, Estado)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],      # ID_Asignacion
                    ID_TIPO_MOVIMIENTO_VENTA,         # ID_TipoMovimiento
                    id_vendedor,                      # ID_Usuario_Registra
                    documento_numero,                 # Documento_Numero
                    int(id_cliente),                  # ID_Cliente
                    total_venta,                      # Total_Productos (monto total)
                    total_items,                      # Total_Items (cantidad total de productos)
                    total_venta,                      # Total_Subtotal (subtotal)
                    asignacion['ID_Empresa'],         # ID_Empresa
                ))
                
                id_movimiento_cabecera = cursor.lastrowid
                print(f"✅ Movimiento registrado en cabecera con ID: {id_movimiento_cabecera}")
                
                # ===== 3. INSERTAR DETALLES EN movimientos_ruta_detalle Y ACTUALIZAR INVENTARIO =====
                for prod in productos:
                    total_linea = prod['cantidad'] * prod['precio']
                    
                    # Insertar en detalle de facturación
                    cursor.execute("""
                        INSERT INTO detalle_facturacion_ruta
                        (ID_FacturaRuta, ID_Producto, Cantidad, Precio, Total)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, prod['id'], prod['cantidad'], 
                          prod['precio'], total_linea))
                    
                    # Insertar en movimientos_ruta_detalle
                    cursor.execute("""
                        INSERT INTO movimientos_ruta_detalle
                        (ID_Movimiento, ID_Producto, Cantidad, Precio_Unitario, Subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        id_movimiento_cabecera,   # ID_Movimiento
                        prod['id'],               # ID_Producto
                        prod['cantidad'],         # Cantidad
                        prod['precio'],           # Precio_Unitario
                        total_linea               # Subtotal
                    ))
                    
                    print(f"  - Detalle producto {prod['id']}: {prod['cantidad']} x {prod['precio']} = {total_linea}")
                    
                    # Actualizar inventario de ruta
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad - %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (prod['cantidad'], asignacion['ID_Asignacion'], prod['id']))
                
                print(f"✅ {len(productos)} productos registrados en detalle de movimientos")
                
                # ===== 4. REGISTRO EN CAJA (SOLO PARA VENTAS DE CONTADO) =====
                if tipo_venta == '1':  # CONTADO
                    # Calcular saldo actual de caja ANTES de insertar
                    cursor.execute("""
                        SELECT COALESCE(SUM(CASE 
                            WHEN Tipo = 'GASTO' THEN -Monto 
                            WHEN Tipo = 'CIERRE' THEN 0
                            ELSE Monto 
                        END), 0) as Saldo_Actual
                        FROM movimientos_caja_ruta 
                        WHERE ID_Asignacion = %s 
                          AND Estado = 'ACTIVO'
                          AND Tipo != 'CIERRE'
                    """, (asignacion['ID_Asignacion'],))
                    
                    saldo_result = cursor.fetchone()
                    saldo_actual = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
                    nuevo_saldo = saldo_actual + total_venta
                    
                    cursor.execute("""
                        INSERT INTO movimientos_caja_ruta
                        (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                         Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                        VALUES (%s, %s, 'VENTA', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                    """, (
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        f"Venta Contado Factura #{id_factura}",
                        total_venta,
                        'CONTADO',
                        id_factura,
                        int(id_cliente),
                        nuevo_saldo
                    ))
                    
                    print(f"✅ Movimiento en caja registrado: +{total_venta}")
                    
                    # Actualizar el monto efectivo en la cabecera del movimiento
                    cursor.execute("""
                        UPDATE movimientos_ruta_cabecera
                        SET Monto_Efectivo = %s
                        WHERE ID_Movimiento = %s
                    """, (total_venta, id_movimiento_cabecera))
                    
                else:  # CREDITO - NO SE REGISTRA NADA EN CAJA
                    print(f"✅ Venta a crédito #{id_factura} registrada SIN movimiento de caja (como debe ser)")
                
                # ===== 5. CREAR CUENTA POR COBRAR (si es crédito) =====
                if tipo_venta == '2':  # Crédito
                    try:
                        fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO cuentas_por_cobrar
                            (Fecha, ID_Cliente, Num_Documento, Observacion, Fecha_Vencimiento,
                             Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente,
                             ID_Factura, ID_FacturaRuta, ID_Usuario_Creacion, Estado)
                            VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            int(id_cliente),                    # ID_Cliente
                            f"FAC-R{id_factura}",               # Num_Documento
                            observacion,                         # Observacion
                            fecha_vencimiento,                   # Fecha_Vencimiento
                            2,                                    # Tipo_Movimiento (2=Venta)
                            total_venta,                         # Monto_Movimiento
                            asignacion['ID_Empresa'],            # ID_Empresa
                            total_venta,                         # Saldo_Pendiente
                            None,                                # ID_Factura (NULL)
                            id_factura,                          # ID_FacturaRuta
                            id_vendedor,                         # ID_Usuario_Creacion
                            'Pendiente'                          # Estado
                        ))
                        
                        id_cuenta = cursor.lastrowid
                        print(f"✅ Cuenta por cobrar creada con ID: {id_cuenta}")
                        
                        # Actualizar saldo del cliente
                        cursor.execute("""
                            UPDATE clientes 
                            SET Saldo_Pendiente_Total = COALESCE(Saldo_Pendiente_Total, 0) + %s,
                                Fecha_Ultimo_Movimiento = NOW(),
                                ID_Ultima_Factura = %s
                            WHERE ID_Cliente = %s AND ID_Empresa = %s
                        """, (total_venta, id_factura, int(id_cliente), asignacion['ID_Empresa']))
                        
                        print(f"✅ Saldo del cliente actualizado: +{total_venta}")
                        
                    except Exception as e:
                        print(f"❌ Error al crear cuenta por cobrar: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        raise
                
                # ===== 6. PROCESAR ABONO (DESPUÉS DE LA FACTURA) =====
                if procesar_abono and abono_monto > 0:
                    try:
                        print(f"💰 Procesando abono de {abono_monto} para cliente {id_cliente}")
                        
                        # 6.1 Obtener facturas pendientes del cliente
                        cursor.execute("""
                            SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                                   Fecha_Vencimiento,
                                   CASE 
                                       WHEN Fecha_Vencimiento < CURDATE() THEN 1 
                                       ELSE 2 
                                   END as Prioridad
                            FROM cuentas_por_cobrar
                            WHERE ID_Cliente = %s 
                              AND Estado IN ('Pendiente', 'Vencida')
                              AND Saldo_Pendiente > 0
                            ORDER BY Prioridad ASC, Fecha_Vencimiento ASC
                        """, (int(id_cliente),))
                        
                        facturas_pendientes = cursor.fetchall()
                        
                        if not facturas_pendientes:
                            print("⚠️ No hay facturas pendientes para aplicar el abono")
                        else:
                            # 6.2 Calcular saldo actual de caja para el abono
                            cursor.execute("""
                                SELECT COALESCE(SUM(CASE 
                                    WHEN Tipo = 'GASTO' THEN -Monto 
                                    ELSE Monto 
                                END), 0) as Saldo_Actual
                                FROM movimientos_caja_ruta
                                WHERE ID_Asignacion = %s 
                                  AND Estado = 'ACTIVO'
                                  AND Tipo != 'CIERRE'
                            """, (asignacion['ID_Asignacion'],))
                            
                            saldo_result = cursor.fetchone()
                            saldo_actual_abono = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
                            nuevo_saldo_caja = saldo_actual_abono + abono_monto
                            
                            # 6.3 Registrar movimiento de abono en caja (SÍ porque es efectivo real)
                            cursor.execute("""
                                INSERT INTO movimientos_caja_ruta
                                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                                 Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                                VALUES (%s, %s, 'ABONO', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                            """, (
                                asignacion['ID_Asignacion'],
                                id_vendedor,
                                f"Abono a cuenta - Factura #{id_factura}",
                                abono_monto,
                                'CONTADO' if tipo_venta == '1' else 'CREDITO',
                                id_factura,
                                int(id_cliente),
                                nuevo_saldo_caja
                            ))
                            
                            id_movimiento_caja = cursor.lastrowid
                            
                            # 6.4 Distribuir el abono entre las facturas pendientes
                            monto_restante = abono_monto
                            monto_aplicado = 0
                            
                            for factura in facturas_pendientes:
                                if monto_restante <= 0:
                                    break
                                    
                                saldo_factura = float(factura['Saldo_Pendiente'])
                                monto_aplicar = min(monto_restante, saldo_factura)
                                nuevo_saldo_factura = saldo_factura - monto_aplicar
                                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0 else 'Pendiente'
                                
                                # Actualizar factura
                                cursor.execute("""
                                    UPDATE cuentas_por_cobrar
                                    SET Saldo_Pendiente = %s, 
                                        Estado = %s
                                    WHERE ID_Movimiento = %s
                                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                                
                                # Insertar en abonos_detalle
                                try:
                                    cursor.execute("""
                                        INSERT INTO abonos_detalle
                                        (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                                         ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                    """, (
                                        id_movimiento_caja,
                                        asignacion['ID_Asignacion'],
                                        id_vendedor,
                                        int(id_cliente),
                                        factura['ID_Movimiento'],
                                        monto_aplicar,
                                        saldo_factura,
                                        nuevo_saldo_factura
                                    ))
                                except Exception as e:
                                    print(f"⚠️ No se pudo insertar en abonos_detalle: {e}")
                                
                                monto_restante -= monto_aplicar
                                monto_aplicado += monto_aplicar
                            
                            # 6.5 Actualizar saldo del cliente
                            cursor.execute("""
                                UPDATE clientes 
                                SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                                    Fecha_Ultimo_Pago = NOW()
                                WHERE ID_Cliente = %s AND ID_Empresa = %s
                            """, (monto_aplicado, int(id_cliente), asignacion['ID_Empresa']))
                            
                            print(f"✅ Abono de {abono_monto} procesado exitosamente")
                            print(f"   - Monto aplicado: {monto_aplicado}")
                            print(f"   - Vuelto: {monto_restante}")
                            
                    except Exception as e:
                        print(f"❌ Error al procesar abono: {str(e)}")
                        traceback.print_exc()
                        raise
                
                print(f"✅ Venta {id_factura} procesada exitosamente")
                print(f"✅ Movimiento cabecera {id_movimiento_cabecera} registrado con {len(productos)} detalles")
                
            # Fuera del context manager, los cambios ya están commiteados
            flash('Venta registrada exitosamente', 'success')
            
            # Redirigir al ticket
            return redirect(url_for('vendedor.vendedor_generar_ticket_ruta', 
                                  id_venta=id_factura, 
                                  autoPrint=1))
                             
    except Exception as e:
        print(f"❌ Error en vendedor_venta_crear: {str(e)}")
        traceback.print_exc()
        flash(f'Error al procesar la venta: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_ventas'))

@vendedor_bp.route('/api/vendedor/procesar_abono', methods=['POST'])
@vendedor_required
def api_procesar_abono():
    """Procesa un abono con información completa de ruta, usuario y método de pago"""
    try:
        data = request.get_json()
        print(f"📥 Datos recibidos: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'Datos no válidos'}), 400
            
        id_cliente = data.get('id_cliente')
        monto_abono = data.get('monto_abono')
        id_metodo_pago = data.get('id_metodo_pago')
        id_vendedor = int(current_user.id)
        
        print(f"🔍 Validando: id_cliente={id_cliente}, monto={monto_abono}, metodo={id_metodo_pago}")
        
        if not id_cliente:
            return jsonify({'success': False, 'error': 'ID de cliente no proporcionado'}), 400
            
        if not monto_abono or float(monto_abono) <= 0:
            return jsonify({'success': False, 'error': 'Monto inválido'}), 400
            
        if not id_metodo_pago:
            return jsonify({'success': False, 'error': 'Debe seleccionar un método de pago'}), 400
        
        monto_abono = float(monto_abono)
        id_metodo_pago = int(id_metodo_pago)
        
        with get_db_cursor(commit=True) as cursor:
            # 1. Obtener el nombre del método de pago
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM metodos_pago 
                WHERE ID_MetodoPago = %s
            """, (id_metodo_pago,))
            metodo = cursor.fetchone()
            
            print(f"💳 Método de pago encontrado: {metodo}")
            
            if not metodo:
                return jsonify({'success': False, 'error': 'Método de pago no válido'}), 400
            
            nombre_metodo_pago = metodo['Nombre']
            
            # 2. Obtener asignación activa del vendedor
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa asignada'}), 400
            
            print(f"📍 Asignación encontrada: {asignacion}")
            
            # 3. Obtener facturas pendientes del cliente
            cursor.execute("""
                SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                       Fecha_Vencimiento,
                       CASE 
                           WHEN Fecha_Vencimiento < CURDATE() THEN 1 
                           ELSE 2 
                       END as Prioridad
                FROM cuentas_por_cobrar
                WHERE ID_Cliente = %s 
                  AND Estado IN ('Pendiente', 'Vencida')
                  AND Saldo_Pendiente > 0
                ORDER BY Prioridad ASC, Fecha_Vencimiento ASC
            """, (int(id_cliente),))
            
            facturas = cursor.fetchall()
            print(f"📄 Facturas encontradas: {len(facturas)}")
            
            if not facturas:
                return jsonify({'success': False, 'error': 'No hay facturas pendientes para este cliente'}), 400
            
            # 4. Calcular saldo actual de caja
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo = 'GASTO' THEN -Monto 
                    ELSE Monto 
                END), 0) as Saldo_Actual
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                  AND DATE(Fecha) = CURDATE() 
                  AND Tipo != 'CIERRE'
                  AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            
            saldo_result = cursor.fetchone()
            saldo_actual = float(saldo_result['Saldo_Actual'] if saldo_result else 0)
            nuevo_saldo = saldo_actual + monto_abono
            
            # 5. Registrar movimiento en caja CON EL ID_METODOPAGO
            concepto = f"Abono de cliente - Monto: C${monto_abono:,.2f} - Pago: {nombre_metodo_pago}"
            
            print(f"💵 Insertando movimiento: ID_MetodoPago={id_metodo_pago}, Monto={monto_abono}")
            
            try:
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                     Tipo_Pago, ID_Cliente, Saldo_Acumulado, Estado, ID_MetodoPago)
                    VALUES (%s, %s, 'ABONO', %s, %s, NULL, %s, %s, 'ACTIVO', %s)
                """, (
                    asignacion['ID_Asignacion'],
                    id_vendedor,
                    concepto,
                    monto_abono,
                    int(id_cliente),
                    nuevo_saldo,
                    id_metodo_pago  # ← GUARDAMOS EL ID DEL MÉTODO DE PAGO
                ))
                
                id_movimiento_caja = cursor.lastrowid
                print(f"✅ Movimiento de caja insertado: ID={id_movimiento_caja}, ID_MetodoPago={id_metodo_pago}")
                
            except Exception as e:
                print(f"❌ Error al insertar en movimientos_caja_ruta: {e}")
                raise Exception(f"Error al registrar movimiento de caja: {str(e)}")
            
            # 6. Distribuir el abono entre las facturas
            monto_restante = monto_abono
            detalle_abono = []
            monto_aplicado = 0
            ultimo_id_abono = None
            
            for factura in facturas:
                if monto_restante <= 0:
                    break
                    
                saldo_factura = float(factura['Saldo_Pendiente'])
                monto_aplicar = min(monto_restante, saldo_factura)
                nuevo_saldo_factura = saldo_factura - monto_aplicar
                nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0.01 else 'Pendiente'
                
                # Actualizar factura
                cursor.execute("""
                    UPDATE cuentas_por_cobrar
                    SET Saldo_Pendiente = %s, 
                        Estado = %s
                    WHERE ID_Movimiento = %s
                """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                
                # Insertar en abonos_detalle con el método de pago
                try:
                    cursor.execute("""
                        SELECT COUNT(*) as count 
                        FROM information_schema.tables 
                        WHERE table_schema = DATABASE()
                        AND table_name = 'abonos_detalle'
                    """)
                    table_exists = cursor.fetchone()['count'] > 0
                    
                    if table_exists:
                        cursor.execute("""
                            INSERT INTO abonos_detalle
                            (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                             ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo,
                             ID_MetodoPago, Metodo_Pago_Nombre)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento_caja,
                            asignacion['ID_Asignacion'],
                            id_vendedor,
                            int(id_cliente),
                            factura['ID_Movimiento'],
                            monto_aplicar,
                            saldo_factura,
                            nuevo_saldo_factura,
                            id_metodo_pago,
                            nombre_metodo_pago
                        ))
                        
                        ultimo_id_abono = cursor.lastrowid
                        print(f"✅ Detalle de abono insertado para factura {factura['Num_Documento']}")
                    else:
                        print(f"⚠️ Tabla abonos_detalle no existe, omitiendo inserción")
                        ultimo_id_abono = id_movimiento_caja
                    
                except Exception as e:
                    print(f"⚠️ No se pudo insertar en abonos_detalle: {e}")
                    ultimo_id_abono = id_movimiento_caja
                
                detalle_abono.append({
                    'factura': factura['Num_Documento'],
                    'monto': monto_aplicar,
                    'saldo_anterior': saldo_factura,
                    'saldo_nuevo': nuevo_saldo_factura,
                    'estado': nuevo_estado
                })
                
                monto_restante -= monto_aplicar
                monto_aplicado += monto_aplicar
            
            # 7. Actualizar saldo del cliente
            cursor.execute("""
                UPDATE clientes 
                SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                    Fecha_Ultimo_Pago = NOW()
                WHERE ID_Cliente = %s
            """, (monto_aplicado, int(id_cliente)))
            
            print(f"✅ Abono procesado: Monto={monto_aplicado}, Cliente={id_cliente}")
            
            # ID para el recibo
            id_abono_para_recibo = ultimo_id_abono if ultimo_id_abono else id_movimiento_caja
            
            return jsonify({
                'success': True,
                'mensaje': 'Abono procesado correctamente',
                'id_movimiento': id_movimiento_caja,
                'id_abono': id_abono_para_recibo,
                'id_metodo_pago': id_metodo_pago,
                'metodo_pago': nombre_metodo_pago,
                'ruta': asignacion['ID_Ruta'],
                'vendedor': current_user.username,
                'monto_abono': monto_abono,
                'monto_aplicado': monto_aplicado,
                'vuelto': monto_restante,
                'detalle': detalle_abono,
                'nuevo_saldo_caja': nuevo_saldo
            })
            
    except Exception as e:
        print(f"❌ Error en api_procesar_abono: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500

@vendedor_bp.route('/vendedor/venta/<int:id_venta>/ticket')
@vendedor_required
def vendedor_generar_ticket_ruta(id_venta):
    """Generar ticket de venta de ruta con información de saldos"""
    try:
        id_vendedor = int(current_user.id)
        auto_print = request.args.get('autoPrint', 0)
        
        with get_db_cursor() as cursor:
            # Obtener datos de la venta de ruta (INCLUYENDO SALDO_ANTERIOR_CLIENTE)
            cursor.execute("""
                SELECT 
                    fr.ID_FacturaRuta as ID_Factura,
                    fr.Fecha,
                    fr.Fecha_Creacion,
                    fr.Observacion,
                    fr.Credito_Contado,
                    fr.Saldo_Anterior_Cliente,  -- ← NUEVO CAMPO
                    fr.ID_Usuario_Creacion,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    c.Telefono as Telefono_Cliente,
                    c.Direccion as Direccion_Cliente,
                    COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Cliente_Actual,
                    u.NombreUsuario as Usuario,
                    e.ID_Empresa,
                    COALESCE(e.Nombre_Empresa, 'MI EMPRESA') as Nombre_Empresa,
                    COALESCE(e.RUC, 'RUC NO CONFIGURADO') as RUC_Empresa,
                    COALESCE(e.Direccion, '') as Direccion_Empresa,
                    COALESCE(e.Telefono, '') as Telefono_Empresa,
                    r.Nombre_Ruta,
                    CASE 
                        WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                        ELSE 'CREDITO'
                    END as Tipo_Venta_Formateado
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN empresa e ON fr.ID_Empresa = e.ID_Empresa
                WHERE fr.ID_FacturaRuta = %s
                AND av.ID_Usuario = %s
            """, (id_venta, id_vendedor))
            
            factura = cursor.fetchone()
            
            if not factura:
                flash('Venta no encontrada o no tienes permiso para verla', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Formatear fechas
            fecha_formateada = factura['Fecha'].strftime('%d/%m/%Y') if factura['Fecha'] else ''
            hora_creacion = factura['Fecha_Creacion'].strftime('%H:%M:%S') if factura['Fecha_Creacion'] else ''
            
            # Obtener detalles de la venta
            cursor.execute("""
                SELECT 
                    df.ID_DetalleRuta as ID_Detalle,
                    df.Cantidad,
                    df.Precio,
                    df.Total as Subtotal,
                    p.ID_Producto,
                    COALESCE(p.COD_Producto, 'N/A') as COD_Producto,
                    COALESCE(p.Descripcion, 'PRODUCTO ELIMINADO') as Producto,
                    cat.Descripcion as Categoria,
                    um.Descripcion as Unidad
                FROM detalle_facturacion_ruta df
                LEFT JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE df.ID_FacturaRuta = %s
                ORDER BY df.ID_DetalleRuta
            """, (id_venta,))
            
            detalles = cursor.fetchall()
            
            if not detalles:
                flash('La venta no tiene detalles de productos', 'error')
                return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))
            
            # Calcular total de la venta actual
            total_venta = 0
            for detalle in detalles:
                subtotal = float(detalle['Subtotal'] or 0)
                total_venta += subtotal
            
            # Calcular subtotales por producto
            for detalle in detalles:
                detalle['Subtotal_Calculado'] = float(detalle['Cantidad']) * float(detalle['Precio'])
                detalle['Cantidad_Formateada'] = f"{float(detalle['Cantidad']):g}"
                detalle['Precio_Formateado'] = f"C$ {float(detalle['Precio']):,.2f}"
                detalle['Subtotal_Formateado'] = f"C$ {float(detalle['Subtotal']):,.2f}"
            
            # Variables para información de crédito
            cuenta_cobrar = None
            facturas_pendientes = []
            saldo_anterior_total = 0
            abonos_detalle = []
            proximo_vencimiento = None
            abono_realizado = 0
            abonos_esta_factura = 0
            mostrar_seccion_credito = False
            mensaje_credito = ""
            
            # ===== USAR EL SALDO ANTERIOR GUARDADO EN LA FACTURA =====
            saldo_anterior_total = float(factura['Saldo_Anterior_Cliente'] or 0)
            print(f"📊 Usando saldo anterior guardado en factura: {saldo_anterior_total}")
            
            # Obtener TODAS las cuentas por cobrar pendientes del cliente (para mostrar en el ticket)
            cursor.execute("""
                SELECT 
                    cxc.ID_Movimiento,
                    cxc.Num_Documento,
                    cxc.Saldo_Pendiente,
                    cxc.Monto_Movimiento as Monto_Original,
                    cxc.Fecha_Vencimiento,
                    cxc.Estado,
                    DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido,
                    DATE_FORMAT(cxc.Fecha_Vencimiento, '%d/%m/%Y') as Fecha_Vencimiento_Formateada,
                    CASE 
                        WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 'VENCIDA'
                        ELSE 'PENDIENTE'
                    END as Estado_Calculado
                FROM cuentas_por_cobrar cxc
                WHERE cxc.ID_Cliente = %s 
                AND cxc.Estado IN ('Pendiente', 'Vencida')
                AND cxc.Saldo_Pendiente > 0
                ORDER BY 
                    CASE WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 0 ELSE 1 END,
                    cxc.Fecha_Vencimiento ASC
            """, (factura['ID_Cliente'],))
            
            facturas_pendientes = cursor.fetchall()
            
            # Obtener el abono que se realizó EN ESTA VENTA
            cursor.execute("""
                SELECT 
                    m.ID_Movimiento,
                    m.Fecha,
                    m.Monto,
                    m.Concepto,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y %H:%i') as Fecha_Hora,
                    m.Tipo_Pago,
                    m.Estado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.ID_FacturaRuta = %s
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
                LIMIT 1
            """, (factura['ID_Cliente'], id_venta))
            
            abono_actual = cursor.fetchone()
            
            # Obtener abonos totales realizados para esta factura
            cursor.execute("""
                SELECT COALESCE(SUM(m.Monto), 0) as Total_Abonado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.ID_FacturaRuta = %s
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
            """, (factura['ID_Cliente'], id_venta))
            
            abonos_result = cursor.fetchone()
            abonos_esta_factura = float(abonos_result['Total_Abonado'] if abonos_result else 0)
            
            # Determinar el abono que dio el cliente en esta venta
            if abono_actual:
                abono_cliente = float(abono_actual['Monto'])
                concepto_abono = abono_actual['Concepto'] or 'ABONO A CUENTA'
                fecha_abono = abono_actual['Fecha_Hora']
            else:
                if factura['Credito_Contado'] == 1:
                    abono_cliente = total_venta
                    concepto_abono = 'PAGO CONTADO'
                    fecha_abono = datetime.now().strftime('%d/%m/%Y %H:%M')
                else:
                    abono_cliente = abonos_esta_factura
                    concepto_abono = 'ABONO A CUENTA' if abono_cliente > 0 else 'SIN ABONO'
                    fecha_abono = None
            
            # El nuevo saldo pendiente es el que está en la tabla clientes (ya actualizado)
            nuevo_saldo_pendiente = float(factura['Saldo_Cliente_Actual'] or 0)
            
            # Determinar si mostrar sección de crédito
            if saldo_anterior_total > 0 or abono_cliente > 0 or factura['Credito_Contado'] == 2:
                mostrar_seccion_credito = True
                if factura['Credito_Contado'] == 2:
                    if saldo_anterior_total > 0:
                        mensaje_credito = "NUEVA DEUDA + SALDO ANTERIOR"
                    else:
                        mensaje_credito = "NUEVA VENTA A CREDITO"
                else:
                    if saldo_anterior_total > 0:
                        mensaje_credito = "ABONO A DEUDAS PENDIENTES"
                    else:
                        mensaje_credito = "VENTA AL CONTADO"
            
            # Obtener el próximo vencimiento
            if facturas_pendientes:
                facturas_futuras = [f for f in facturas_pendientes 
                                  if f['Fecha_Vencimiento'] and f['Fecha_Vencimiento'] >= datetime.now().date()]
                if facturas_futuras:
                    proxima_factura = min(facturas_futuras, key=lambda x: x['Fecha_Vencimiento'])
                    if proxima_factura['Fecha_Vencimiento']:
                        proximo_vencimiento = proxima_factura['Fecha_Vencimiento'].strftime('%d/%m/%Y')
            
            # Obtener historial de abonos recientes del cliente
            cursor.execute("""
                SELECT 
                    m.Fecha,
                    m.Concepto,
                    m.Monto,
                    m.ID_Movimiento,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y') as Fecha_Formateada,
                    TIME_FORMAT(m.Fecha, '%H:%i') as Hora_Formateada
                FROM movimientos_caja_ruta m
                WHERE m.ID_Cliente = %s 
                AND m.Tipo = 'ABONO'
                AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
                LIMIT 5
            """, (factura['ID_Cliente'],))
            
            abonos_detalle = cursor.fetchall()
            
            # Formatear montos de abonos
            for abono in abonos_detalle:
                abono['Monto_Formateado'] = f"C$ {float(abono['Monto'] or 0):,.2f}"
            
            # Preparar datos para el ticket
            ticket_data = {
                'id_factura': f"R-{id_venta:06d}",
                'id_factura_numerico': id_venta,
                'fecha': factura['Fecha'],
                'hora_emision': datetime.now(),
                'fecha_factura': fecha_formateada,
                'hora_factura': hora_creacion,
                'ruta': factura['Nombre_Ruta'],
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'cliente_detalles': {
                    'nombre': factura['Cliente'] or 'Consumidor Final',
                    'ruc': factura['RUC_Cliente'] or 'Consumidor Final',
                    'telefono': factura['Telefono_Cliente'] or '',
                    'direccion': factura['Direccion_Cliente'] or ''
                },
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'tipo_venta_valor': factura['Credito_Contado'],
                'observacion': factura['Observacion'] or '',
                'usuario': factura['Usuario'] or 'Vendedor',
                'usuario_id': factura['ID_Usuario_Creacion'],
                'detalles': detalles,
                'total': total_venta,
                'total_formateado': f"C$ {total_venta:,.2f}",
                'subtotal_sin_descuento': total_venta,
                'descuento': 0,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa'],
                },
                'tiene_credito': cuenta_cobrar is not None,
                'cuenta_cobrar': cuenta_cobrar
            }
            
            # Formatear valores para mostrar
            venta_realizada = total_venta
            venta_realizada_formateada = f"C$ {total_venta:,.2f}"
            
            saldo_anterior_formateado = f"C$ {saldo_anterior_total:,.2f}"
            abono_cliente_formateado = f"C$ {abono_cliente:,.2f}"
            nuevo_saldo_pendiente_formateado = f"C$ {nuevo_saldo_pendiente:,.2f}"
            
            # Calcular saldo total (venta + saldo anterior)
            saldo_total = venta_realizada + saldo_anterior_total
            
            return render_template('vendedor/ventas/ticket_venta_ruta.html',
                                 ticket=ticket_data,
                                 mostrar_seccion_credito=mostrar_seccion_credito,
                                 mensaje_credito=mensaje_credito,
                                 facturas_pendientes=facturas_pendientes if facturas_pendientes else [],
                                 abonos_detalle=abonos_detalle if abonos_detalle else [],
                                 proximo_vencimiento=proximo_vencimiento,
                                 # Variables para el formato solicitado
                                 venta_realizada=venta_realizada,
                                 venta_realizada_formateada=venta_realizada_formateada,
                                 saldo_anterior=saldo_anterior_total,
                                 saldo_anterior_formateado=saldo_anterior_formateado,
                                 saldo_total=saldo_total,
                                 abono_cliente=abono_cliente,
                                 abono_cliente_formateado=abono_cliente_formateado,
                                 concepto_abono=concepto_abono,
                                 fecha_abono=fecha_abono,
                                 nuevo_saldo_pendiente=nuevo_saldo_pendiente,
                                 nuevo_saldo_pendiente_formateado=nuevo_saldo_pendiente_formateado,
                                 auto_print=auto_print,
                                 now=datetime.now())
                             
    except Exception as e:
        print(f"Error en vendedor_generar_ticket_ruta: {str(e)}")
        traceback.print_exc()
        flash(f'Error al generar ticket: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))

@vendedor_bp.route('/vendedor/venta/<int:id_venta>/detalle')
@vendedor_required
def vendedor_venta_detalle(id_venta):
    """Ver detalle completo de una venta específica
    """
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Verificar que la venta pertenezca al vendedor actual
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM facturacion_ruta fr
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                WHERE fr.ID_FacturaRuta = %s
                AND av.ID_Usuario = %s
            """, (id_venta, id_vendedor))
            verificar = cursor.fetchone()
            
            if verificar['total'] == 0:
                flash('Venta no encontrada o no tienes permiso para verla', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Obtener información general de la venta
            cursor.execute("""
                SELECT fr.ID_FacturaRuta,
                       fr.Fecha,
                       fr.Credito_Contado,
                       fr.Observacion,
                       fr.Estado,
                       fr.Fecha_Creacion,
                       c.ID_Cliente,
                       c.Nombre as Cliente,
                       c.RUC_CEDULA,
                       c.Telefono,
                       c.Direccion,
                       u.NombreUsuario as Vendedor,
                       u.NombreUsuario,
                       r.Nombre_Ruta,
                       av.Fecha_Asignacion,
                       CASE 
                           WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                           ELSE 'CRÉDITO'
                       END as Tipo_Venta,
                       COALESCE((
                           SELECT SUM(Saldo_Pendiente) 
                           FROM cuentas_por_cobrar 
                           WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                       ), 0) as Saldo_Pendiente
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE fr.ID_FacturaRuta = %s
            """, (id_venta,))
            
            venta_data = cursor.fetchone()
            if not venta_data:
                flash('Venta no encontrada', 'error')
                return redirect(url_for('vendedor.vendedor_ventas'))
            
            # Convertir a diccionario
            venta = dict(venta_data)
            
            
            # Función helper para formatear fechas (opcional, para no repetir código)
            def formatear_fecha(valor, formato_salida='%d/%m/%Y', incluir_hora=False):
                if not valor:
                    return 'Fecha no disponible'
                
                if isinstance(valor, datetime):
                    return valor.strftime(formato_salida + (' %H:%M' if incluir_hora else ''))
                
                try:
                    if incluir_hora:
                        fecha_obj = datetime.strptime(str(valor), '%Y-%m-%d %H:%M:%S')
                    else:
                        fecha_obj = datetime.strptime(str(valor), '%Y-%m-%d')
                    return fecha_obj.strftime(formato_salida + (' %H:%M' if incluir_hora else ''))
                except:
                    return 'Fecha no disponible'
            
            # Formatear fechas
            venta['Fecha'] = formatear_fecha(venta.get('Fecha'))
            venta['Fecha_Creacion'] = formatear_fecha(venta.get('Fecha_Creacion'), incluir_hora=True)
            venta['Fecha_Asignacion'] = formatear_fecha(venta.get('Fecha_Asignacion'))
            
            # Obtener detalle de productos
            cursor.execute("""
                SELECT df.ID_DetalleRuta,
                       df.Cantidad,
                       df.Precio,
                       df.Total,
                       p.ID_Producto,
                       p.COD_Producto,
                       p.Descripcion as Producto,
                       um.Descripcion as Unidad_Medida
                FROM detalle_facturacion_ruta df
                INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE df.ID_FacturaRuta = %s
                ORDER BY df.ID_DetalleRuta
            """, (id_venta,))
            detalles = cursor.fetchall()
            
            # Calcular totales
            subtotal = 0
            for d in detalles:
                subtotal += float(d['Total'])
            
            # Obtener información de cuentas por cobrar si es crédito
            cuentas_cobrar = None
            pagos = []
            if venta['Credito_Contado'] == 2:
                cursor.execute("""
                    SELECT ID_Movimiento, 
                           Monto_Movimiento,
                           Saldo_Pendiente, 
                           Estado as Estado_CXC,
                           Fecha_Vencimiento,
                           DATEDIFF(CURDATE(), Fecha_Vencimiento) as Dias_Vencidos
                    FROM cuentas_por_cobrar
                    WHERE Num_Documento = %s
                """, (f"FAC-R{id_venta}",))
                
                cuenta_data = cursor.fetchone()
                if cuenta_data:
                    cuentas_cobrar = dict(cuenta_data)
                    cuentas_cobrar['Fecha_Vencimiento'] = formatear_fecha(cuentas_cobrar.get('Fecha_Vencimiento'))
                    
                    # Obtener pagos realizados si existen
                    cursor.execute("""
                        SELECT p.ID_Pago,
                               p.Fecha as Fecha_Pago,
                               p.Monto as Monto_Pagado,
                               mp.Nombre as Metodo_Pago,
                               p.Comentarios as Observacion
                        FROM pagos_cuentascobrar p
                        INNER JOIN metodos_pago mp ON p.ID_MetodoPago = mp.ID_MetodoPago
                        WHERE p.ID_Movimiento = %s
                        ORDER BY p.Fecha DESC
                    """, (cuentas_cobrar['ID_Movimiento'],))
                    
                    pagos_data = cursor.fetchall()
                    for pago in pagos_data:
                        pago_dict = dict(pago)
                        pago_dict['Fecha_Pago'] = formatear_fecha(pago_dict.get('Fecha_Pago'), incluir_hora=True)
                        pagos.append(pago_dict)
            
            # Obtener métodos de pago para el modal
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
            metodos_pago = cursor.fetchall()
            
        return render_template('vendedor/ventas/venta_detalle.html',
                             venta=venta,
                             detalles=detalles,
                             subtotal=subtotal,
                             cuentas_cobrar=cuentas_cobrar,
                             pagos=pagos,
                             metodos_pago=metodos_pago)
                             
    except Exception as e:
        print(f"Error en vendedor_venta_detalle: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar detalle: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_ventas'))

@vendedor_bp.route('/vendedor/venta/<int:id_venta>/anular', methods=['POST'])
@vendedor_required
def vendedor_venta_anular(id_venta):
    """Anular una venta (solo si es del día y está activa)
    """
    try:
        id_vendedor = current_user.id  # CORREGIDO: usar current_user.id
        motivo = request.form.get('motivo', 'Sin motivo especificado')
        
        with get_db_cursor(commit=True) as cursor:  # CORREGIDO: agregar commit=True
            # Verificar que la venta pertenezca al vendedor y sea del día
            cursor.execute("""
                SELECT fr.ID_FacturaRuta, fr.ID_Asignacion, fr.Credito_Contado,
                       dfr.ID_Producto, dfr.Cantidad
                FROM facturacion_ruta fr
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_FacturaRuta = %s 
                AND fr.ID_Usuario_Creacion = %s
                AND fr.Estado = 'Activa'
                AND DATE(fr.Fecha_Creacion) = CURDATE()
            """, (id_venta, id_vendedor))
            venta_data = cursor.fetchall()
            
            if not venta_data:
                flash('No se puede anular la venta. Solo puedes anular ventas del día', 'error')
                return redirect(url_for('vendedor.vendedor_venta_detalle', id_venta=id_venta))
            
            # Devolver productos al inventario
            for item in venta_data:
                if item['ID_Producto']:
                    cursor.execute("""
                        UPDATE inventario_ruta 
                        SET Cantidad = Cantidad + %s
                        WHERE ID_Asignacion = %s AND ID_Producto = %s
                    """, (item['Cantidad'], item['ID_Asignacion'], item['ID_Producto']))
            
            # Si es crédito, anular cuenta por cobrar
            if venta_data[0]['Credito_Contado'] == 2:
                cursor.execute("""
                    UPDATE cuentas_por_cobrar 
                    SET Estado = 'Anulada'
                    WHERE Num_Documento = %s
                """, (f"FAC-R{id_venta}",))
            
            # Anular factura
            cursor.execute("""
                UPDATE facturacion_ruta 
                SET Estado = 'Anulada',
                    Observacion = CONCAT(COALESCE(Observacion, ''), ' | ANULADA: ', %s)
                WHERE ID_FacturaRuta = %s
            """, (motivo, id_venta))
            
            flash('Venta anulada exitosamente', 'success')
            
    except Exception as e:
        print(f"Error en vendedor_venta_anular: {str(e)}")
        flash(f'Error al anular venta: {str(e)}', 'error')
    
    return redirect(url_for('vendedor.vendedor_ventas'))

@vendedor_bp.route('/api/filtrar_ventas', methods=['POST'])
@vendedor_required
def api_filtrar_ventas():
    """API para filtrar ventas por fecha y ruta
    """
    try:
        id_vendedor = current_user.id
        fecha = request.form.get('fecha', 'hoy')
        id_ruta = request.form.get('ruta', '')  # Cambiado: valor por defecto vacío
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        
        with get_db_cursor(True) as cursor:
            # Primero obtener las asignaciones del vendedor
            cursor.execute("""
                SELECT ID_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s
            """, (id_vendedor,))
            asignaciones = cursor.fetchall()
            
            if not asignaciones:
                return jsonify({'success': True, 'ventas': []})
            
            ids_asignacion = [a['ID_Asignacion'] for a in asignaciones]
            placeholders = ','.join(['%s'] * len(ids_asignacion))
            
            # Construir condición de fecha
            fecha_cond = ""
            params = list(ids_asignacion)  # Iniciar con los IDs de asignación
            
            from datetime import datetime, timedelta
            
            if fecha == 'hoy':
                fecha_cond = "AND DATE(fr.Fecha) = CURDATE()"
            elif fecha == 'ayer':
                fecha_cond = "AND DATE(fr.Fecha) = CURDATE() - INTERVAL 1 DAY"
            elif fecha == 'semana':
                fecha_cond = "AND fr.Fecha >= CURDATE() - INTERVAL 7 DAY"
            elif fecha == 'mes':
                fecha_cond = "AND fr.Fecha >= CURDATE() - INTERVAL 30 DAY"
            elif fecha == 'personalizado' and fecha_inicio and fecha_fin:
                try:
                    # Intentar parsear en DD/MM/YYYY primero
                    try:
                        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%d/%m/%Y')
                        fecha_fin_obj = datetime.strptime(fecha_fin, '%d/%m/%Y')
                    except:
                        # Si falla, intentar en YYYY-MM-DD
                        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d')
                    
                    fecha_inicio_mysql = fecha_inicio_obj.strftime('%Y-%m-%d')
                    fecha_fin_mysql = fecha_fin_obj.strftime('%Y-%m-%d')
                    fecha_cond = "AND DATE(fr.Fecha) BETWEEN %s AND %s"
                    params.append(fecha_inicio_mysql)
                    params.append(fecha_fin_mysql)
                except Exception as e:
                    print(f"Error al parsear fechas: {e}")
                    fecha_cond = "AND DATE(fr.Fecha) = CURDATE()"
            
            # Construir condición de ruta
            ruta_cond = ""
            if id_ruta and id_ruta != '' and id_ruta != 'todas':
                # Validar que la ruta pertenezca al vendedor
                try:
                    if int(id_ruta) in ids_asignacion:
                        ruta_cond = "AND fr.ID_Asignacion = %s"
                        params.append(id_ruta)
                except:
                    pass
            
            # Consulta SQL
            query = f"""
                SELECT fr.ID_FacturaRuta, 
                       DATE_FORMAT(fr.Fecha, '%%d/%%m/%%Y') as Fecha,
                       fr.Fecha_Creacion,
                       fr.Credito_Contado,
                       fr.Observacion, 
                       fr.Estado, 
                       c.Nombre as Cliente, 
                       c.RUC_CEDULA,
                       c.Telefono,
                       r.Nombre_Ruta,
                       COALESCE(SUM(dfr.Total), 0) as Total_Venta,
                       CASE 
                           WHEN fr.Credito_Contado = 1 THEN 'CONTADO'
                           ELSE 'CRÉDITO'
                       END as Tipo_Venta,
                       CASE 
                           WHEN fr.Credito_Contado = 2 THEN (
                               SELECT COALESCE(SUM(Saldo_Pendiente), 0)
                               FROM cuentas_por_cobrar 
                               WHERE Num_Documento = CONCAT('FAC-R', fr.ID_FacturaRuta)
                           )
                           ELSE 0
                       END as Saldo_Pendiente
                FROM facturacion_ruta fr
                INNER JOIN clientes c ON fr.ID_Cliente = c.ID_Cliente
                INNER JOIN asignacion_vendedores av ON fr.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                LEFT JOIN detalle_facturacion_ruta dfr ON fr.ID_FacturaRuta = dfr.ID_FacturaRuta
                WHERE fr.ID_Asignacion IN ({placeholders})
                {fecha_cond}
                {ruta_cond}
                GROUP BY fr.ID_FacturaRuta
                ORDER BY fr.Fecha DESC, fr.ID_FacturaRuta DESC
            """
            
            cursor.execute(query, tuple(params))
            ventas_raw = cursor.fetchall()
            
            # Formatear para JSON
            ventas_list = []
            from datetime import datetime as dt
            
            for v in ventas_raw:
                # Calcular hora desde Fecha_Creacion
                hora = "00:00"
                if v.get('Fecha_Creacion'):
                    try:
                        if isinstance(v['Fecha_Creacion'], dt):
                            hora = v['Fecha_Creacion'].strftime('%H:%M')
                        else:
                            fecha_obj = dt.strptime(str(v['Fecha_Creacion']), '%Y-%m-%d %H:%M:%S')
                            hora = fecha_obj.strftime('%H:%M')
                    except:
                        hora = "00:00"
                
                ventas_list.append({
                    'ID_FacturaRuta': v['ID_FacturaRuta'],
                    'Fecha': v['Fecha'],
                    'Hora': hora,
                    'Cliente': v['Cliente'],
                    'RUC_CEDULA': v['RUC_CEDULA'] or 'N/A',
                    'Telefono': v['Telefono'] or '',
                    'Nombre_Ruta': v['Nombre_Ruta'],
                    'Total_Venta': float(v['Total_Venta']),
                    'Tipo_Venta': v['Tipo_Venta'],
                    'Estado': v['Estado'],
                    'Saldo_Pendiente': float(v['Saldo_Pendiente']) if v['Saldo_Pendiente'] else 0
                })
            
            return jsonify({'success': True, 'ventas': ventas_list})
            
    except Exception as e:
        print(f"Error en api_filtrar_ventas: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@vendedor_bp.route('/api/vendedor/verificar_saldo_cliente/<int:id_cliente>', methods=['GET'])
@vendedor_required
def api_verificar_saldo_cliente(id_cliente):
    """API para verificar el saldo pendiente de un cliente"""
    try:
        with get_db_cursor() as cursor:
            # Obtener la empresa del vendedor desde su asignación activa
            cursor.execute("""
                SELECT r.ID_Empresa
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({
                    'success': False,
                    'error': 'No tienes una asignación activa hoy'
                }), 400
            
            # Obtener saldo pendiente del cliente
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA, Saldo_Pendiente_Total,
                       (SELECT COUNT(*) FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')) as Facturas_Pendientes
                FROM clientes c
                WHERE c.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND c.Estado = 'ACTIVO'
            """, (id_cliente, empresa['ID_Empresa']))
            
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({
                    'success': False,
                    'error': 'Cliente no encontrado'
                }), 404
            
            # Si tiene saldo pendiente, obtener detalles de las facturas de ruta
            facturas_pendientes = []
            if cliente['Saldo_Pendiente_Total'] > 0:
                cursor.execute("""
                    SELECT c.ID_Movimiento, c.Fecha, c.Num_Documento, 
                           c.Monto_Movimiento, c.Saldo_Pendiente,
                           c.Fecha_Vencimiento,
                           DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as Dias_Vencido,
                           fr.ID_FacturaRuta,
                           fr.Fecha as FechaFactura
                    FROM cuentas_por_cobrar c
                    LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                    WHERE c.ID_Cliente = %s 
                    AND c.Estado IN ('Pendiente', 'Vencida')
                    AND c.ID_FacturaRuta IS NOT NULL  -- Solo facturas de ruta
                    ORDER BY c.Fecha_Vencimiento ASC, c.Fecha ASC
                """, (id_cliente,))
                facturas_pendientes = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'cliente': {
                    'id': cliente['ID_Cliente'],
                    'nombre': cliente['Nombre'],
                    'ruc': cliente['RUC_CEDULA'],
                    'saldo_pendiente': float(cliente['Saldo_Pendiente_Total'] or 0),
                    'facturas_pendientes': cliente['Facturas_Pendientes']
                },
                'facturas_detalle': facturas_pendientes
            })
            
    except Exception as e:
        print(f"Error en verificar saldo: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ENDPOINTS PARA SINCRONIZACIÓN OFFLINE
# ============================================
@vendedor_bp.route('/api/vendedor/verificar_saldo_cliente_offline/<int:id_cliente>', methods=['GET'])
@vendedor_required
def api_verificar_saldo_cliente_offline(id_cliente):
    """
    Versión simplificada para verificar un cliente específico offline.
    Esta función es llamada cuando hay conexión para obtener datos actualizados.
    """
    try:
        with get_db_cursor() as cursor:
            # Obtener la empresa del vendedor desde su asignación activa
            cursor.execute("""
                SELECT r.ID_Empresa
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s
                AND av.Estado = 'Activa'
                AND av.Fecha_Asignacion = CURDATE()
                LIMIT 1
            """, (current_user.id,))
            
            empresa = cursor.fetchone()
            
            if not empresa:
                return jsonify({
                    'success': False,
                    'error': 'No tienes una asignación activa hoy'
                }), 400
            
            # Obtener información completa del cliente
            cursor.execute("""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre,
                    c.RUC_CEDULA,
                    c.Telefono,
                    c.Direccion,
                    c.perfil_cliente,
                    COALESCE((
                        SELECT SUM(Saldo_Pendiente) 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')
                    ), 0) as Saldo_Pendiente_Total,
                    (
                        SELECT COUNT(*) 
                        FROM cuentas_por_cobrar 
                        WHERE ID_Cliente = c.ID_Cliente 
                        AND Estado IN ('Pendiente', 'Vencida')
                    ) as Facturas_Pendientes
                FROM clientes c
                WHERE c.ID_Cliente = %s 
                AND c.ID_Empresa = %s
                AND c.Estado = 'ACTIVO'
            """, (id_cliente, empresa['ID_Empresa']))
            
            cliente = cursor.fetchone()
            
            if not cliente:
                return jsonify({
                    'success': False,
                    'error': 'Cliente no encontrado'
                }), 404
            
            # Obtener facturas pendientes si tiene saldo
            facturas_pendientes = []
            if cliente['Saldo_Pendiente_Total'] > 0:
                cursor.execute("""
                    SELECT 
                        c.ID_Movimiento,
                        c.Fecha,
                        c.Num_Documento,
                        c.Monto_Movimiento,
                        c.Saldo_Pendiente,
                        c.Fecha_Vencimiento,
                        DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as Dias_Vencido,
                        fr.ID_FacturaRuta,
                        fr.Fecha as FechaFactura
                    FROM cuentas_por_cobrar c
                    LEFT JOIN facturacion_ruta fr ON c.ID_FacturaRuta = fr.ID_FacturaRuta
                    WHERE c.ID_Cliente = %s 
                    AND c.Estado IN ('Pendiente', 'Vencida')
                    AND c.ID_FacturaRuta IS NOT NULL
                    ORDER BY c.Fecha_Vencimiento ASC, c.Fecha ASC
                    LIMIT 50
                """, (id_cliente,))
                facturas_pendientes = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'cliente': {
                    'id': cliente['ID_Cliente'],
                    'nombre': cliente['Nombre'],
                    'ruc': cliente['RUC_CEDULA'],
                    'telefono': cliente['Telefono'],
                    'direccion': cliente['Direccion'],
                    'perfil': cliente['perfil_cliente'],
                    'saldo_pendiente': float(cliente['Saldo_Pendiente_Total'] or 0),
                    'facturas_pendientes': cliente['Facturas_Pendientes']
                },
                'facturas_detalle': facturas_pendientes
            })
            
    except Exception as e:
        print(f"Error en verificar saldo: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@vendedor_bp.route('/api/vendedor/sincronizar_inventario', methods=['GET'])
@vendedor_required
def api_sincronizar_inventario():
    """Sincronizar inventario de la ruta (solo cambios recientes)"""
    try:
        id_vendedor = int(current_user.id)
        ultima_sincronizacion = request.args.get('ultima_sincronizacion')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta, ID_Empresa
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s AND Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            # Construir consulta según si hay última sincronización
            if ultima_sincronizacion:
                # Solo productos con cambios desde la última sincronización
                cursor.execute("""
                    SELECT ir.ID_Producto, p.COD_Producto, p.Descripcion as Nombre,
                           p.Precio_Ruta, ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida, um.Abreviatura,
                           p.ID_Categoria, c.Descripcion as Categoria,
                           p.Estado as Producto_Estado,
                           ir.Fecha_Actualizacion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE ir.ID_Asignacion = %s 
                      AND ir.Fecha_Actualizacion > %s
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'], ultima_sincronizacion))
            else:
                # Primera sincronización: todos los productos
                cursor.execute("""
                    SELECT ir.ID_Producto, p.COD_Producto, p.Descripcion as Nombre,
                           p.Precio_Ruta, ir.Cantidad as Stock_Disponible,
                           um.Descripcion as Unidad_Medida, um.Abreviatura,
                           p.ID_Categoria, c.Descripcion as Categoria,
                           p.Estado as Producto_Estado,
                           ir.Fecha_Actualizacion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    WHERE ir.ID_Asignacion = %s 
                      AND p.Estado = 'activo'
                    ORDER BY p.Descripcion
                """, (asignacion['ID_Asignacion'],))
            
            inventario = cursor.fetchall()
            
            # Obtener la fecha de la última modificación para próxima sincronización
            cursor.execute("""
                SELECT MAX(Fecha_Actualizacion) as ultima_modificacion
                FROM inventario_ruta
                WHERE ID_Asignacion = %s
            """, (asignacion['ID_Asignacion'],))
            
            ultima_modificacion = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'inventario': inventario,
                'ultima_modificacion': ultima_modificacion['ultima_modificacion'] if ultima_modificacion else None,
                'asignacion_id': asignacion['ID_Asignacion'],
                'ruta_id': asignacion['ID_Ruta']
            })
            
    except Exception as e:
        print(f"Error en api_sincronizar_inventario: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/api/vendedor/sincronizar_clientes_saldos', methods=['GET'])
@vendedor_required
def api_sincronizar_clientes_saldos():
    """Sincronizar clientes y sus saldos pendientes"""
    try:
        id_vendedor = int(current_user.id)
        ultima_sincronizacion = request.args.get('ultima_sincronizacion')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Empresa
                FROM asignacion_vendedores av
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            # Obtener clientes de la ruta
            if ultima_sincronizacion:
                cursor.execute("""
                    SELECT c.ID_Cliente, c.Nombre, c.RUC_CEDULA, c.Telefono, 
                           c.Direccion, c.tipo_cliente, c.perfil_cliente,
                           COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total,
                           c.Fecha_Ultimo_Movimiento, c.Fecha_Ultimo_Pago,
                           c.Estado as Cliente_Estado,
                           c.Fecha_Creacion
                    FROM clientes c
                    WHERE c.ID_Empresa = %s 
                      AND c.Estado = 'ACTIVO'
                      AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
                      AND (c.Fecha_Ultimo_Movimiento > %s OR c.Fecha_Creacion > %s)
                    ORDER BY c.Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta'], 
                      ultima_sincronizacion, ultima_sincronizacion))
            else:
                cursor.execute("""
                    SELECT c.ID_Cliente, c.Nombre, c.RUC_CEDULA, c.Telefono, 
                           c.Direccion, c.tipo_cliente, c.perfil_cliente,
                           COALESCE(c.Saldo_Pendiente_Total, 0) as Saldo_Pendiente_Total,
                           c.Fecha_Ultimo_Movimiento, c.Fecha_Ultimo_Pago,
                           c.Estado as Cliente_Estado,
                           c.Fecha_Creacion
                    FROM clientes c
                    WHERE c.ID_Empresa = %s 
                      AND c.Estado = 'ACTIVO'
                      AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
                    ORDER BY c.Nombre
                """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
            
            clientes = cursor.fetchall()
            
            # Para cada cliente con saldo, obtener facturas pendientes
            for cliente in clientes:
                if cliente['Saldo_Pendiente_Total'] > 0:
                    cursor.execute("""
                        SELECT cxc.ID_Movimiento, cxc.Num_Documento, 
                               cxc.Monto_Movimiento, cxc.Saldo_Pendiente,
                               cxc.Fecha_Vencimiento,
                               DATEDIFF(CURDATE(), cxc.Fecha_Vencimiento) as Dias_Vencido,
                               DATE_FORMAT(cxc.Fecha_Vencimiento, '%%Y-%%m-%%d') as Fecha_Vencimiento_ISO
                        FROM cuentas_por_cobrar cxc
                        WHERE cxc.ID_Cliente = %s 
                          AND cxc.Estado IN ('Pendiente', 'Vencida')
                          AND cxc.Saldo_Pendiente > 0
                        ORDER BY 
                            CASE WHEN cxc.Fecha_Vencimiento < CURDATE() THEN 0 ELSE 1 END,
                            cxc.Fecha_Vencimiento ASC
                    """, (cliente['ID_Cliente'],))
                    cliente['facturas_pendientes'] = cursor.fetchall()
                else:
                    cliente['facturas_pendientes'] = []
            
            # Obtener fecha de última modificación de clientes en la ruta
            cursor.execute("""
                SELECT MAX(GREATEST(
                    COALESCE(c.Fecha_Ultimo_Movimiento, '1900-01-01'),
                    COALESCE(c.Fecha_Creacion, '1900-01-01')
                )) as ultima_modificacion
                FROM clientes c
                WHERE c.ID_Empresa = %s 
                  AND (c.ID_Ruta = %s OR c.ID_Ruta IS NULL)
            """, (asignacion['ID_Empresa'], asignacion['ID_Ruta']))
            
            ultima_modificacion = cursor.fetchone()
            
            return jsonify({
                'success': True,
                'clientes': clientes,
                'ultima_modificacion': ultima_modificacion['ultima_modificacion'] if ultima_modificacion else None,
                'asignacion_id': asignacion['ID_Asignacion']
            })
            
    except Exception as e:
        print(f"Error en api_sincronizar_clientes_saldos: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/api/vendedor/verificar_stock_venta', methods=['POST'])
@vendedor_required
def api_verificar_stock_venta():
    """Verificar stock antes de sincronizar una venta offline"""
    try:
        data = request.get_json()
        productos = data.get('productos', [])
        id_asignacion = data.get('asignacion_id')
        
        with get_db_cursor() as cursor:
            errores = []
            for producto in productos:
                cursor.execute("""
                    SELECT ir.Cantidad, p.Descripcion
                    FROM inventario_ruta ir
                    INNER JOIN productos p ON ir.ID_Producto = p.ID_Producto
                    WHERE ir.ID_Asignacion = %s AND ir.ID_Producto = %s
                """, (id_asignacion, producto['id']))
                
                stock = cursor.fetchone()
                if not stock or float(stock['Cantidad']) < float(producto['cantidad']):
                    errores.append({
                        'producto_id': producto['id'],
                        'nombre': producto.get('nombre', stock['Descripcion'] if stock else 'Producto'),
                        'stock_disponible': float(stock['Cantidad']) if stock else 0,
                        'solicitado': float(producto['cantidad'])
                    })
            
            if errores:
                return jsonify({
                    'success': False,
                    'error': 'Stock insuficiente',
                    'detalles': errores
                }), 400
            
            return jsonify({'success': True})
            
    except Exception as e:
        print(f"Error en api_verificar_stock_venta: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/api/vendedor/registrar_venta_offline', methods=['POST'])
@vendedor_required
def api_registrar_venta_offline():
    """Endpoint específico para registrar ventas offline sincronizadas"""
    try:
        id_vendedor = int(current_user.id)
        data = request.get_json()
        
        with get_db_cursor(commit=True) as cursor:
            # Verificar asignación activa
            cursor.execute("""
                SELECT av.*, r.Nombre_Ruta, u.NombreUsuario as Nombre_Vendedor
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                INNER JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
                WHERE av.ID_Usuario = %s 
                AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
            
            # Verificar/crear caja
            cursor.execute("""
                SELECT ID_Movimiento, Saldo_Acumulado
                FROM movimientos_caja_ruta 
                WHERE ID_Asignacion = %s 
                AND DATE(Fecha) = CURDATE() 
                AND Tipo = 'APERTURA'
                AND Estado = 'ACTIVO'
            """, (asignacion['ID_Asignacion'],))
            caja = cursor.fetchone()
            
            if not caja:
                # Crear apertura automática
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                     Tipo_Pago, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'APERTURA', %s, 0.00, NULL, 0.00, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],
                    id_vendedor,
                    f"Apertura automática - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                ))
                
                cursor.execute("SELECT LAST_INSERT_ID() as ID_Movimiento")
                caja = cursor.fetchone()
            
            # Obtener saldo anterior del cliente
            cursor.execute("""
                SELECT COALESCE(Saldo_Pendiente_Total, 0) as Saldo_Anterior
                FROM clientes 
                WHERE ID_Cliente = %s
            """, (int(data['cliente_id']),))
            saldo_anterior = cursor.fetchone()['Saldo_Anterior']
            
            # Insertar factura
            cursor.execute("""
                INSERT INTO facturacion_ruta 
                (Fecha, ID_Cliente, ID_Asignacion, Credito_Contado, 
                 Observacion, Saldo_Anterior_Cliente, ID_Empresa, ID_Usuario_Creacion, Estado)
                VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, 'Activa')
            """, (
                int(data['cliente_id']), 
                asignacion['ID_Asignacion'], 
                int(data['tipo_venta']),
                data.get('observacion', ''),
                saldo_anterior,
                asignacion['ID_Empresa'],
                id_vendedor
            ))
            
            id_factura = cursor.lastrowid
            
            # Insertar detalles y actualizar inventario
            total_venta = 0
            for producto in data['productos']:
                total_linea = float(producto['cantidad']) * float(producto['precio'])
                total_venta += total_linea
                
                cursor.execute("""
                    INSERT INTO detalle_facturacion_ruta
                    (ID_FacturaRuta, ID_Producto, Cantidad, Precio, Total)
                    VALUES (%s, %s, %s, %s, %s)
                """, (id_factura, producto['id'], producto['cantidad'], 
                      producto['precio'], total_linea))
                
                # Actualizar inventario
                cursor.execute("""
                    UPDATE inventario_ruta 
                    SET Cantidad = Cantidad - %s
                    WHERE ID_Asignacion = %s AND ID_Producto = %s
                """, (producto['cantidad'], asignacion['ID_Asignacion'], producto['id']))
            
            # Registrar en caja según tipo de venta
            if data['tipo_venta'] == '1':  # Contado
                cursor.execute("""
                    SELECT COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        ELSE Monto 
                    END), 0) as Saldo_Actual
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                      AND Estado = 'ACTIVO'
                      AND Tipo != 'CIERRE'
                """, (asignacion['ID_Asignacion'],))
                saldo_actual = float(cursor.fetchone()['Saldo_Actual'] or 0)
                nuevo_saldo = saldo_actual + total_venta
                
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                     Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'VENTA', %s, %s, 'CONTADO', %s, %s, %s, 'ACTIVO')
                """, (
                    asignacion['ID_Asignacion'],
                    id_vendedor,
                    f"Venta Contado Factura #{id_factura}",
                    total_venta,
                    id_factura,
                    int(data['cliente_id']),
                    nuevo_saldo
                ))
            else:  # Crédito
                # Crear cuenta por cobrar
                fecha_vencimiento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute("""
                    INSERT INTO cuentas_por_cobrar
                    (Fecha, ID_Cliente, Num_Documento, Observacion, Fecha_Vencimiento,
                     Tipo_Movimiento, Monto_Movimiento, ID_Empresa, Saldo_Pendiente,
                     ID_FacturaRuta, ID_Usuario_Creacion, Estado)
                    VALUES (CURDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente')
                """, (
                    int(data['cliente_id']),
                    f"FAC-R{id_factura}",
                    data.get('observacion', ''),
                    fecha_vencimiento,
                    2,  # Tipo_Movimiento (2=Venta)
                    total_venta,
                    asignacion['ID_Empresa'],
                    total_venta,
                    id_factura,
                    id_vendedor
                ))
                
                # Actualizar saldo del cliente
                cursor.execute("""
                    UPDATE clientes 
                    SET Saldo_Pendiente_Total = COALESCE(Saldo_Pendiente_Total, 0) + %s,
                        Fecha_Ultimo_Movimiento = NOW(),
                        ID_Ultima_Factura = %s
                    WHERE ID_Cliente = %s
                """, (total_venta, id_factura, int(data['cliente_id'])))
            
            # Procesar abono si existe
            if data.get('procesar_abono') == '1' and float(data.get('abono_monto', 0)) > 0:
                monto_abono = float(data['abono_monto'])
                
                # Obtener facturas pendientes del cliente
                cursor.execute("""
                    SELECT ID_Movimiento, Num_Documento, Saldo_Pendiente,
                           Fecha_Vencimiento,
                           CASE 
                               WHEN Fecha_Vencimiento < CURDATE() THEN 1 
                               ELSE 2 
                           END as Prioridad
                    FROM cuentas_por_cobrar
                    WHERE ID_Cliente = %s 
                      AND Estado IN ('Pendiente', 'Vencida')
                      AND Saldo_Pendiente > 0
                    ORDER BY Prioridad ASC, Fecha_Vencimiento ASC
                """, (int(data['cliente_id']),))
                
                facturas_pendientes = cursor.fetchall()
                
                if facturas_pendientes:
                    # Registrar movimiento de abono en caja
                    cursor.execute("""
                        SELECT COALESCE(SUM(CASE 
                            WHEN Tipo = 'GASTO' THEN -Monto 
                            ELSE Monto 
                        END), 0) as Saldo_Actual
                        FROM movimientos_caja_ruta
                        WHERE ID_Asignacion = %s 
                          AND Estado = 'ACTIVO'
                          AND Tipo != 'CIERRE'
                    """, (asignacion['ID_Asignacion'],))
                    saldo_actual = float(cursor.fetchone()['Saldo_Actual'] or 0)
                    nuevo_saldo_caja = saldo_actual + monto_abono
                    
                    cursor.execute("""
                        INSERT INTO movimientos_caja_ruta
                        (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, 
                         Tipo_Pago, ID_FacturaRuta, ID_Cliente, Saldo_Acumulado, Estado)
                        VALUES (%s, %s, 'ABONO', %s, %s, %s, %s, %s, %s, 'ACTIVO')
                    """, (
                        asignacion['ID_Asignacion'],
                        id_vendedor,
                        f"Abono a cuenta - Factura #{id_factura}",
                        monto_abono,
                        'CONTADO' if data['tipo_venta'] == '1' else 'CREDITO',
                        id_factura,
                        int(data['cliente_id']),
                        nuevo_saldo_caja
                    ))
                    
                    id_movimiento_caja = cursor.lastrowid
                    
                    # Distribuir el abono
                    monto_restante = monto_abono
                    for factura in facturas_pendientes:
                        if monto_restante <= 0:
                            break
                            
                        saldo_factura = float(factura['Saldo_Pendiente'])
                        monto_aplicar = min(monto_restante, saldo_factura)
                        nuevo_saldo_factura = saldo_factura - monto_aplicar
                        nuevo_estado = 'Pagada' if nuevo_saldo_factura <= 0 else 'Pendiente'
                        
                        cursor.execute("""
                            UPDATE cuentas_por_cobrar
                            SET Saldo_Pendiente = %s, 
                                Estado = %s
                            WHERE ID_Movimiento = %s
                        """, (nuevo_saldo_factura, nuevo_estado, factura['ID_Movimiento']))
                        
                        cursor.execute("""
                            INSERT INTO abonos_detalle
                            (ID_Movimiento_Caja, ID_Asignacion, ID_Usuario, ID_Cliente, 
                             ID_CuentaCobrar, Monto_Aplicado, Saldo_Anterior, Saldo_Nuevo)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento_caja,
                            asignacion['ID_Asignacion'],
                            id_vendedor,
                            int(data['cliente_id']),
                            factura['ID_Movimiento'],
                            monto_aplicar,
                            saldo_factura,
                            nuevo_saldo_factura
                        ))
                        
                        monto_restante -= monto_aplicar
                    
                    # Actualizar saldo del cliente
                    cursor.execute("""
                        UPDATE clientes 
                        SET Saldo_Pendiente_Total = GREATEST(0, COALESCE(Saldo_Pendiente_Total, 0) - %s),
                            Fecha_Ultimo_Pago = NOW()
                        WHERE ID_Cliente = %s
                    """, (monto_abono, int(data['cliente_id'])))
            
            return jsonify({
                'success': True,
                'id_venta': id_factura,
                'ticket_url': url_for('vendedor.vendedor_generar_ticket_ruta', id_venta=id_factura, autoPrint=1, _external=True)
            })
            
    except Exception as e:
        print(f"Error en api_registrar_venta_offline: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/api/vendedor/asignacion_actual', methods=['GET'])
@vendedor_required
def api_asignacion_actual():
    """Obtener la asignación actual del vendedor"""
    try:
        id_vendedor = int(current_user.id)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, av.ID_Empresa,
                       r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
                LIMIT 1
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'}), 400
                
            return jsonify({
                'success': True,
                'asignacion_id': asignacion['ID_Asignacion'],
                'ruta_id': asignacion['ID_Ruta'],
                'ruta_nombre': asignacion['Nombre_Ruta'],
                'empresa_id': asignacion['ID_Empresa']
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =================================
#  CAJA DE MOVIMIENTOS DE EFECTIVOS
# =================================
@vendedor_bp.route('/vendedor/caja/mis_movimientos', methods=['GET'])
@vendedor_required
def mis_movimientos_caja():
    """Muestra los movimientos del vendedor actual en su ruta"""
    try:
        id_vendedor = current_user.id
        fecha = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        
        # Obtener nombre del vendedor (con manejo seguro)
        nombre_vendedor = getattr(current_user, 'NombreUsuario', 
                                  getattr(current_user, 'username', 
                                         getattr(current_user, 'name', f"Vendedor {id_vendedor}")))
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s 
                  AND av.Estado = 'Activa'
                  AND av.Fecha_Asignacion <= %s
                  AND (av.Fecha_Finalizacion >= %s OR av.Fecha_Finalizacion IS NULL)
                ORDER BY av.Fecha_Asignacion DESC
                LIMIT 1
            """, (id_vendedor, fecha, fecha))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada para esta fecha', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            # Verificar si ya hay apertura y cierre hoy - CORREGIDO
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN 1 ELSE 0 END), 0) as tiene_apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'CIERRE' THEN 1 ELSE 0 END), 0) as tiene_cierre
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
            estado_dia = cursor.fetchone()
            
            # Resumen del día - CORREGIDO con COALESCE
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN Tipo = 'APERTURA' THEN Monto ELSE 0 END), 0) as Apertura,
                    COALESCE(SUM(CASE WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CONTADO' THEN Monto ELSE 0 END), 0) as Ventas_Contado,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CREDITO' THEN 1 END), 0) as Ventas_Credito_Count,
                    COALESCE(SUM(CASE WHEN Tipo = 'ABONO' THEN Monto ELSE 0 END), 0) as Total_Abonos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Cantidad_Abonos,
                    COALESCE(SUM(CASE WHEN Tipo = 'GASTO' THEN Monto ELSE 0 END), 0) as Gastos,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') AND Tipo != 'CIERRE' THEN Monto 
                        ELSE 0 
                    END), 0) as Saldo_Actual,
                    COALESCE(SUM(CASE 
                        WHEN Tipo = 'VENTA' AND Tipo_Pago = 'CONTADO' THEN Monto 
                        WHEN Tipo = 'ABONO' THEN Monto 
                        WHEN Tipo = 'GASTO' THEN -Monto 
                        ELSE 0 
                    END), 0) as Total_Movimientos
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
            resumen = cursor.fetchone()
            
            # Movimientos detallados
            cursor.execute("""
                SELECT 
                    m.ID_Movimiento,
                    m.ID_Asignacion,
                    m.ID_Usuario,
                    DATE_FORMAT(m.Fecha, '%d/%m/%Y %H:%i') as Fecha_Formateada,
                    m.Fecha as Fecha_Original,
                    m.Tipo,
                    m.Concepto,
                    m.Monto,
                    m.Tipo_Pago,
                    m.ID_FacturaRuta,
                    m.ID_Cliente,
                    m.Saldo_Acumulado,
                    m.Estado as Estado_Movimiento,
                    c.Nombre as Nombre_Cliente,
                    c.RUC_CEDULA,
                    c.Telefono as Telefono_Cliente
                FROM movimientos_caja_ruta m
                LEFT JOIN clientes c ON m.ID_Cliente = c.ID_Cliente
                WHERE m.ID_Usuario = %s 
                  AND DATE(m.Fecha) = %s
                  AND m.Estado = 'ACTIVO'
                ORDER BY m.Fecha DESC
            """, (id_vendedor, fecha))
            
            movimientos = cursor.fetchall()
            
            # Estadísticas - CORREGIDO con COALESCE
            cursor.execute("""
                SELECT 
                    COALESCE(COUNT(DISTINCT ID_Cliente), 0) as clientes_Atendidos,
                    COALESCE(COUNT(CASE WHEN Tipo = 'VENTA' THEN 1 END), 0) as Total_Ventas,
                    COALESCE(COUNT(CASE WHEN Tipo = 'ABONO' THEN 1 END), 0) as Total_Abonos_Dia,
                    COALESCE(COUNT(CASE WHEN Tipo = 'GASTO' THEN 1 END), 0) as Total_Gastos_Dia
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha))
            
            estadisticas = cursor.fetchone()
            
            # Calcular valores seguros para el template - CORREGIDO
            tiene_apertura = int(estado_dia['tiene_apertura'] or 0) > 0
            tiene_cierre = int(estado_dia['tiene_cierre'] or 0) > 0
            
            # Asegurar que todos los valores del resumen sean números
            resumen_seguro = {
                'apertura': float(resumen['Apertura'] or 0),
                'ventas_contado': float(resumen['Ventas_Contado'] or 0),
                'ventas_credito_count': int(resumen['Ventas_Credito_Count'] or 0),
                'total_abonos': float(resumen['Total_Abonos'] or 0),
                'cantidad_abonos': int(resumen['Cantidad_Abonos'] or 0),
                'gastos': float(resumen['Gastos'] or 0),
                'saldo_actual': float(resumen['Saldo_Actual'] or 0),
                'total_movimientos': float(resumen['Total_Movimientos'] or 0)
            }
            
            # Calcular saldo esperado para el cierre (saldo_actual + gastos)
            saldo_esperado_cierre = resumen_seguro['saldo_actual'] + resumen_seguro['gastos']
            
            # Estadísticas seguras
            estadisticas_seguras = {
                'clientes_atendidos': int(estadisticas['clientes_Atendidos'] or 0),
                'total_ventas': int(estadisticas['Total_Ventas'] or 0),
                'total_abonos_dia': int(estadisticas['Total_Abonos_Dia'] or 0),
                'total_gastos_dia': int(estadisticas['Total_Gastos_Dia'] or 0)
            }
            
            return render_template('vendedor/caja/mis_movimientos.html',
                                 vendedor=nombre_vendedor,
                                 ruta=asignacion['Nombre_Ruta'],
                                 id_asignacion=asignacion['ID_Asignacion'],
                                 fecha=fecha,
                                 tiene_apertura=tiene_apertura,
                                 tiene_cierre=tiene_cierre,
                                 resumen=resumen_seguro,
                                 saldo_esperado_cierre=saldo_esperado_cierre,
                                 estadisticas=estadisticas_seguras,
                                 movimientos=movimientos)
            
    except Exception as e:
        print(f"Error en mis_movimientos_caja: {str(e)}")
        traceback.print_exc()
        flash(f'Error al cargar los movimientos: {str(e)}', 'danger')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/vendedor/caja/apertura_modal', methods=['POST'])
@vendedor_required
def apertura_caja_modal():
    """Procesa la apertura de caja desde el modal"""
    try:
        data = request.get_json()
        id_vendedor = current_user.id
        monto = float(data.get('monto', 0))
        observacion = data.get('observacion', '')
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s 
                  AND Estado = 'Activa'
                  AND Fecha_Asignacion <= %s
                  AND (Fecha_Finalizacion >= %s OR Fecha_Finalizacion IS NULL)
                LIMIT 1
            """, (id_vendedor, fecha_actual, fecha_actual))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'})
            
            # Insertar apertura
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Estado)
                VALUES (%s, %s, 'APERTURA', %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                f"Apertura de caja: {observacion}" if observacion else "Apertura de caja",
                monto
            ))
            
            return jsonify({'success': True, 'message': 'Apertura realizada con éxito'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/vendedor/caja/cierre_modal', methods=['POST'])
@vendedor_required
def cierre_caja_modal():
    """Procesa el cierre de caja desde el modal"""
    try:
        data = request.get_json()
        id_vendedor = current_user.id
        monto_real = float(data.get('monto_real', 0))
        observacion = data.get('observacion', '')
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        with get_db_cursor() as cursor:
            # Obtener asignación activa
            cursor.execute("""
                SELECT ID_Asignacion
                FROM asignacion_vendedores
                WHERE ID_Usuario = %s 
                  AND Estado = 'Activa'
                  AND Fecha_Asignacion <= %s
                  AND (Fecha_Finalizacion >= %s OR Fecha_Finalizacion IS NULL)
                LIMIT 1
            """, (id_vendedor, fecha_actual, fecha_actual))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                return jsonify({'success': False, 'error': 'Sin ruta activa'})
            
            # Calcular saldo esperado
            cursor.execute("""
                SELECT COALESCE(SUM(CASE 
                    WHEN Tipo = 'GASTO' THEN -Monto 
                    WHEN Tipo IN ('APERTURA', 'VENTA', 'ABONO') THEN Monto 
                    ELSE 0 
                END), 0) as Saldo_Esperado
                FROM movimientos_caja_ruta
                WHERE ID_Usuario = %s 
                  AND DATE(Fecha) = %s
                  AND Estado = 'ACTIVO'
            """, (id_vendedor, fecha_actual))
            
            saldo = cursor.fetchone()
            saldo_esperado = float(saldo['Saldo_Esperado'])
            diferencia = monto_real - saldo_esperado
            
            # Insertar cierre
            cursor.execute("""
                INSERT INTO movimientos_caja_ruta 
                (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Estado)
                VALUES (%s, %s, 'CIERRE', %s, %s, 'ACTIVO')
            """, (
                asignacion['ID_Asignacion'],
                id_vendedor,
                f"Cierre de caja - Diferencia: Gs. {diferencia:,.0f}. {observacion}" if observacion else f"Cierre de caja - Diferencia: Gs. {diferencia:,.0f}",
                monto_real
            ))
            
            return jsonify({
                'success': True, 
                'message': 'Cierre realizado con éxito',
                'diferencia': diferencia,
                'saldo_esperado': saldo_esperado
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/vendedor/abonos/mis_abonos', methods=['GET'])
@vendedor_required
def mis_abonos_detalle():
    """Muestra los abonos registrados por el vendedor con detalle de facturas"""
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    ad.Fecha,
                    ad.ID_Movimiento_Caja,
                    ad.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA,
                    ad.ID_CuentaCobrar,
                    cc.Num_Documento as Factura,
                    ad.Monto_Aplicado,
                    ad.Saldo_Anterior,
                    ad.Saldo_Nuevo,
                    CASE 
                        WHEN ad.Saldo_Nuevo = 0 THEN 'Pagada'
                        WHEN ad.Monto_Aplicado < ad.Saldo_Anterior THEN 'Pago Parcial'
                        ELSE 'Pendiente'
                    END as Estado_Factura,
                    r.Nombre_Ruta
                FROM abonos_detalle ad
                INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                INNER JOIN cuentas_por_cobrar cc ON ad.ID_CuentaCobrar = cc.ID_Movimiento
                INNER JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE ad.ID_Usuario = %s
                ORDER BY ad.Fecha DESC
                LIMIT 50
            """, (id_vendedor,))
            
            abonos = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'vendedor': current_user.NombreUsuario,
                'total_abonos': len(abonos),
                'abonos': abonos
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@vendedor_bp.route('/vendedor/resumen/diario', methods=['GET'])
@vendedor_required
def resumen_diario_vendedor():
    """Resumen diario de actividades del vendedor"""
    try:
        id_vendedor = current_user.id
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    DATE(m.Fecha) as Dia,
                    r.Nombre_Ruta,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'VENTA' THEN m.ID_FacturaRuta END) as Total_Ventas,
                    SUM(CASE WHEN m.Tipo = 'VENTA' AND m.Tipo_Pago = 'CONTADO' THEN m.Monto ELSE 0 END) as Ventas_Contado,
                    SUM(CASE WHEN m.Tipo = 'VENTA' AND m.Tipo_Pago = 'CREDITO' THEN 1 ELSE 0 END) as Ventas_Credito,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'ABONO' THEN m.ID_Movimiento END) as Cantidad_Abonos,
                    SUM(CASE WHEN m.Tipo = 'ABONO' THEN m.Monto ELSE 0 END) as Total_Abonado,
                    COUNT(DISTINCT CASE WHEN m.Tipo = 'ABONO' THEN m.ID_Cliente END) as clientes_Abonaron,
                    SUM(CASE WHEN m.Tipo = 'GASTO' THEN m.Monto ELSE 0 END) as Total_Gastos
                FROM movimientos_caja_ruta m
                INNER JOIN asignacion_vendedores av ON m.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE m.ID_Usuario = %s
                AND m.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                GROUP BY DATE(m.Fecha), r.Nombre_Ruta
                ORDER BY Dia DESC
            """, (id_vendedor,))
            
            resumen = cursor.fetchall()
            
            return jsonify({
                'success': True,
                'vendedor': current_user.NombreUsuario,
                'resumen': resumen
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================================
# CLIENTES DE RUTA
# ==================================
@vendedor_bp.route('/vendedor/clientes')
@vendedor_required
def vendedor_clientes():
    """Lista de clientes del vendedor con su ruta asignada"""
    try:
        id_vendedor = int(current_user.id)
        
        # Obtener la ruta asignada al vendedor
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT av.ID_Asignacion, av.ID_Ruta, r.Nombre_Ruta
                FROM asignacion_vendedores av
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                WHERE av.ID_Usuario = %s AND av.Estado = 'Activa'
            """, (id_vendedor,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta activa asignada', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            # Parámetros de paginación y filtros
            page = request.args.get('page', 1, type=int)
            per_page = 10
            search = request.args.get('q', '')
            ruta_seleccionada = request.args.get('ruta', '')
            
            # Construir consulta base
            query_base = """
                FROM clientes c
                LEFT JOIN rutas r ON c.ID_Ruta = r.ID_Ruta
                WHERE c.Estado = 'ACTIVO'
                AND c.ID_Ruta = %s
            """
            params = [asignacion['ID_Ruta']]
            
            # Agregar filtro de búsqueda
            if search:
                query_base += """ AND (c.Nombre LIKE %s 
                                    OR c.Telefono LIKE %s 
                                    OR c.RUC_CEDULA LIKE %s)"""
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            # Agregar filtro de ruta específica (si se selecciona)
            if ruta_seleccionada and ruta_seleccionada != str(asignacion['ID_Ruta']):
                query_base += " AND c.ID_Ruta = %s"
                params.append(int(ruta_seleccionada))
            
            # Contar total
            cursor.execute(f"SELECT COUNT(*) as total {query_base}", params)
            total = cursor.fetchone()['total']
            
            # Obtener clientes paginados
            query_clientes = f"""
                SELECT 
                    c.ID_Cliente,
                    c.Nombre,
                    c.Telefono,
                    c.Direccion,
                    c.RUC_CEDULA,
                    c.Saldo_Pendiente_Total,
                    r.Nombre_Ruta
                {query_base}
                ORDER BY c.Nombre ASC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, (page - 1) * per_page])
            cursor.execute(query_clientes, params)
            clientes = cursor.fetchall()
            
            # Obtener todas las rutas disponibles para el filtro
            cursor.execute("""
                SELECT ID_Ruta, Nombre_Ruta 
                FROM rutas 
                WHERE ID_Empresa = (SELECT ID_Empresa FROM asignacion_vendedores WHERE ID_Usuario = %s LIMIT 1)
                AND Estado = 'Activa'
                ORDER BY Nombre_Ruta
            """, (id_vendedor,))
            rutas = cursor.fetchall()
            
            # OBTENER MÉTODOS DE PAGO
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM metodos_pago 
                ORDER BY Nombre
            """)
            metodos_pago = cursor.fetchall()
            
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('vendedor/clientes/clientes.html',
                                 clientes=clientes,
                                 total=total,
                                 page=page,
                                 per_page=per_page,
                                 total_pages=total_pages,
                                 search=search,
                                 ruta_seleccionada=ruta_seleccionada,
                                 rutas=rutas,
                                 metodos_pago=metodos_pago,
                                 fecha_actual=datetime.now().strftime('%d/%m/%Y'))
                             
    except Exception as e:
        print(f"Error en vendedor_clientes: {str(e)}")
        traceback.print_exc()
        flash('Error al cargar clientes', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))

@vendedor_bp.route('/vendedor/abono/<int:id_abono>/recibo')
@vendedor_required
def vendedor_recibo_abono(id_abono):
    """Generar recibo de abono simplificado con saldo de clientes"""
    try:
        id_vendedor = int(current_user.id)
        auto_print = request.args.get('autoPrint', 0)
        
        with get_db_cursor() as cursor:
            # PRIMERO: Buscar en abonos_detalle
            cursor.execute("""
                SELECT 
                    ad.ID_Detalle as id_abono,
                    ad.Monto_Aplicado,
                    ad.Fecha,
                    c.ID_Cliente,
                    c.Nombre as cliente_nombre,
                    c.RUC_CEDULA as cliente_ruc,
                    c.Saldo_Pendiente_Total as saldo_actual_cliente,
                    u.NombreUsuario as vendedor_nombre,
                    r.Nombre_Ruta as ruta_nombre,
                    mc.Concepto as movimiento_concepto,
                    mc.Tipo_Pago as tipo_pago,
                    mc.ID_MetodoPago,
                    mp.Nombre as metodo_pago_nombre,
                    e.Nombre_Empresa as empresa_nombre,
                    e.RUC as empresa_ruc,
                    e.Direccion as empresa_direccion,
                    e.Telefono as empresa_telefono
                FROM abonos_detalle ad
                INNER JOIN clientes c ON ad.ID_Cliente = c.ID_Cliente
                INNER JOIN usuarios u ON ad.ID_Usuario = u.ID_Usuario
                INNER JOIN asignacion_vendedores av ON ad.ID_Asignacion = av.ID_Asignacion
                INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                INNER JOIN movimientos_caja_ruta mc ON ad.ID_Movimiento_Caja = mc.ID_Movimiento
                LEFT JOIN metodos_pago mp ON mc.ID_MetodoPago = mp.ID_MetodoPago
                INNER JOIN empresa e ON av.ID_Empresa = e.ID_Empresa
                WHERE ad.ID_Detalle = %s
                AND ad.ID_Usuario = %s
            """, (id_abono, id_vendedor))
            
            abono = cursor.fetchone()
            
            # Si no encuentra en abonos_detalle, buscar directamente en movimientos_caja_ruta
            if not abono:
                print(f"Buscando en movimientos_caja_ruta para ID: {id_abono}")
                cursor.execute("""
                    SELECT 
                        mc.ID_Movimiento as id_abono,
                        mc.Monto as Monto_Aplicado,
                        mc.Fecha,
                        c.ID_Cliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        c.Saldo_Pendiente_Total as saldo_actual_cliente,
                        u.NombreUsuario as vendedor_nombre,
                        r.Nombre_Ruta as ruta_nombre,
                        mc.Concepto as movimiento_concepto,
                        mc.Tipo_Pago as tipo_pago,
                        mc.ID_MetodoPago,
                        mp.Nombre as metodo_pago_nombre,
                        e.Nombre_Empresa as empresa_nombre,
                        e.RUC as empresa_ruc,
                        e.Direccion as empresa_direccion,
                        e.Telefono as empresa_telefono
                    FROM movimientos_caja_ruta mc
                    INNER JOIN clientes c ON mc.ID_Cliente = c.ID_Cliente
                    INNER JOIN usuarios u ON mc.ID_Usuario = u.ID_Usuario
                    INNER JOIN asignacion_vendedores av ON mc.ID_Asignacion = av.ID_Asignacion
                    INNER JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
                    LEFT JOIN metodos_pago mp ON mc.ID_MetodoPago = mp.ID_MetodoPago
                    INNER JOIN empresa e ON av.ID_Empresa = e.ID_Empresa
                    WHERE mc.ID_Movimiento = %s
                    AND mc.ID_Usuario = %s
                    AND mc.Tipo = 'ABONO'
                """, (id_abono, id_vendedor))
                
                abono = cursor.fetchone()
            
            if not abono:
                flash('Abono no encontrado', 'error')
                return redirect(url_for('vendedor.vendedor_clientes'))
            
            # Calcular datos
            monto_abono = float(abono['Monto_Aplicado'])
            saldo_actual = float(abono['saldo_actual_cliente'])
            saldo_anterior = saldo_actual + monto_abono
            
            # Obtener el nombre del método de pago
            metodo_pago = abono.get('metodo_pago_nombre')
            if not metodo_pago:
                # Si no hay método de pago guardado, usar el Tipo_Pago
                tipo_pago = abono.get('tipo_pago') or 'CONTADO'
                metodo_pago = {
                    'CONTADO': 'EFECTIVO',
                    'CREDITO': 'CRÉDITO'
                }.get(tipo_pago, tipo_pago)
            
            # Formatear fecha correctamente
            fecha_abono = abono['Fecha']
            if isinstance(fecha_abono, str):
                from datetime import datetime
                fecha_abono = datetime.strptime(fecha_abono, '%Y-%m-%d %H:%M:%S')
            
            # Datos para el template - COINCIDIENDO CON EL TEMPLATE
            ticket_data = {
                'id_abono': abono['id_abono'],
                'fecha': fecha_abono.strftime('%d/%m/%Y %H:%M:%S'),
                'cliente': abono['cliente_nombre'],
                'cliente_ruc': abono['cliente_ruc'] or 'N/A',
                'vendedor': abono['vendedor_nombre'],
                'ruta': abono['ruta_nombre'],
                'concepto': abono['movimiento_concepto'],
                'metodo_pago': metodo_pago,
                'saldo_anterior_formateado': f"C$ {saldo_anterior:,.2f}",
                'monto_abono_formateado': f"C$ {monto_abono:,.2f}",
                'nuevo_saldo_formateado': f"C$ {saldo_actual:,.2f}",
                'empresa': {
                    'nombre': abono['empresa_nombre'],
                    'ruc': abono['empresa_ruc'],
                    'direccion': abono['empresa_direccion'] or '',
                    'telefono': abono['empresa_telefono'] or ''
                },
                'auto_print': auto_print
            }
            
            return render_template('vendedor/clientes/recibo_abono.html', ticket=ticket_data)
                             
    except Exception as e:
        print(f"Error en recibo: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error al generar recibo', 'error')
        return redirect(url_for('vendedor.vendedor_clientes'))

# ============================================
# GASTOS DE RUTA/COMPRAS (MANDO DE JEFE)
# ============================================

@vendedor_bp.route('/vendedor/gastos', methods=['GET', 'POST'])
@vendedor_required
def vendedor_gastos():
    """
    Ruta para gestionar los gastos de ruta/compras del vendedor durante su trayecto del dia.
    """
    
    # Obtener el ID del usuario actual (asumiendo que está en sesión)
    usuario_actual = current_user.id
    
    # Para GET y POST necesitamos la asignación activa primero
    try:
        with get_db_cursor() as cursor:
            # Obtener la asignación activa del vendedor para hoy
            cursor.execute("""
                SELECT ID_Asignacion, ID_Ruta, Fecha_Asignacion 
                FROM asignacion_vendedores 
                WHERE ID_Usuario = %s 
                AND DATE(Fecha_Asignacion) = CURDATE() 
                AND Estado = 'ACTIVA'
                ORDER BY Fecha_Asignacion DESC 
                LIMIT 1
            """, (usuario_actual,))
            
            asignacion = cursor.fetchone()
            
            if not asignacion:
                flash('No tienes una ruta asignada para hoy', 'warning')
                return redirect(url_for('vendedor.vendedor_dashboard'))
            
            id_asignacion = asignacion['ID_Asignacion']
    except Exception as e:
        flash(f'Error al verificar asignación: {str(e)}', 'error')
        return redirect(url_for('vendedor.vendedor_dashboard'))
    
    # Procesar el formulario cuando es POST
    if request.method == 'POST':
        concepto = request.form.get('concepto', '').strip()
        monto = request.form.get('monto', '').strip()
        tipo_pago = request.form.get('tipo_pago', 'CONTADO')
        
        # Validaciones básicas
        if not concepto or not monto:
            flash('El concepto y el monto son obligatorios', 'error')
            return redirect(url_for('vendedor.vendedor_gastos'))
        
        try:
            monto = float(monto)
            if monto <= 0:
                flash('El monto debe ser mayor a cero', 'error')
                return redirect(url_for('vendedor.vendedor_gastos'))
        except ValueError:
            flash('El monto debe ser un número válido', 'error')
            return redirect(url_for('vendedor.vendedor_gastos'))
        
        # Usamos get_db_cursor con commit=True para que haga commit automático
        try:
            with get_db_cursor(commit=True) as cursor:
                # Obtener el saldo acumulado actual
                cursor.execute("""
                    SELECT Saldo_Acumulado 
                    FROM movimientos_caja_ruta 
                    WHERE ID_Asignacion = %s 
                    AND Estado = 'ACTIVO'
                    ORDER BY Fecha DESC 
                    LIMIT 1
                """, (id_asignacion,))
                
                ultimo_movimiento = cursor.fetchone()
                
                # Convertir Decimal a float para la operación
                if ultimo_movimiento and ultimo_movimiento['Saldo_Acumulado'] is not None:
                    saldo_anterior = float(ultimo_movimiento['Saldo_Acumulado'])
                else:
                    saldo_anterior = 0.0
                
                # Calcular nuevo saldo (el gasto resta del saldo)
                nuevo_saldo = saldo_anterior - monto
                
                # Insertar el nuevo gasto
                cursor.execute("""
                    INSERT INTO movimientos_caja_ruta 
                    (ID_Asignacion, ID_Usuario, Tipo, Concepto, Monto, Tipo_Pago, Saldo_Acumulado, Estado)
                    VALUES (%s, %s, 'GASTO', %s, %s, %s, %s, 'ACTIVO')
                """, (id_asignacion, usuario_actual, concepto, monto, tipo_pago, nuevo_saldo))
                
                flash('Gasto registrado exitosamente', 'success')
            
        except Exception as e:
            flash(f'Error al registrar el gasto: {str(e)}', 'error')
            print(f"Error en vendedor_gastos POST: {e}")
        
        return redirect(url_for('vendedor.vendedor_gastos'))
    
    # Para GET: obtener los gastos del día
    try:
        with get_db_cursor() as cursor:
            # Obtener todos los gastos del día para esta asignación
            cursor.execute("""
                SELECT m.ID_Movimiento, m.Concepto, m.Monto, m.Tipo_Pago, 
                       DATE_FORMAT(m.Fecha, '%%H:%%i') as Hora,
                       m.Saldo_Acumulado
                FROM movimientos_caja_ruta m
                WHERE m.ID_Asignacion = %s 
                AND m.Tipo = 'GASTO'
                AND m.Estado = 'ACTIVO'
                AND DATE(m.Fecha) = CURDATE()
                ORDER BY m.Fecha DESC
            """, (id_asignacion,))
            
            gastos = cursor.fetchall()
            
            # Convertir Decimal a float para la plantilla
            for gasto in gastos:
                if gasto['Monto'] is not None:
                    gasto['Monto'] = float(gasto['Monto'])
                if gasto['Saldo_Acumulado'] is not None:
                    gasto['Saldo_Acumulado'] = float(gasto['Saldo_Acumulado'])
            
            # Calcular total de gastos del día
            cursor.execute("""
                SELECT COALESCE(SUM(Monto), 0) as Total_Gastos
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                AND Tipo = 'GASTO'
                AND Estado = 'ACTIVO'
                AND DATE(Fecha) = CURDATE()
            """, (id_asignacion,))
            
            total_gastos = cursor.fetchone()['Total_Gastos']
            total_gastos = float(total_gastos) if total_gastos is not None else 0
            
            # Obtener saldo actual
            cursor.execute("""
                SELECT Saldo_Acumulado
                FROM movimientos_caja_ruta
                WHERE ID_Asignacion = %s 
                AND Estado = 'ACTIVO'
                ORDER BY Fecha DESC
                LIMIT 1
            """, (id_asignacion,))
            
            saldo_actual = cursor.fetchone()
            if saldo_actual and saldo_actual['Saldo_Acumulado'] is not None:
                saldo_actual = float(saldo_actual['Saldo_Acumulado'])
            else:
                saldo_actual = 0
            
    except Exception as e:
        print(f"Error en vendedor_gastos GET: {e}")
        gastos = []
        total_gastos = 0
        saldo_actual = 0
        flash('Error al cargar los gastos', 'error')
    
    return render_template('vendedor/gastos/gastos.html', 
                         gastos=gastos, 
                         total_gastos=total_gastos,
                         saldo_actual=saldo_actual,
                         asignacion=asignacion)