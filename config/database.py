"""
Configuración específica de base de datos
"""
import os
import sys

# Configurar encoding a UTF-8 para evitar errores de codificación con emojis en Windows
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import warnings
import collections.abc
import time
import threading
import logging
from mysql.connector import Error, pooling
import mysql.connector
import contextlib
from flask import g, has_app_context

# ===== INICIO - MODIFICACIONES PARA PYTHON 3.13 Y RENDER =====
# Solución para Python 3.13
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

# Suprimir warnings de deprecación
warnings.filterwarnings('ignore', category=DeprecationWarning)
# ===== FIN DE MODIFICACIONES =====

from .settings import DB_CONFIG, RENDER_ENV, RAILWAY_ENV

logger = logging.getLogger(__name__)

# Variables globales para el pool
connection_pool = None
pool_lock = threading.Lock()


def init_pool():
    """Inicializar el pool con reintentos automáticos"""
    global connection_pool
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with pool_lock:
                connection_pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
            print("✅ Conexión a la base de datos establecida correctamente.")
            crear_tablas_sistema()
            return True
        except Error as e:
            print(f"❌ Intento {attempt + 1} fallado: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Espera exponencial
    return False


def crear_tablas_sistema():
    """Crear tablas de configuración del sistema si no existen (optimizado para arranque rápido)"""
    try:
        conn = _obtener_nueva_conexion()
        cursor = conn.cursor(dictionary=True)
        
        # Crear tabla config_sistema si no existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_sistema (
                llave VARCHAR(100) PRIMARY KEY,
                valor TEXT,
                descripcion VARCHAR(255),
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
        """)
        
        # Verificar si ya existen configuraciones para evitar 12 consultas innecesarias en cada arranque de worker
        cursor.execute("SELECT COUNT(*) AS total FROM config_sistema")
        conteo = cursor.fetchone()
        
        if not conteo or conteo['total'] == 0:
            valores_defecto = [
                ("empresa_nombre", "FERDEL", "Nombre de la empresa para reportes y comprobantes"),
                ("empresa_ruc", "J0310000000000", "RUC/Identificación fiscal de la empresa"),
                ("empresa_direccion", "Managua, Nicaragua", "Dirección física de la empresa"),
                ("empresa_telefono", "+505 8888-8888", "Teléfono de contacto general"),
                ("iva_porcentaje", "15.0", "Porcentaje de impuesto al valor agregado (IVA)"),
                ("smtp_host", "smtp.gmail.com", "Servidor de correo SMTP"),
                ("smtp_port", "587", "Puerto del servidor SMTP (587 para TLS)"),
                ("smtp_user", "", "Usuario/Correo del servidor SMTP"),
                ("smtp_password", "", "Contraseña de aplicación o del servidor SMTP"),
                ("ultimo_backup_automatico", "", "Fecha y hora del último respaldo generado en el servidor"),
                ("backup_auto_habilitado", "1", "Habilitar respaldo automático diario cada 24 horas (1=Sí, 0=No)"),
                ("backup_auto_dias_retencion", "15", "Días de retención para copias de seguridad automáticas")
            ]
            for llave, valor, desc in valores_defecto:
                cursor.execute("""
                    INSERT IGNORE INTO config_sistema (llave, valor, descripcion) 
                    VALUES (%s, %s, %s)
                """, (llave, valor, desc))
            
        # Asegurar existencia y SQL SECURITY INVOKER de la vista pagos_cxc requerida por el módulo de facturación
        try:
            cursor.execute("""
                CREATE OR REPLACE SQL SECURITY INVOKER VIEW pagos_cxc AS
                SELECT 
                    pc.ID_Pago,
                    pc.ID_Movimiento,
                    cxc.ID_Factura,
                    cxc.ID_Cliente,
                    pc.Fecha AS Fecha_Pago,
                    pc.Fecha,
                    pc.Monto,
                    COALESCE(mp.Nombre, 'Efectivo') AS Metodo_Pago,
                    pc.ID_MetodoPago,
                    pc.Comentarios,
                    pc.Detalles_Metodo,
                    pc.ID_Usuario_Creacion
                FROM pagos_cuentascobrar pc
                INNER JOIN cuentas_por_cobrar cxc ON pc.ID_Movimiento = cxc.ID_Movimiento
                LEFT JOIN metodos_pago mp ON pc.ID_MetodoPago = mp.ID_MetodoPago;
            """)
        except Exception as e_view:
            print(f"⚠️ Nota al verificar vista pagos_cxc: {e_view}")

        # Reparar automáticamente cualquier vista en la BD que tenga DEFINER inexistente (ej. 'root'@'%' -> Error 1449)
        try:
            cursor.execute("""
                SELECT TABLE_NAME, VIEW_DEFINITION
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND SECURITY_TYPE = 'DEFINER'
            """)
            vistas_definer = cursor.fetchall() or []
            for v_info in vistas_definer:
                v_name = v_info.get('TABLE_NAME')
                v_def = v_info.get('VIEW_DEFINITION')
                if v_name and v_def:
                    try:
                        cursor.execute(f"SELECT 1 FROM `{v_name}` LIMIT 1")
                        cursor.fetchall()
                    except Exception as err_v:
                        if '1449' in str(err_v):
                            try:
                                cursor.execute(f"CREATE OR REPLACE SQL SECURITY INVOKER VIEW `{v_name}` AS {v_def}")
                                print(f"✅ Vista `{v_name}` reparada automáticamente con SQL SECURITY INVOKER.")
                            except Exception as err_fix:
                                print(f"⚠️ No se pudo reparar automáticamente la vista `{v_name}`: {err_fix}")
        except Exception as e_views_check:
            print(f"⚠️ Nota al verificar definers de vistas: {e_views_check}")

        conn.commit()
        cursor.close()
        conn.close()
        print("⚙️ Tablas de sistema y vistas verificadas correctamente.")
    except Exception as e:
        print(f"⚠️ Error al inicializar tablas de sistema: {e}")



def _obtener_nueva_conexion():
    """Crea una conexión desde el pool o conexión directa y ajusta zona horaria"""
    conn = None
    if connection_pool:
        try:
            conn = connection_pool.get_connection()
        except Exception:
            conn = None

    if conn is None:
        config_simple = {k: v for k, v in DB_CONFIG.items() 
                       if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
        conn = mysql.connector.connect(**config_simple)

    try:
        cur = conn.cursor()
        cur.execute("SET time_zone = '-06:00'")
        cur.close()
    except Exception:
        pass
    return conn


def get_db():
    """Obtener conexión de la base de datos con manejo de errores dentro o fuera de Flask"""
    if has_app_context():
        if 'db' not in g:
            g.db = _obtener_nueva_conexion()
        return g.db
    else:
        return _obtener_nueva_conexion()


def close_db(exception=None):
    """Cerrar conexión al final de cada request"""
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            try:
                if db.is_connected():
                    db.close()
            except Exception as e:
                print(f"❌ Error al cerrar conexión: {e}")


@contextlib.contextmanager
def get_db_cursor(commit=True):
    """Context manager para manejar cursor automáticamente tanto en Flask como en segundo plano"""
    en_app_context = has_app_context()
    db = get_db()
    if db is None:
        raise Exception("No se pudo conectar a la base de datos")
    
    cursor = None
    try:
        try:
            db.ping(reconnect=True, attempts=2, delay=0)
        except Exception:
            if not db.is_connected():
                db.reconnect(attempts=2, delay=0)
    
        cursor = db.cursor(dictionary=True)
        yield cursor
        
        if commit:
            db.commit()

    except Exception as e:
        if commit:
            try:
                db.rollback()
            except Exception:
                pass
        raise e

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if not en_app_context and db:
            try:
                db.close()
            except Exception:
                pass


def test_connection():
    """Probar la conexión a la base de datos"""
    try:
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            print("✅ Conexión a BD exitosa")
            return True
        else:
            print("❌ No se pudo establecer conexión a la BD")
            return False
    except Error as e:
        print(f"❌ Error al probar conexión a la BD: {e}")
        return False


def diagnose_db():
    """Diagnóstico completo de la base de datos"""
    print("\n=== DIAGNÓSTICO DE BASE DE DATOS ===")
    
    # Verificar variables de entorno
    print(f"📋 Variables de entorno:")
    print(f"   DB_USER: {os.environ.get('DB_USER')}")
    print(f"   DB_NAME: {os.environ.get('DB_NAME')}")
    print(f"   DB_HOST: {os.environ.get('DB_HOST')}")
    print(f"   DB_SSL_DISABLED: {os.environ.get('DB_SSL_DISABLED')}")
    print(f"   DB_SSL_CA: {os.environ.get('DB_SSL_CA')}")
    print(f"   RENDER: {RENDER_ENV}")
    print(f"   RAILWAY: {RAILWAY_ENV}")
    
    # 1. Verificar conexión
    conn = get_db()
    if not conn:
        print("❌ No se pudo conectar a la BD")
        return False
    
    try:
        # Crear cursor con dictionary=True para obtener resultados como diccionarios
        cursor = conn.cursor(buffered=True, dictionary=True)
        
        # 2. Verificar base de datos
        cursor.execute("SELECT DATABASE() as current_db")
        current_db = cursor.fetchone()['current_db']
        print(f"📊 Base de datos actual: {current_db}")
        
        # 3. Verificar tablas
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables] if tables else []
        print(f"📊 Tablas encontradas: {table_names}")
        
        # 4. Verificar tabla usuarios específicamente
        if 'usuarios' in table_names:
            cursor.execute("DESCRIBE usuarios")
            columns = cursor.fetchall()
            print("📋 Estructura de tabla usuarios:")
            for col in columns:
                print(f"   - {col['Field']}: {col['Type']}")
                
            # 5. Verificar datos en usuarios
            cursor.execute("SELECT COUNT(*) as count FROM usuarios")
            count_result = cursor.fetchone()
            user_count = count_result['count'] if count_result else 0
            print(f"👥 usuarios en sistema: {user_count}")
            
            # 6. Mostrar algunos usuarios de ejemplo
            if user_count > 0:
                cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM usuarios LIMIT 5")
                sample_users = cursor.fetchall()
                print("👤 Ejemplo de usuarios:")
                for user in sample_users:
                    print(f"   - {user['ID_Usuario']}: {user['NombreUsuario']} ({user['Estado']})")
                    print(f"     Contraseña: {user['Contraseña'][:20]}...")  # Mostrar solo parte
        else:
            print("❌ Tabla 'usuarios' no encontrada")
        
        # 7. Verificar tabla roles
        if 'roles' in table_names:
            cursor.execute("SELECT * FROM roles")
            roles = cursor.fetchall()
            print("🎭 roles disponibles:")
            for role in roles:
                print(f"   - {role['ID_Rol']}: {role['Nombre_Rol']}")
        
        cursor.close()
        return True
        
    except Error as e:
        print(f"❌ Error en diagnóstico: {e}")
        return False
    finally:
        if conn:
            conn.close()