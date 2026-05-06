"""
Sistema de bitácora y auditoría
"""
import functools
from functools import wraps
from flask import request
from flask_login import current_user
from config.database import get_db_cursor


def registrar_bitacora(id_usuario=None, modulo=None, accion=None, ip_acceso='0.0.0.0'):
    """
    Registrar en bitácora - IP ahora es obligatoria con valor por defecto
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Si no se proporciona usuario, usar el current_user
            if id_usuario is None and current_user.is_authenticated:
                id_usuario = current_user.id
            
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, modulo, accion, ip_acceso))
            
            print(f"📝 Bitácora registrada: {modulo} - {accion}")
            return True
            
    except Exception as e:
        print(f"❌ Error al registrar en bitácora: {e}")
        return False


def bitacora_decorator(modulo):
    """
    Decorador para automatizar el registro en bitácora
    
    Uso:
        @bitacora_decorator('PRODUCTO')
        def crear_producto():
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Ejecutar la función primero
            result = func(*args, **kwargs)
            
            # Registrar en bitácora después de la ejecución exitosa
            try:
                if current_user.is_authenticated:
                    registrar_bitacora(
                        modulo=modulo,
                        accion=func.__name__,
                        ip_acceso=request.remote_addr
                    )
            except Exception as e:
                print(f"Error en decorador bitácora: {e}")
            
            return result
        return wrapper
    return decorator


def registrar_login_exitoso(username, id_usuario):
    from flask import request
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH",
        accion="LOGIN_EXITOSO",
        ip_acceso=request.remote_addr
    )


def registrar_login_fallido(username, razon):
    """
    Registrar un intento fallido de login
    
    Args:
        username (str): Nombre de usuario
        razon (str): Razón del fallo
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO bitacora (Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s)
            """, ("AUTH", f"LOGIN_FALLIDO: {razon} - Usuario: {username}", request.remote_addr))
    except Exception as e:
        print(f"Error al registrar login fallido: {e}")


def registrar_logout(id_usuario):
    """
    Registrar un logout en bitácora
    
    Args:
        id_usuario (int): ID del usuario
    """
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH", 
        accion="LOGOUT",
        ip_acceso=request.remote_addr
    )