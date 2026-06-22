"""
Configuración de variables de entorno y settings
"""
import os
import time
from dotenv import load_dotenv
from datetime import timedelta

# ===== CONFIGURAR ZONA HORARIA DEL PROCESO (Nicaragua UTC-6) =====
os.environ['TZ'] = 'America/Managua'
if hasattr(time, 'tzset'):
    time.tzset()

load_dotenv()

# ===== VARIABLES DE ENTORNO =====
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
RENDER_ENV = os.environ.get('RENDER', False)

# ===== CONFIGURACIÓN SIMPLIFICADA DE BASE DE DATOS (SIN SSL) =====
DB_CONFIG = {
    'user': os.environ.get('DB_USER', 'avnadmin'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'host': os.environ.get('DB_HOST', 'mysql-ferdel-pruebadoce46-eadc.c.aivencloud.com'),
    'port': int(os.environ.get('DB_PORT', 28375)),
    'database': os.environ.get('DB_NAME', 'db_ferdel'),
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