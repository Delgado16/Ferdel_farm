"""
Configuración de variables de entorno y settings
"""
import os
import time
from dotenv import load_dotenv
from datetime import timedelta
import urllib.parse

# ===== CONFIGURAR PARCHE DE ZONA HORARIA GLOBAL (Nicaragua UTC-6) =====
import datetime
if not hasattr(datetime, '__patched__'):
    from zoneinfo import ZoneInfo
    _original_datetime = datetime.datetime
    _original_date = datetime.date

    class SafeDatetime(_original_datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                try:
                    dt = _original_datetime.now(ZoneInfo('America/Managua')).replace(tzinfo=None)
                except Exception:
                    dt = _original_datetime.now()
            else:
                dt = _original_datetime.now(tz)
            return cls(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)
        
        @classmethod
        def utcnow(cls):
            try:
                dt = _original_datetime.now(ZoneInfo('UTC')).replace(tzinfo=None)
            except Exception:
                dt = _original_datetime.utcnow()
            return cls(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond, dt.tzinfo)

    class SafeDate(_original_date):
        @classmethod
        def today(cls):
            try:
                dt = _original_datetime.now(ZoneInfo('America/Managua'))
                return cls(dt.year, dt.month, dt.day)
            except Exception:
                d = _original_date.today()
                return cls(d.year, d.month, d.day)

    datetime.datetime = SafeDatetime
    datetime.date = SafeDate
    datetime.__patched__ = True

# También configurar a nivel de sistema operativo
os.environ['TZ'] = 'America/Managua'
if hasattr(time, 'tzset'):
    time.tzset()

# Cargar .env asegurando la ruta absoluta del proyecto (independiente del directorio de ejecución)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ENV_FILE = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE, override=True)
else:
    load_dotenv(override=True)

# ===== VARIABLES DE ENTORNO =====
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
RENDER_ENV = os.environ.get('RENDER', False)
RAILWAY_ENV = any(os.environ.get(k) is not None for k in [
    'RAILWAY_STATIC_URL', 'RAILWAY_ENVIRONMENT', 'RAILWAY_PROJECT_ID', 'RAILWAY_SERVICE_ID'
])

DB_SSL_DISABLED = os.environ.get('DB_SSL_DISABLED', 'True') == 'True' 
DB_SSL_CA = os.environ.get('DB_SSL_CA', None)

# ===== DETECCIÓN AUTOMÁTICA DE BASE DE DATOS (Railway / Render / Local) =====
# En Railway, preferir siempre la red interna privada (MYSQL_PRIVATE_URL) para latencia sub-milisegundo (<1ms)
_db_url = os.environ.get('MYSQL_PRIVATE_URL') or os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
_parsed_url = urllib.parse.urlparse(_db_url) if (_db_url and _db_url.startswith('mysql')) else None

_default_user = _parsed_url.username if _parsed_url else (os.environ.get('MYSQLUSER') or os.environ.get('DB_USER') or 'root')
_default_pwd = _parsed_url.password if _parsed_url else (os.environ.get('MYSQLPASSWORD') or os.environ.get('DB_PASSWORD') or 'admin')
_default_host = _parsed_url.hostname if _parsed_url else (
    os.environ.get('MYSQL_PRIVATE_HOST') or 
    os.environ.get('RAILWAY_PRIVATE_DOMAIN') or 
    os.environ.get('MYSQLHOST') or 
    os.environ.get('MYSQL_HOST') or 
    '127.0.0.1'
)
_default_port = _parsed_url.port if (_parsed_url and _parsed_url.port) else int(
    os.environ.get('MYSQLPORT') or 3306
)
_default_db = _parsed_url.path.lstrip('/') if _parsed_url else (os.environ.get('MYSQLDATABASE') or 'db_ferdel')

DB_CONFIG = {
    'user': os.environ.get('DB_USER', _default_user),
    'password': os.environ.get('DB_PASSWORD', _default_pwd),
    'host': os.environ.get('DB_HOST', _default_host),
    'port': int(os.environ.get('DB_PORT', _default_port)),
    'database': os.environ.get('DB_NAME', _default_db),
    'pool_name': 'ferdel_pool',
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
    'pool_reset_session': True,
    'autocommit': os.environ.get('DB_AUTOCOMMIT', 'False') == 'True',
    'connect_timeout': 15,
    'use_pure': os.environ.get('DB_USE_PURE', 'True') == 'True',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_general_ci',
    'ssl_disabled': DB_SSL_DISABLED
}

if DB_SSL_CA:
    DB_CONFIG['ssl_ca'] = DB_SSL_CA


# ===== CONFIGURACIÓN DE SESIÓN =====
SESSION_CONFIG = {
    'PERMANENT': False,
    'TYPE': os.environ.get('SESSION_TYPE', None),
    'PERMANENT_LIFETIME': timedelta(hours=12),
    'TEMPLATES_AUTO_RELOAD': DEBUG,
}

# ===== CONFIGURACIÓN DE CORS =====
CORS_CONFIG = {
    'CORS_HEADERS': 'Content-Type'
}

def print_db_config():
    """Imprimir configuración de BD (sin mostrar contraseña)"""
    ssl_status = "DESHABILITADO" if DB_CONFIG.get('ssl_disabled', True) else "HABILITADO"
    print(f"📋 Configuración de BD (SSL: {ssl_status}):")
    print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database: {DB_CONFIG['database']}")
    print(f"   User: {DB_CONFIG['user']}")
    print(f"   Pool Size: {DB_CONFIG['pool_size']}")