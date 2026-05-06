"""
Decoradores para control de acceso y autenticación
"""
from functools import wraps
from flask import abort
from flask_login import login_required, current_user


def role_requerido(requested_role):
    """
    Decorador para requerir un rol específico
    
    Uso:
        @role_requerido('Administrador')
        def admin_page():
            pass
    """
    def decorator(f):
        @login_required
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.rol != requested_role:
                abort(403)  # Forbidden
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Decorador para requerir rol de Administrador"""
    return role_requerido('Administrador')(f)


def bodega_required(f):
    """Decorador para requerir rol de Bodega"""
    return role_requerido('Bodega')(f)


def vendedor_required(f):
    """Decorador para requerir rol de Vendedor"""
    return role_requerido('Vendedor')(f)


def admin_or_bodega_required(f):
    """Decorador para requerir rol de Administrador o Bodega"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)  # No autenticado
        if current_user.rol not in ['Administrador', 'Bodega']:
            abort(403)  # No autorizado
        return f(*args, **kwargs)
    return decorated_function