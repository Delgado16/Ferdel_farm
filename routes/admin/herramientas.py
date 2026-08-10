import csv
import io
from flask import make_response, render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user
from datetime import datetime, date
from decimal import Decimal
from config.database import get_db_cursor
from auth.decorators import admin_required
from . import admin_bp
from helpers.bitacora import bitacora_decorator, registrar_bitacora

#============================
#=== MODULO HERRAMIENTAS ====
#============================
@admin_bp.route('/admin/bitacora')
@admin_required
def admin_bitacora():
    """Vista principal de la bitácora del sistema"""
    try:
        modulo = request.args.get('modulo')
        fecha_desde = request.args.get('fecha_desde')
        fecha_hasta = request.args.get('fecha_hasta')
        
        with get_db_cursor() as cursor:
            # Construir query con filtros
            query = """
                SELECT b.*, u.NombreUsuario 
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                WHERE 1=1
            """
            params = []
            
            if modulo:
                query += " AND b.Modulo = %s"
                params.append(modulo)
                
            if fecha_desde:
                query += " AND DATE(b.Fecha) >= %s"
                params.append(fecha_desde)
                
            if fecha_hasta:
                query += " AND DATE(b.Fecha) <= %s"
                params.append(fecha_hasta)
            
            query += " ORDER BY b.Fecha DESC LIMIT 200"
            
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            # Obtener módulos únicos para el dropdown
            cursor.execute("SELECT DISTINCT Modulo FROM bitacora WHERE Modulo IS NOT NULL ORDER BY Modulo")
            modulos = cursor.fetchall()
            
            return render_template('admin/bitacora.html', 
                                 registros=registros, 
                                 modulos=modulos)
            
    except Exception as e:
        flash(f"Error al cargar bitácora: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))

@admin_bp.route('/admin/bitacora/limpiar', methods=['POST'])
@admin_required
def limpiar_bitacora():
    """Limpiar registros antiguos de la bitácora"""
    try:
        with get_db_cursor(commit=True) as cursor:
            # Mantener solo los últimos 1000 registros
            cursor.execute("""
                DELETE FROM bitacora 
                WHERE ID_Bitacora NOT IN (
                    SELECT ID_Bitacora FROM (
                        SELECT ID_Bitacora FROM bitacora 
                        ORDER BY Fecha DESC 
                        LIMIT 1000
                    ) AS temp
                )
            """)
            
            registros_eliminados = cursor.rowcount
            registrar_bitacora(modulo="BITACORA", accion=f"LIMPIAR_BITACORA: {registros_eliminados} registros eliminados")
            
            flash(f"Bitácora limpiada exitosamente. Se eliminaron {registros_eliminados} registros antiguos.", "success")
            
    except Exception as e:
        flash(f"Error al limpiar bitácora: {e}", "danger")
    
    return redirect(url_for('admin.admin_bitacora'))

@admin_bp.route('/admin/bitacora/exportar')
@admin_required
def exportar_bitacora():
    """Exportar bitácora a CSV"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT b.Fecha, u.NombreUsuario, b.Modulo, b.Accion, b.IP_Acceso
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                ORDER BY b.Fecha DESC
            """)
            registros = cursor.fetchall()
            
            # Crear respuesta CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Fecha', 'Usuario', 'Módulo', 'Acción', 'IP'])
            
            for registro in registros:
                writer.writerow([
                    registro['Fecha'].strftime('%Y-%m-%d %H:%M:%S'),
                    registro['NombreUsuario'] or 'Sistema',
                    registro['Modulo'] or 'N/A',
                    registro['Accion'] or 'N/A',
                    registro['IP_Acceso'] or 'N/A'
                ])
            
            # Registrar exportación
            registrar_bitacora(modulo="BITACORA", accion="EXPORTAR_BITACORA_CSV")
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=bitacora_sistema.csv"
            response.headers["Content-type"] = "text/csv"
            return response
            
    except Exception as e:
        flash(f"Error al exportar bitácora: {e}", "danger")
        return redirect(url_for('admin.admin_bitacora'))

