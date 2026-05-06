"""
Módulo de rutas y blueprints
"""
from .auth import auth_bp
from .main import main_bp
from .admin import admin_bp
from .vendedor import vendedor_bp
from .bodega import bodega_bp

__all__ = ['auth_bp', 'main_bp', 'admin_bp', 'vendedor_bp', 'bodega_bp']
