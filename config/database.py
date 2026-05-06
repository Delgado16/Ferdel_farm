"""
Configuración específica de base de datos
"""
import os
import sys
import warnings
import collections.abc
import time
import threading
import logging
from mysql.connector import Error, pooling
import mysql.connector
import contextlib
from flask import g

# ===== INICIO - MODIFICACIONES PARA PYTHON 3.13 Y RENDER =====
# Solución para Python 3.13
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable

# Suprimir warnings de deprecación
warnings.filterwarnings('ignore', category=DeprecationWarning)
# ===== FIN DE MODIFICACIONES =====

from .settings import DB_CONFIG, RENDER_ENV

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
            return True
        except Error as e:
            print(f"❌ Intento {attempt + 1} fallado: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Espera exponencial
    return False


def get_db():
    """Obtener conexión de la base de datos con manejo de errores"""
    if 'db' not in g:
        try:
            if connection_pool:
                g.db = connection_pool.get_connection()
            else:
                # Fallback a conexión simple si el pool falla
                config_simple = {k: v for k, v in DB_CONFIG.items() 
                               if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            print("✅ Conexión a BD establecida")
            
        except pooling.PoolError as e:
            print(f"⚠️ Pool agotado, usando conexión directa: {e}")
            try:
                config_simple = {k: v for k, v in DB_CONFIG.items()
                                if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            except Error as fallback_error:
                print(f"❌ Fallback también falló: {fallback_error}")
                g.db = None
        except Error as e:
            print(f"❌ Error al conectar a la BD: {e}")
            g.db = None
    return g.db


def close_db(exception=None):
    """Cerrar conexión al final de cada request"""
    db = g.pop('db', None)
    if db is not None:
        try:
            if db.is_connected():
                db.close()
                print("🔒 Conexión a BD cerrada")
            else:
                print("ℹ️ Conexión ya estaba cerrada")
        except Error as e:
            print(f"❌ Error al cerrar conexión: {e}")


@contextlib.contextmanager
def get_db_cursor(commit=False):
    """Context manager para manejar cursor automáticamente"""
    db = get_db()
    if db is None:
        raise Exception("No se pudo conectar a la base de datos")
    
    cursor = None
    try:
        if not db.is_connected():
            print("🔄 Reconectando...")
            db.reconnect(attempts=1, delay=0)
    
        cursor = db.cursor(dictionary=True)
        yield cursor
        
        if commit:
            db.commit()
            print("✅ Cambios confirmados en la BD")

    except Exception as e:
        print(f"❌ Error en operación de BD: {e}")
        if commit:
            try:
                db.rollback()
                print("🔄 Rollback realizado en la BD")
            except:
                print("❌ Error al hacer rollback")
        raise e

    finally:
        if cursor:
            try:
                cursor.close()
                print("🔒 Cursor cerrado")
            except:
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
    print(f"   RENDER: {RENDER_ENV}")
    
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