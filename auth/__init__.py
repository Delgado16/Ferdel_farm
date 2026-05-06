"""
Módulo de autenticación y autorización
"""
from flask_login import UserMixin
from .models import User
from .decorators import (
    role_requerido,
    admin_required,
    bodega_required,
    vendedor_required,
    admin_or_bodega_required
)
from .utils import (
    verify_credentials_debug,
    load_user,
    setup_login_manager
)

__all__ = [
    'User',
    'role_requerido',
    'admin_required',
    'bodega_required',
    'vendedor_required',
    'admin_or_bodega_required',
    'verify_credentials_debug',
    'load_user',
    'setup_login_manager'
]