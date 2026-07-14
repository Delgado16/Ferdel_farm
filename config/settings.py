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


load_dotenv(override=True)

# ===== VARIABLES DE ENTORNO =====
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
RENDER_ENV = os.environ.get('RENDER', False)
RAILWAY_ENV = os.environ.get('RAILWAY_STATIC_URL', None) is not None

DB_SSL_DISABLED = os.environ.get('DB_SSL_DISABLED', 'True') == 'True'
DB_SSL_CA = os.environ.get('DB_SSL_CA', None)

DB_CONFIG = {
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'host': os.environ.get('DB_HOST', 'reseau.proxy.rlwy.net'),
    'port': int(os.environ.get('DB_PORT', 41024)),
    'database': os.environ.get('DB_NAME', 'db_ferdel'),
    'pool_name': 'ferdel_pool',
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 5)),
    'pool_reset_session': True,
    'autocommit': os.environ.get('DB_AUTOCOMMIT', 'False') == 'True',
    'connect_timeout': 30,
    'use_pure': True,
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
    'TEMPLATES_AUTO_RELOAD': True,
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