@admin_bp.route('/admin/config/visibilidad', methods=['GET', 'POST'])
@admin_required
def config_visibilidad():
    """Configurar visibilidad de categorías"""
    
    if request.method == 'POST':
        try:
            with get_db_cursor(commit=True) as cursor:
                # Procesar TODAS las categorías
                cursor.execute("SELECT ID_Categoria FROM categorias_producto")
                todas_categorias = cursor.fetchall()
                
                for cat in todas_categorias:
                    categoria_id = cat['ID_Categoria']
                    
                    # Para clientes Comunes
                    key_comun = f"cat_{categoria_id}_Comun"
                    visible_comun = 1 if key_comun in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_categorias 
                        (tipo_cliente, ID_Categoria, visible) 
                        VALUES ('Comun', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (categoria_id, visible_comun, visible_comun))
                    
                    # Para clientes Especiales
                    key_especial = f"cat_{categoria_id}_Especial"
                    visible_especial = 1 if key_especial in request.form else 0
                    
                    cursor.execute("""
                        INSERT INTO config_visibilidad_categorias 
                        (tipo_cliente, ID_Categoria, visible) 
                        VALUES ('Especial', %s, %s)
                        ON DUPLICATE KEY UPDATE visible = %s
                    """, (categoria_id, visible_especial, visible_especial))
                
                flash('✅ Configuración guardada exitosamente', 'success')
                return redirect(url_for('admin.config_visibilidad'))
                
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
    
    # GET: Mostrar formulario
    with get_db_cursor() as cursor:
        # Consulta CORREGIDA - sin productos_activos
        cursor.execute("""
            SELECT 
                c.ID_Categoria,
                c.Descripcion as nombre,
                COALESCE(cfg_comun.visible, 0) as comun_visible,
                COALESCE(cfg_especial.visible, 0) as especial_visible
            FROM categorias_producto c
            LEFT JOIN config_visibilidad_categorias cfg_comun 
                ON c.ID_Categoria = cfg_comun.ID_Categoria 
                AND cfg_comun.tipo_cliente = 'Comun'
            LEFT JOIN config_visibilidad_categorias cfg_especial 
                ON c.ID_Categoria = cfg_especial.ID_Categoria 
                AND cfg_especial.tipo_cliente = 'Especial'
            ORDER BY c.Descripcion
        """)
        categorias = cursor.fetchall()
    
    return render_template('admin/config/visibilidad.html', categorias=categorias)


