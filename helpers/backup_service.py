"""
Módulo de servicio para respaldos de base de datos (Backups automáticos y manuales)
Permite generar SQL dumps puros en Python, rotar respaldos antiguos,
guardar copias locales en el servidor y programar respaldos cada 24 horas.
"""
import os
import io
import time
import glob
import logging
import threading
from datetime import datetime, date, timedelta
from decimal import Decimal

from config.database import get_db_cursor
from helpers.bitacora import registrar_bitacora

logger = logging.getLogger(__name__)

# Directorio por defecto para guardar los respaldos
BACKUP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backups'))


def obtener_directorio_backups():
    """Garantiza que el directorio de respaldos exista y retorna su ruta absoluta"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def generar_script_sql():
    """
    Genera el script SQL completo de la base de datos actual (Pure Python).
    Incluye estructura DROP/CREATE, datos INSERT y vistas.
    """
    output = io.StringIO()
    output.write("-- ========================================================\n")
    output.write("-- Respaldador Automático de Base de Datos Ferdel (Pure Python)\n")
    output.write(f"-- Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("-- ========================================================\n\n")
    output.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

    with get_db_cursor(commit=False) as cursor:
        cursor.execute("SELECT DATABASE() as db_name")
        res_db = cursor.fetchone()
        db_name = res_db['db_name'] if res_db else 'ferdel'

        output.write(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;\n")
        output.write(f"USE `{db_name}`;\n\n")

        cursor.execute("SHOW TABLES")
        tables = [list(row.values())[0] for row in cursor.fetchall()]

        # 1. Tablas y sus registros
        for table in tables:
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

            output.write(f"-- Registros de la tabla `{table}`\n")
            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()
            if rows:
                columns = list(rows[0].keys())
                col_names = ", ".join([f"`{col}`" for col in columns])

                # Escritura de INSERT en bloques de hasta 100 filas
                chunk_size = 100
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i:i + chunk_size]
                    rows_values = []
                    for row in chunk:
                        vals = []
                        for col in columns:
                            val = row[col]
                            if val is None:
                                vals.append("NULL")
                            elif isinstance(val, (int, float, Decimal)):
                                vals.append(str(val))
                            elif isinstance(val, (datetime, date)):
                                if isinstance(val, datetime):
                                    vals.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                                else:
                                    vals.append(f"'{val.strftime('%Y-%m-%d')}'")
                            elif isinstance(val, bytes):
                                vals.append(f"0x{val.hex()}")
                            else:
                                escaped_val = str(val).replace("\\", "\\\\").replace("'", "\\'")
                                vals.append(f"'{escaped_val}'")
                        rows_values.append(f"({', '.join(vals)})")

                    output.write(f"INSERT INTO `{table}` ({col_names}) VALUES\n")
                    output.write(",\n".join(rows_values) + ";\n")
            output.write("\n")

        # 2. Vistas
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
    return output.getvalue()


def rotar_backups_antiguos(dias_retencion=15, min_archivos=5):
    """
    Elimina archivos de respaldo con más de 'dias_retencion' días de antigüedad,
    asegurando conservar al menos 'min_archivos' más recientes.
    """
    directorio = obtener_directorio_backups()
    archivos = glob.glob(os.path.join(directorio, "backup_ferdel_*.sql"))
    if len(archivos) <= min_archivos:
        return 0

    archivos.sort(key=os.path.getmtime, reverse=True)
    archivos_evaluar = archivos[min_archivos:]
    limite_tiempo = time.time() - (dias_retencion * 86400)
    eliminados = 0

    for filepath in archivos_evaluar:
        try:
            if os.path.getmtime(filepath) < limite_tiempo:
                os.remove(filepath)
                eliminados += 1
                logger.info(f"Respaldo antiguo rotado/eliminado: {os.path.basename(filepath)}")
        except Exception as e:
            logger.warning(f"No se pudo eliminar respaldo antiguo {filepath}: {e}")

    return eliminados


def ejecutar_backup_servidor(es_automatico=True, dias_retencion=15):
    """
    Ejecuta el respaldo de base de datos y lo guarda en el disco del servidor.
    Actualiza la bitácora y la configuración del sistema.
    """
    directorio = obtener_directorio_backups()
    tipo = "auto" if es_automatico else "manual"
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_ferdel_{tipo}_{timestamp_str}.sql"
    filepath = os.path.join(directorio, filename)

    logger.info(f"Iniciando respaldo de base de datos ({tipo}): {filename}")
    sql_content = generar_script_sql()

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(sql_content)

    tamano_bytes = os.path.getsize(filepath)
    tamano_mb = round(tamano_bytes / (1024 * 1024), 2)

    # Registrar en bitácora y en config_sistema
    accion = f"{'BACKUP_AUTOMATICO_24H' if es_automatico else 'BACKUP_MANUAL_SERVIDOR'}: {filename} ({tamano_mb} MB)"
    try:
        registrar_bitacora(modulo="RESPALDO", accion=accion)
    except Exception as e:
        logger.warning(f"No se pudo registrar bitácora para backup: {e}")

    try:
        ahora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO config_sistema (llave, valor, descripcion)
                VALUES ('ultimo_backup_automatico', %s, 'Fecha y hora del último respaldo generado en el servidor')
                ON DUPLICATE KEY UPDATE valor = %s
            """, (ahora_iso, ahora_iso))
    except Exception as e:
        logger.warning(f"No se pudo actualizar 'ultimo_backup_automatico' en config_sistema: {e}")

    # Rotar backups antiguos
    try:
        rotar_backups_antiguos(dias_retencion=dias_retencion)
    except Exception as e:
        logger.warning(f"Error al rotar respaldos antiguos: {e}")

    logger.info(f"Respaldo generado exitosamente: {filepath} ({tamano_mb} MB)")
    return {
        'success': True,
        'filename': filename,
        'filepath': filepath,
        'size_mb': tamano_mb,
        'fecha': datetime.now()
    }


