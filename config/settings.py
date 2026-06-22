"""
Configuración de variables de entorno y settings
"""
import os
import time
from dotenv import load_dotenv
from datetime import timedelta
import urllib.parse

# ===== CONFIGURAR ZONA HORARIA DEL PROCESO (Nicaragua UTC-6) =====
os.environ['TZ'] = 'America/Managua'
if hasattr(time, 'tzset'):
    time.tzset()

load_dotenv()

# ===== VARIABLES DE ENTORNO =====
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
RENDER_ENV = os.environ.get('RENDER', False)
RAILWAY_ENV = os.environ.get('RAILWAY_STATIC_URL', None) is not None

# ===== CONFIGURACIÓN DE BASE DE DATOS (SOPORTA MYSQL_URL Y VARIABLES INDIVIDUALES) =====
# Parsear MYSQL_URL si está presente (inyectada por Railway y útil para desarrollo local)
mysql_url_str = os.environ.get('MYSQL_URL')
if mysql_url_str:
    try:
        url = urllib.parse.urlparse(mysql_url_str)
        DB_USER_DEFAULT = url.username or 'root'
        DB_PASSWORD_DEFAULT = url.password or 'admin'
        DB_HOST_DEFAULT = url.hostname or 'localhost'
        DB_PORT_DEFAULT = url.port or 3306
        DB_NAME_DEFAULT = url.path.lstrip('/') or 'db_ferdel'
    except Exception:
        DB_USER_DEFAULT = 'root'
        DB_PASSWORD_DEFAULT = 'admin'
        DB_HOST_DEFAULT = 'localhost'
        DB_PORT_DEFAULT = 3306
        DB_NAME_DEFAULT = 'db_ferdel'
else:
    DB_USER_DEFAULT = os.environ.get('MYSQLUSER', 'root')
    DB_PASSWORD_DEFAULT = os.environ.get('MYSQLPASSWORD', 'admin')
    DB_HOST_DEFAULT = os.environ.get('MYSQLHOST', 'localhost')
    DB_PORT_DEFAULT = int(os.environ.get('MYSQLPORT', 3306))
    DB_NAME_DEFAULT = os.environ.get('MYSQLDATABASE', 'db_ferdel')

DB_CONFIG = {
    'user': os.environ.get('DB_USER', DB_USER_DEFAULT),
    'password': os.environ.get('DB_PASSWORD', DB_PASSWORD_DEFAULT),
    'host': os.environ.get('DB_HOST', DB_HOST_DEFAULT),
    'port': int(os.environ.get('DB_PORT', DB_PORT_DEFAULT)),
    'database': os.environ.get('DB_NAME', DB_NAME_DEFAULT),
    'pool_name': 'ferdel_pool',
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 3)),
    'pool_reset_session': True,
    'autocommit': True,
    'connect_timeout': 30,
    'use_pure': True,
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci'
}

# ===== CONFIGURACIÓN DE SESIÓN =====
SESSION_CONFIG = {
    'PERMANENT': False,
    'TYPE': 'filesystem',
    'PERMANENT_LIFETIME': timedelta(hours=12),
    'TEMPLATES_AUTO_RELOAD': True,
}

# ===== CONFIGURACIÓN DE CORS =====
CORS_CONFIG = {
    'CORS_HEADERS': 'Content-Type'
}

def print_db_config():
    """Imprimir configuración de BD (sin mostrar contraseña)"""
    print("📋 Configuración de BD (SIN SSL):")
    print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database: {DB_CONFIG['database']}")
    print(f"   User: {DB_CONFIG['user']}")
    print(f"   Pool Size: {DB_CONFIG['pool_size']}")