import os
import logging
from werkzeug.utils import secure_filename
from flask import render_template, redirect, session, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime, timedelta
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================
# GASTOS OPERATIVOS
# ==========================================

@admin_bp.route('/gastos-operativos', methods=['GET'])
@admin_required
@bitacora_decorator("GASTOS")
def admin_gastos_operativos():
    try:
        # ========== PARÁMETROS DE FILTRO ==========
        filtro_periodo = request.args.get('filtro_periodo', 'mes')
        fecha_especifica = request.args.get('fecha', datetime.now().strftime('%Y-%m-%d'))
        fecha_inicio = request.args.get('fecha_inicio', '').strip()
        fecha_fin = request.args.get('fecha_fin', '').strip()
        semana_num = request.args.get('semana', str(datetime.now().isocalendar()[1]))
        anio_semana = request.args.get('anio_semana', datetime.now().strftime('%Y'))
        mes_filtro = request.args.get('mes', datetime.now().strftime('%Y-%m'))
        anio_filtro = request.args.get('anio', datetime.now().strftime('%Y'))
        
        if (fecha_inicio and fecha_fin and not request.args.get('filtro_periodo')) or filtro_periodo == 'personalizado':
            filtro_periodo = 'personalizado'
        
        # Filtros adicionales
        tipo_gasto_id = request.args.get('tipo_gasto', '')
        subcategoria_filtro = request.args.get('subcategoria', '')
        origen = request.args.get('origen', '')
        proveedor_id = request.args.get('proveedor', '')
        
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # ========== 1. VERIFICAR QUÉ CAMPOS EXISTEN EN LA VISTA ==========
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'vista_gastos_unificados'
            """)
            columnas_existentes = [row['COLUMN_NAME'] for row in cursor.fetchall()]
            
            # Construir SELECT dinámicamente
            select_fields = ['origen', 'tipo_gasto', 'subcategoria', 'fecha', 'monto', 'factura', 'proveedor', 'vehiculo', 'id_gasto', 'id_tipo']
            
            if 'id_proveedor' in columnas_existentes:
                select_fields.append('id_proveedor')
            else:
                select_fields.append('NULL as id_proveedor')
            
            if 'id_categoria_inv' in columnas_existentes:
                select_fields.append('id_categoria_inv')
            
            query_base = f"""
            SELECT {', '.join(select_fields)}
            FROM vista_gastos_unificados
            WHERE ID_Empresa = %s
            """
            
            params = [id_empresa]
            fecha_inicio_semana = None
            fecha_fin_semana = None
            
            # Filtro de período
            if filtro_periodo == 'personalizado':
                if not fecha_inicio:
                    fecha_inicio = datetime.now().strftime('%Y-%m-01')
                if not fecha_fin:
                    fecha_fin = datetime.now().strftime('%Y-%m-%d')
                query_base += " AND fecha BETWEEN %s AND %s"
                params.extend([fecha_inicio, fecha_fin])
                try:
                    f_ini_fmt = datetime.strptime(fecha_inicio, '%Y-%m-%d').strftime('%d/%m/%Y')
                    f_fin_fmt = datetime.strptime(fecha_fin, '%Y-%m-%d').strftime('%d/%m/%Y')
                    titulo_periodo = f"Gastos del {f_ini_fmt} al {f_fin_fmt}"
                except Exception:
                    titulo_periodo = f"Gastos del {fecha_inicio} al {fecha_fin}"
                
            elif filtro_periodo == 'dia':
                query_base += " AND fecha = %s"
                params.append(fecha_especifica)
                titulo_periodo = f"Gastos del día {datetime.strptime(fecha_especifica, '%Y-%m-%d').strftime('%d/%m/%Y')}"
                
            elif filtro_periodo == 'semana':
                año = int(anio_semana)
                semana = int(semana_num)
                fecha_inicio_semana = datetime.strptime(f'{año}-W{semana}-1', '%Y-W%W-%w').date()
                fecha_fin_semana = fecha_inicio_semana + timedelta(days=6)
                query_base += " AND fecha BETWEEN %s AND %s"
                params.extend([fecha_inicio_semana, fecha_fin_semana])
                titulo_periodo = f"Gastos de la semana {semana_num} ({fecha_inicio_semana.strftime('%d/%m')} - {fecha_fin_semana.strftime('%d/%m/%Y')})"
                
            elif filtro_periodo == 'mes':
                año, mes = mes_filtro.split('-')
                query_base += " AND YEAR(fecha) = %s AND MONTH(fecha) = %s"
                params.extend([año, mes])
                meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                nombre_mes = f"{meses_es[int(mes)]} {año}"
                titulo_periodo = f"Gastos de {nombre_mes}"
                
            elif filtro_periodo == 'acumulado':
                query_base += " AND YEAR(fecha) = %s AND fecha <= CURDATE()"
                params.append(anio_filtro)
                meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                mes_actual_nombre = meses_es[datetime.now().month]
                titulo_periodo = f"Gastos Acumulados {anio_filtro} (Enero - {mes_actual_nombre})"
                
            elif filtro_periodo == 'anual':
                query_base += " AND YEAR(fecha) = %s"
                params.append(anio_filtro)
                titulo_periodo = f"Gastos del año {anio_filtro}"
                
            elif filtro_periodo == 'todo':
                query_base += " AND fecha >= '2020-01-01'"
                titulo_periodo = "Todos los Gastos Registrados"
            else:
                titulo_periodo = "Gastos Operativos"
            
            # Filtros adicionales
            if tipo_gasto_id and tipo_gasto_id.isdigit():
                query_base += " AND id_tipo = %s"
                params.append(int(tipo_gasto_id))
            
            if subcategoria_filtro:
                query_base += " AND subcategoria = %s"
                params.append(subcategoria_filtro)
            
            if origen:
                query_base += " AND origen = %s"
                params.append(origen)
            
            if proveedor_id and proveedor_id.isdigit() and 'id_proveedor' in columnas_existentes:
                query_base += " AND id_proveedor = %s"
                params.append(int(proveedor_id))
            
            # Orden
            query_base += " ORDER BY fecha DESC, monto DESC"
            
            cursor.execute(query_base, params)
            resultados = cursor.fetchall()
            
            # Calcular totales del período
            total_periodo = sum(float(r['monto'] or 0) for r in resultados)
            total_inventario_periodo = sum(float(r['monto'] or 0) for r in resultados if r.get('origen') == 'INVENTARIO')
            total_directo_periodo = sum(float(r['monto'] or 0) for r in resultados if r.get('origen') == 'GASTO_DIRECTO')
            conteo_gastos = len(resultados)
            
            # ========== 2. TOTALES ACUMULADOS HISTÓRICOS ==========
            query_totales = """
            SELECT 
                'total_compras' AS concepto,
                COALESCE(SUM(dmi.Cantidad * dmi.Costo_Unitario), 0) AS total
            FROM movimientos_inventario mi
            LEFT JOIN detalle_movimientos_inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
            WHERE mi.Estado = 'Activa' AND mi.ID_TipoMovimiento = 1 AND mi.ID_Empresa = %s
            
            UNION ALL
            
            SELECT 
                'total_gastos' AS concepto,
                COALESCE(SUM(gg.Monto), 0) AS total
            FROM gastos_generales gg
            WHERE gg.Estado = 'Activo' AND gg.ID_Empresa = %s
            """
            cursor.execute(query_totales, [id_empresa, id_empresa])
            totales_acumulados = {row['concepto']: float(row['total'] or 0) for row in cursor.fetchall()}
            
            # ========== 3. LISTAS PARA FILTROS ==========
            cursor.execute("""
                SELECT DISTINCT id_tipo, tipo_gasto 
                FROM vista_gastos_unificados 
                WHERE ID_Empresa = %s AND tipo_gasto IS NOT NULL
                ORDER BY tipo_gasto
            """, [id_empresa])
            tipos_gasto_disponibles = cursor.fetchall()
            
            cursor.execute("""
                SELECT DISTINCT subcategoria 
                FROM vista_gastos_unificados 
                WHERE ID_Empresa = %s AND subcategoria IS NOT NULL AND subcategoria != ''
                ORDER BY subcategoria
            """, [id_empresa])
            subcategorias_disponibles = [r['subcategoria'] for r in cursor.fetchall()]
            
            if 'id_proveedor' in columnas_existentes:
                cursor.execute("""
                    SELECT DISTINCT id_proveedor, proveedor 
                    FROM vista_gastos_unificados 
                    WHERE ID_Empresa = %s AND proveedor IS NOT NULL
                    ORDER BY proveedor
                """, [id_empresa])
                proveedores_lista = cursor.fetchall()
            else:
                proveedores_lista = []
            
            años_disponibles = range(2020, datetime.now().year + 2)
            semanas_disponibles = range(1, 54)
            
            return render_template(
                'admin/gastos/gastos_operativos.html',
                # Filtros actuales
                filtro_periodo=filtro_periodo,
                fecha_especifica=fecha_especifica,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                semana_num=semana_num,
                anio_semana=anio_semana,
                mes_filtro=mes_filtro,
                anio_filtro=anio_filtro,
                tipo_gasto_id=tipo_gasto_id,
                subcategoria_filtro=subcategoria_filtro,
                origen=origen,
                proveedor_id=proveedor_id,
                # Datos principales
                resultados=resultados,
                total_periodo=total_periodo,
                total_inventario_periodo=total_inventario_periodo,
                total_directo_periodo=total_directo_periodo,
                conteo_gastos=conteo_gastos,
                titulo_periodo=titulo_periodo,
                totales_acumulados=totales_acumulados,
                # Listas para filtros
                tipos_gasto_disponibles=tipos_gasto_disponibles,
                subcategorias_disponibles=subcategorias_disponibles,
                proveedores_lista=proveedores_lista,
                años_disponibles=años_disponibles,
                semanas_disponibles=semanas_disponibles,
                titulo="Control de Gastos - Compras y Egresos Operativos"
            )
            
    except Exception as e:
        logger.error(f"Error en gastos operativos: {str(e)}", exc_info=True)
        flash(f'Error al cargar los gastos: {str(e)}', 'error')
        return redirect(url_for('admin.admin_dashboard'))

# ==========================================
# REGISTRAR GASTO
# ==========================================

@admin_bp.route('/gastos/registrar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRO_GASTO")
def registrar_gasto():
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Obtener listas para selects
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE Estado = 'Activo' AND ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo 
                FROM vehiculos 
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, [id_empresa])
            vehiculos = cursor.fetchall()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                id_subcategoria = request.form.get('id_subcategoria') or None
                fecha = request.form.get('fecha')
                monto_raw = request.form.get('monto', '').strip()
                descripcion = request.form.get('descripcion', '').strip()
                n_factura = request.form.get('n_factura', '').strip() or None
                id_proveedor = request.form.get('id_proveedor') or None
                id_vehiculo = request.form.get('id_vehiculo') or None
                metodo_pago = request.form.get('metodo_pago', 'EFECTIVO')
                
                # Validaciones
                if not id_tipo_gasto:
                    flash('Debe seleccionar una categoría o tipo de gasto', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                if not fecha:
                    flash('Debe ingresar la fecha del egreso', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                try:
                    monto = float(monto_raw)
                    if monto <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    flash('Debe ingresar un monto válido y mayor a 0', 'error')
                    return redirect(url_for('admin.registrar_gasto'))
                
                # Manejo de comprobante (archivo adjunto opcional)
                comprobante_nombre = None
                if 'comprobante' in request.files:
                    archivo = request.files['comprobante']
                    if archivo and archivo.filename and allowed_file(archivo.filename):
                        ext = archivo.filename.rsplit('.', 1)[1].lower()
                        nombre_limpio = secure_filename(archivo.filename.rsplit('.', 1)[0])
                        comprobante_nombre = f"gasto_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{nombre_limpio}.{ext}"
                        upload_folder = os.path.join('static', 'uploads', 'gastos')
                        os.makedirs(upload_folder, exist_ok=True)
                        archivo.save(os.path.join(upload_folder, comprobante_nombre))
                
                # Insertar gasto general
                cursor.execute("""
                    INSERT INTO gastos_generales (
                        ID_Tipo_Gasto, ID_Subcategoria, Fecha, Monto, Descripcion,
                        N_Factura, ID_Proveedor, ID_Vehiculo, Metodo_Pago, 
                        Comprobante, ID_Empresa, Estado, Fecha_Registro, ID_Usuario_Registro
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Activo', NOW(), %s)
                """, (
                    id_tipo_gasto, id_subcategoria, fecha, monto, descripcion,
                    n_factura, id_proveedor, id_vehiculo, metodo_pago,
                    comprobante_nombre, id_empresa, id_usuario
                ))
                
                id_gasto = cursor.lastrowid
                
                # Si es gasto asociado a vehículo, registrar detalle adicional
                if id_vehiculo:
                    kilometraje = request.form.get('kilometraje') or None
                    tipo_mantenimiento = request.form.get('tipo_mantenimiento') or None
                    taller = request.form.get('taller') or None
                    
                    cursor.execute("""
                        INSERT INTO gastos_vehiculo_detalle (
                            ID_Gasto, ID_Vehiculo, Kilometraje, Tipo_Mantenimiento, Taller
                        ) VALUES (%s, %s, %s, %s, %s)
                    """, (id_gasto, id_vehiculo, kilometraje, tipo_mantenimiento, taller))
                
                flash(f'Gasto registrado exitosamente. Total: C$ {monto:,.2f}', 'success')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            return render_template(
                'admin/gastos/registrar_gastos.html',
                tipos_gasto=tipos_gasto,
                proveedores=proveedores,
                vehiculos=vehiculos,
                hoy=datetime.now().strftime('%Y-%m-%d'),
                titulo="Registrar Nuevo Gasto Operativo"
            )
            
    except Exception as e:
        logger.error(f"Error al registrar gasto: {str(e)}", exc_info=True)
        flash(f'Error al registrar el gasto: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

# ==========================================
# EDITAR GASTO
# ==========================================

@admin_bp.route('/gastos/editar/<int:id_gasto>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_GASTO")
def editar_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Obtener el gasto existente
            cursor.execute("""
                SELECT 
                    gg.*,
                    tg.Nombre AS tipo_gasto_nombre,
                    sg.Nombre AS subcategoria_nombre
                FROM gastos_generales gg
                LEFT JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
                WHERE gg.ID_Gasto = %s AND gg.ID_Empresa = %s
            """, [id_gasto, id_empresa])
            gasto = cursor.fetchone()
            
            if not gasto:
                flash('Gasto no encontrado o no pertenece a su empresa', 'error')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            if gasto.get('Estado') == 'Anulado':
                flash('No se puede editar un gasto que ya ha sido anulado', 'warning')
                return redirect(url_for('admin.ver_gasto', id_gasto=id_gasto))
            
            # Obtener listas maestras
            cursor.execute("""
                SELECT ID_Tipo_Gasto, Nombre 
                FROM tipos_gasto 
                WHERE Estado = 'Activo' AND ID_Empresa = %s
                ORDER BY Nombre
            """, [id_empresa])
            tipos_gasto = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Subcategoria, Nombre 
                FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [gasto['ID_Tipo_Gasto']])
            subcategorias = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Proveedor, Nombre 
                FROM proveedores 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            cursor.execute("""
                SELECT ID_Vehiculo, Placa, Marca, Modelo 
                FROM vehiculos 
                WHERE ID_Empresa = %s AND Estado != 'Inactivo'
                ORDER BY Placa
            """, [id_empresa])
            vehiculos = cursor.fetchall()
            
            # Obtener detalle vehicular actual si existe
            cursor.execute("""
                SELECT * FROM gastos_vehiculo_detalle WHERE ID_Gasto = %s
            """, [id_gasto])
            detalle_vehiculo = cursor.fetchone()
            
            if request.method == 'POST':
                id_tipo_gasto = request.form.get('id_tipo_gasto')
                id_subcategoria = request.form.get('id_subcategoria') or None
                fecha = request.form.get('fecha')
                monto_raw = request.form.get('monto', '').strip()
                descripcion = request.form.get('descripcion', '').strip()
                n_factura = request.form.get('n_factura', '').strip() or None
                id_proveedor = request.form.get('id_proveedor') or None
                id_vehiculo = request.form.get('id_vehiculo') or None
                metodo_pago = request.form.get('metodo_pago', 'EFECTIVO')
                
                # Validaciones
                if not id_tipo_gasto:
                    flash('Debe seleccionar un tipo de gasto', 'error')
                    return redirect(url_for('admin.editar_gasto', id_gasto=id_gasto))
                
                if not fecha:
                    flash('Debe ingresar la fecha del egreso', 'error')
                    return redirect(url_for('admin.editar_gasto', id_gasto=id_gasto))
                
                try:
                    monto = float(monto_raw)
                    if monto <= 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    flash('Debe ingresar un monto válido y mayor a 0', 'error')
                    return redirect(url_for('admin.editar_gasto', id_gasto=id_gasto))
                
                # Manejo de comprobante (reemplazar si se envía nuevo archivo)
                comprobante_nombre = gasto.get('Comprobante')
                if 'comprobante' in request.files:
                    archivo = request.files['comprobante']
                    if archivo and archivo.filename and allowed_file(archivo.filename):
                        ext = archivo.filename.rsplit('.', 1)[1].lower()
                        nombre_limpio = secure_filename(archivo.filename.rsplit('.', 1)[0])
                        comprobante_nombre = f"gasto_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{nombre_limpio}.{ext}"
                        upload_folder = os.path.join('static', 'uploads', 'gastos')
                        os.makedirs(upload_folder, exist_ok=True)
                        archivo.save(os.path.join(upload_folder, comprobante_nombre))
                
                # Actualizar gasto general
                cursor.execute("""
                    UPDATE gastos_generales SET
                        ID_Tipo_Gasto = %s,
                        ID_Subcategoria = %s,
                        Fecha = %s,
                        Monto = %s,
                        Descripcion = %s,
                        N_Factura = %s,
                        ID_Proveedor = %s,
                        ID_Vehiculo = %s,
                        Metodo_Pago = %s,
                        Comprobante = %s
                    WHERE ID_Gasto = %s AND ID_Empresa = %s
                """, (
                    id_tipo_gasto, id_subcategoria, fecha, monto, descripcion,
                    n_factura, id_proveedor, id_vehiculo, metodo_pago,
                    comprobante_nombre, id_gasto, id_empresa
                ))
                
                # Actualizar o insertar/eliminar detalle vehicular
                if id_vehiculo:
                    kilometraje = request.form.get('kilometraje') or None
                    tipo_mantenimiento = request.form.get('tipo_mantenimiento') or None
                    taller = request.form.get('taller') or None
                    
                    if detalle_vehiculo:
                        cursor.execute("""
                            UPDATE gastos_vehiculo_detalle SET
                                ID_Vehiculo = %s,
                                Kilometraje = %s,
                                Tipo_Mantenimiento = %s,
                                Taller = %s
                            WHERE ID_Gasto = %s
                        """, (id_vehiculo, kilometraje, tipo_mantenimiento, taller, id_gasto))
                    else:
                        cursor.execute("""
                            INSERT INTO gastos_vehiculo_detalle (
                                ID_Gasto, ID_Vehiculo, Kilometraje, Tipo_Mantenimiento, Taller
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, (id_gasto, id_vehiculo, kilometraje, tipo_mantenimiento, taller))
                else:
                    if detalle_vehiculo:
                        cursor.execute("DELETE FROM gastos_vehiculo_detalle WHERE ID_Gasto = %s", [id_gasto])
                
                flash(f'Gasto #{id_gasto} actualizado exitosamente.', 'success')
                return redirect(url_for('admin.ver_gasto', id_gasto=id_gasto))
            
            return render_template(
                'admin/gastos/editar_gasto.html',
                gasto=gasto,
                tipos_gasto=tipos_gasto,
                subcategorias=subcategorias,
                proveedores=proveedores,
                vehiculos=vehiculos,
                detalle_vehiculo=detalle_vehiculo,
                titulo=f"Editar Gasto #{id_gasto}"
            )
            
    except Exception as e:
        logger.error(f"Error al editar gasto #{id_gasto}: {str(e)}", exc_info=True)
        flash(f'Error al actualizar el gasto: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

# ==========================================
# AJAX: OBTENER SUBCATEGORÍAS
# ==========================================

@admin_bp.route('/gastos/get_subcategorias', methods=['GET'])
@admin_required
def get_subcategorias():
    try:
        id_tipo_gasto = request.args.get('id_tipo_gasto')
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Subcategoria, Nombre 
                FROM subcategorias_gasto 
                WHERE ID_Tipo_Gasto = %s AND Estado = 'Activo'
                ORDER BY Nombre
            """, [id_tipo_gasto])
            subcategorias = cursor.fetchall()
            
        return jsonify({'success': True, 'subcategorias': subcategorias})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# VER GASTO DETALLE
# ==========================================

@admin_bp.route('/gastos/ver/<int:id_gasto>', methods=['GET'])
@admin_required
def ver_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    gg.*,
                    tg.Nombre AS tipo_gasto_nombre,
                    sg.Nombre AS subcategoria_nombre,
                    pr.Nombre AS proveedor_nombre,
                    v.Placa AS vehiculo_placa,
                    v.Marca AS vehiculo_marca,
                    v.Modelo AS vehiculo_modelo,
                    u.NombreUsuario AS usuario_registro_nombre
                FROM gastos_generales gg
                LEFT JOIN tipos_gasto tg ON gg.ID_Tipo_Gasto = tg.ID_Tipo_Gasto
                LEFT JOIN subcategorias_gasto sg ON gg.ID_Subcategoria = sg.ID_Subcategoria
                LEFT JOIN proveedores pr ON gg.ID_Proveedor = pr.ID_Proveedor
                LEFT JOIN vehiculos v ON gg.ID_Vehiculo = v.ID_Vehiculo
                LEFT JOIN usuarios u ON gg.ID_Usuario_Registro = u.ID_Usuario
                WHERE gg.ID_Gasto = %s AND gg.ID_Empresa = %s
            """, [id_gasto, id_empresa])
            gasto = cursor.fetchone()
            
            if not gasto:
                flash('Gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            # Obtener detalle de vehículo si aplica
            detalle_vehiculo = None
            if gasto['ID_Vehiculo']:
                cursor.execute("""
                    SELECT * FROM gastos_vehiculo_detalle WHERE ID_Gasto = %s
                """, [id_gasto])
                detalle_vehiculo = cursor.fetchone()
            
            return render_template(
                'admin/gastos/ver_gasto.html',
                gasto=gasto,
                detalle_vehiculo=detalle_vehiculo,
                titulo=f"Detalle del Gasto #{id_gasto}"
            )
            
    except Exception as e:
        logger.error(f"Error al ver gasto #{id_gasto}: {str(e)}", exc_info=True)
        flash(f'Error al consultar el detalle: {str(e)}', 'error')
        return redirect(url_for('admin.admin_gastos_operativos'))

# ==========================================
# ANULAR GASTO
# ==========================================

@admin_bp.route('/gastos/anular/<int:id_gasto>', methods=['POST'])
@admin_required
@bitacora_decorator("ANULAR_GASTO")
def anular_gasto(id_gasto):
    try:
        id_empresa = session.get('id_empresa', 1)
        id_usuario = current_user.id
        
        with get_db_cursor(True) as cursor:
            # Validar que el gasto exista y no esté ya anulado
            cursor.execute("""
                SELECT ID_Gasto, Estado, Monto 
                FROM gastos_generales 
                WHERE ID_Gasto = %s AND ID_Empresa = %s
            """, [id_gasto, id_empresa])
            gasto = cursor.fetchone()
            
            if not gasto:
                flash('Gasto no encontrado', 'error')
                return redirect(url_for('admin.admin_gastos_operativos'))
            
            if gasto['Estado'] == 'Anulado':
                flash('Este gasto ya se encuentra anulado', 'info')
                return redirect(url_for('admin.ver_gasto', id_gasto=id_gasto))
            
            # Actualizar estado a Anulado y registrar nota en Descripcion
            cursor.execute("""
                UPDATE gastos_generales 
                SET Estado = 'Anulado', 
                    Descripcion = CONCAT(IFNULL(Descripcion, ''), '\n[ANULADO por usuario ID ', %s, ' en ', NOW(), ']')
                WHERE ID_Gasto = %s AND ID_Empresa = %s
            """, [id_usuario, id_gasto, id_empresa])
            
            if cursor.rowcount > 0:
                flash(f'Gasto #{id_gasto} anulado correctamente.', 'success')
            else:
                flash('No se pudo anular el gasto', 'error')
                
    except Exception as e:
        logger.error(f"Error al anular gasto #{id_gasto}: {str(e)}", exc_info=True)
        flash(f'Error al anular gasto: {str(e)}', 'error')
    
    return redirect(url_for('admin.admin_gastos_operativos'))