#==================================
#=== MODULO CONFIGURACION GENERAL =
#==================================
@admin_bp.route('/admin/config/general', methods=['GET', 'POST'])
@admin_required
def config_general():
    """Vista y procesamiento de la configuración general del sistema"""
    if request.method == 'POST':
        try:
            llaves_config = [
                'empresa_nombre', 'empresa_ruc', 'empresa_direccion', 'empresa_telefono',
                'iva_porcentaje', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password'
            ]
            
            with get_db_cursor(commit=True) as cursor:
                for llave in llaves_config:
                    valor = request.form.get(llave, '').strip()
                    
                    # Validar porcentaje de IVA
                    if llave == 'iva_porcentaje':
                        try:
                            # Asegurar que sea decimal válido
                            float(valor)
                        except ValueError:
                            flash("❌ El porcentaje del IVA debe ser un número válido.", "danger")
                            return redirect(url_for('admin.config_general'))
                            
                    cursor.execute("""
                        INSERT INTO config_sistema (llave, valor) 
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE valor = %s
                    """, (llave, valor, valor))
            
            registrar_bitacora(modulo="CONFIGURACION", accion="ACTUALIZAR_CONFIGURACION_GENERAL")
            flash("✅ Configuración guardada exitosamente.", "success")
            return redirect(url_for('admin.config_general'))
            
        except Exception as e:
            flash(f"❌ Error al guardar la configuración: {e}", "danger")
            return redirect(url_for('admin.config_general'))
            
    # GET: Obtener configuraciones actuales
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT llave, valor FROM config_sistema")
            rows = cursor.fetchall()
            config = {row['llave']: row['valor'] for row in rows}
            
            # Asegurar que todas las llaves existan en el diccionario para evitar KeyError en plantilla
            llaves_esperadas = [
                'empresa_nombre', 'empresa_ruc', 'empresa_direccion', 'empresa_telefono',
                'iva_porcentaje', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password'
            ]
            for llave in llaves_esperadas:
                if llave not in config:
                    config[llave] = ""
                    
            return render_template('admin/config/general.html', config=config)
    except Exception as e:
        flash(f"❌ Error al cargar configuración: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


#==================================
#=== MODULO RESPALDOS DE BD =======
#==================================
@admin_bp.route('/admin/backup')
@admin_required
def admin_backup():
    """Vista principal de la gestión de respaldos"""
    try:
        with get_db_cursor() as cursor:
            # Obtener el tamaño aproximado de la base de datos
            cursor.execute("SELECT DATABASE() as db_name")
            db_name = cursor.fetchone()['db_name']
            
            cursor.execute("""
                SELECT SUM(data_length + index_length) / 1024 / 1024 AS size_mb 
                FROM information_schema.TABLES 
                WHERE table_schema = %s
            """, (db_name,))
            size_mb = cursor.fetchone()['size_mb'] or 0.0
            
            cursor.execute("""
                SELECT table_name, 
                       COALESCE(table_rows, 0) AS table_rows, 
                       COALESCE((data_length + index_length) / 1024, 0.0) AS size_kb 
                FROM information_schema.TABLES 
                WHERE table_schema = %s
                ORDER BY table_name
            """, (db_name,))
            tablas = cursor.fetchall()
            
            return render_template('admin/herramientas/backup.html', 
                                 db_name=db_name, 
                                 size_mb=round(float(size_mb), 2), 
                                 tablas=tablas)
    except Exception as e:
        flash(f"❌ Error al cargar información de respaldos: {e}", "danger")
        return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/backup/generar')
@admin_required
def generar_backup():
    """Generar y descargar un archivo .sql del respaldo de la base de datos"""
    try:
        output = io.StringIO()
        output.write("-- Respaldador de Base de Datos Ferdel (Pure Python)\n")
        output.write(f"-- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write("-- --------------------------------------------------------\n\n")
        output.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")
        
        with get_db_cursor(commit=False) as cursor:
            # Obtener nombre de la base de datos actual
            cursor.execute("SELECT DATABASE() as db_name")
            db_name = cursor.fetchone()['db_name']
            output.write(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n")
            output.write(f"USE `{db_name}`;\n\n")
            
            cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cursor.fetchall()]
            
            # 1. Primero las estructuras e inserciones de tablas reales
            for table in tables:
                # Comprobar si es vista
                cursor.execute(f"SHOW FULL TABLES LIKE '{table}'")
                table_info = cursor.fetchone()
                is_view = table_info and list(table_info.values())[1] == 'VIEW'
                if is_view:
                    continue
                    
                output.write(f"-- --------------------------------------------------------\n")
                output.write(f"-- Estructura de tabla para `{table}`\n")
                output.write(f"-- --------------------------------------------------------\n")
                output.write(f"DROP TABLE IF EXISTS `{table}`;\n")
                
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_stmt = cursor.fetchone()
                sql_create = list(create_stmt.values())[1]
                output.write(f"{sql_create};\n\n")
                
                # Obtener datos de la tabla
                output.write(f"-- Datos de la tabla `{table}`\n")
                cursor.execute(f"SELECT * FROM `{table}`")
                rows = cursor.fetchall()
                if rows:
                    columns = list(rows[0].keys())
                    col_names = ", ".join([f"`{col}`" for col in columns])
                    
                    for row in rows:
                        vals = []
                        for col in columns:
                            val = row[col]
                            if val is None:
                                vals.append("NULL")
                            elif isinstance(val, (int, float, Decimal)):
                                vals.append(str(val))
                            elif isinstance(val, (datetime, date)):
                                vals.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S') if isinstance(val, datetime) else val.strftime('%Y-%m-%d')}'")
                            elif isinstance(val, bytes):
                                vals.append(f"0x{val.hex()}")
                            else:
                                # Escapar comillas y backslashes
                                escaped_val = str(val).replace("\\", "\\\\").replace("'", "\\'")
                                vals.append(f"'{escaped_val}'")
                                
                        output.write(f"INSERT INTO `{table}` ({col_names}) VALUES ({', '.join(vals)});\n")
                output.write("\n")
                
            # 2. Después las vistas
            for table in tables:
                cursor.execute(f"SHOW FULL TABLES LIKE '{table}'")
                table_info = cursor.fetchone()
                is_view = table_info and list(table_info.values())[1] == 'VIEW'
                if not is_view:
                    continue
                    
                output.write(f"-- --------------------------------------------------------\n")
                output.write(f"-- Estructura de vista `{table}`\n")
                output.write(f"-- --------------------------------------------------------\n")
                output.write(f"DROP VIEW IF EXISTS `{table}`;\n")
                
                cursor.execute(f"SHOW CREATE VIEW `{table}`")
                create_stmt = cursor.fetchone()
                sql_create = list(create_stmt.values())[1]
                output.write(f"{sql_create};\n\n")
                
        output.write("SET FOREIGN_KEY_CHECKS = 1;\n")
        
        filename = f"backup_ferdel_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-type"] = "application/sql"
        
        registrar_bitacora(modulo="RESPALDO", accion=f"GENERAR_BACKUP_SQL: {filename}")
        return response
        
    except Exception as e:
        flash(f"❌ Error al generar respaldo: {e}", "danger")
        return redirect(url_for('admin.admin_backup'))


@admin_bp.route('/admin/backup/restaurar', methods=['POST'])
@admin_required
def restaurar_backup():
    """Restaurar base de datos desde un archivo .sql subido"""
    try:
        file = request.files.get('backup_file')
        if not file or not file.filename.endswith('.sql'):
            flash("❌ Por favor seleccione un archivo .sql válido", "danger")
            return redirect(url_for('admin.admin_backup'))
            
        sql_content = file.read().decode('utf-8', errors='ignore')
        
        # Parseador simple de sentencias SQL separadas por punto y coma (;)
        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
                continue
            current_stmt.append(line)
            if stripped.endswith(';'):
                statements.append(" ".join(current_stmt))
                current_stmt = []
                
        with get_db_cursor(commit=True) as cursor:
            # Desactivar temporalmente revisión de llaves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            exitosas = 0
            errores = 0
            for stmt in statements:
                stmt_strip = stmt.strip()
                if not stmt_strip:
                    continue
                try:
                    cursor.execute(stmt_strip)
                    exitosas += 1
                except Exception as stmt_err:
                    errores += 1
                    print(f"Error al ejecutar sentencia de backup: {stmt_err}\nSentencia: {stmt_strip[:150]}")
            
            # Reactivar llaves foráneas
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
            registrar_bitacora(modulo="RESPALDO", accion=f"RESTAURAR_BACKUP: {exitosas} sentencias ejecutadas, {errores} errores")
            
            if errores == 0:
                flash(f"✅ Base de datos restaurada con éxito. Se ejecutaron {exitosas} sentencias sin errores.", "success")
            else:
                flash(f"⚠️ Base de datos restaurada con advertencias. {exitosas} exitosas, {errores} fallidas. Revisa la consola para más detalles.", "warning")
                
    except Exception as e:
        flash(f"❌ Error al restaurar base de datos: {e}", "danger")
        
    return redirect(url_for('admin.admin_backup'))

