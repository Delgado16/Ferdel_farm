"""
Módulo de configuración de la aplicación
Exporta configuraciones y funciones de base de datos
"""

# Exportar configuraciones desde settings
from .settings import (
    DEBUG,
    SECRET_KEY,
    RENDER_ENV,
    DB_CONFIG,
    SESSION_CONFIG,
    CORS_CONFIG,
    print_db_config
)

# Exportar funciones de base de datos desde database
from .database import (
    init_pool,
    get_db,
    close_db,
    get_db_cursor,
    test_connection,
    diagnose_db
)

# Definir qué se exporta cuando se usa "from config import *"
__all__ = [
    # Configuraciones
    'DEBUG',
    'SECRET_KEY',
    'RENDER_ENV',
    'DB_CONFIG',
    'SESSION_CONFIG',
    'CORS_CONFIG',
    'print_db_config',
    
    # Base de datos
    'init_pool',
    'get_db',
    'close_db',
    'get_db_cursor',
    'test_connection',
    'diagnose_db'
]