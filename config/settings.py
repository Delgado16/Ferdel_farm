"""
Configuración de variables de entorno y settings
"""
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

# ===== VARIABLES DE ENTORNO =====
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
RENDER_ENV = os.environ.get('RENDER', False)

# ===== CONFIGURACIÓN DE BASE DE DATOS =====
DB_CONFIG = {
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'admin'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'database': os.environ.get('DB_NAME', 'db_ferdel'),
    'pool_name': 'ferdel_pool',
    'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
    'pool_reset_session': True,
    'autocommit': True,
    'connect_timeout': 30
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