def listar_backups_servidor():
    """
    Retorna la lista de archivos de respaldo existentes en la carpeta del servidor,
    ordenados cronológicamente de más reciente a más antiguo.
    """
    directorio = obtener_directorio_backups()
    patron = os.path.join(directorio, "backup_ferdel_*.sql")
    archivos = glob.glob(patron)
    archivos.sort(key=os.path.getmtime, reverse=True)

    lista = []
    for filepath in archivos:
        try:
            nombre = os.path.basename(filepath)
            tamano_bytes = os.path.getsize(filepath)
            mtime = os.path.getmtime(filepath)
            fecha_dt = datetime.fromtimestamp(mtime)

            es_auto = "_auto_" in nombre
            lista.append({
                'filename': nombre,
                'path': filepath,
                'size_bytes': tamano_bytes,
                'size_kb': round(tamano_bytes / 1024, 1),
                'size_mb': round(tamano_bytes / (1024 * 1024), 2),
                'fecha': fecha_dt,
                'fecha_str': fecha_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'tipo': 'Automático' if es_auto else 'Manual'
            })
        except Exception as e:
            logger.warning(f"Error al leer información de {filepath}: {e}")

    return lista


def eliminar_backup_servidor(filename):
    """
    Elimina con seguridad un archivo de respaldo del servidor.
    Previene ataques de path traversal.
    """
    nombre_limpio = os.path.basename(filename)
    if not nombre_limpio.endswith('.sql') or not nombre_limpio.startswith('backup_ferdel_'):
        raise ValueError("Nombre de archivo inválido")

    directorio = obtener_directorio_backups()
    filepath = os.path.join(directorio, nombre_limpio)

    if os.path.exists(filepath):
        os.remove(filepath)
        try:
            registrar_bitacora(modulo="RESPALDO", accion=f"ELIMINAR_BACKUP: {nombre_limpio}")
        except Exception:
            pass
        return True
    return False


# ===== SCHEDULER EN SEGUNDO PLANO (CADA 24 HORAS) =====
_scheduler_iniciado = False
_scheduler_lock = threading.Lock()


def _bucle_scheduler():
    """
    Hilo daemon que supervisa periódicamente si corresponde realizar
    el respaldo cada 24 horas.
    """
    logger.info("🕒 Scheduler de respaldo automático de base de datos iniciado (intervalo de chequeo: 30m, frecuencia: cada 24h).")
    
    # Esperar 60 segundos tras el arranque inicial antes del primer chequeo
    time.sleep(60)

    while True:
        try:
            # Consultar configuración de la base de datos
            with get_db_cursor() as cursor:
                cursor.execute("""
                    SELECT llave, valor FROM config_sistema 
                    WHERE llave IN ('ultimo_backup_automatico', 'backup_auto_habilitado', 'backup_auto_dias_retencion')
                """)
                rows = cursor.fetchall()
                config = {r['llave']: r['valor'] for r in rows}

            habilitado = config.get('backup_auto_habilitado', '1') == '1'
            if habilitado:
                ultimo_backup_str = config.get('ultimo_backup_automatico', '').strip()
                dias_retencion = int(config.get('backup_auto_dias_retencion', '15') or 15)

                debe_ejecutar = False
                if not ultimo_backup_str:
                    debe_ejecutar = True
                else:
                    try:
                        ultimo_dt = datetime.strptime(ultimo_backup_str, "%Y-%m-%d %H:%M:%S")
                        # Si ya pasaron 24 horas (86400 segundos) desde el último respaldo
                        segundos_transcurridos = (datetime.now() - ultimo_dt).total_seconds()
                        if segundos_transcurridos >= 86400:
                            debe_ejecutar = True
                    except Exception as pe:
                        logger.warning(f"No se pudo parsear fecha del último backup '{ultimo_backup_str}': {pe}")
                        debe_ejecutar = True

                if debe_ejecutar:
                    logger.info("⏰ Han transcurrido más de 24 horas desde el último respaldo. Ejecutando respaldo automático...")
                    ejecutar_backup_servidor(es_automatico=True, dias_retencion=dias_retencion)
                    logger.info("✅ Respaldo automático completado exitosamente.")

        except Exception as e:
            logger.error(f"❌ Error en el scheduler de respaldo automático: {e}", exc_info=True)

        # Chequear cada 30 minutos (1800 segundos)
        time.sleep(1800)


def iniciar_scheduler_backup(app=None):
    """
    Inicia el hilo en segundo plano para el respaldo diario si aún no está en ejecución.
    """
    global _scheduler_iniciado
    with _scheduler_lock:
        if _scheduler_iniciado:
            return
        _scheduler_iniciado = True

    hilo = threading.Thread(target=_bucle_scheduler, name="FerdelBackupScheduler", daemon=True)
    hilo.start()
