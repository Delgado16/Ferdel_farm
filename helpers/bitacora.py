"""
Sistema de bitácora y auditoría
"""
import functools
from functools import wraps
from flask import request
from flask_login import current_user
from config.database import get_db_cursor


def obtener_ip_cliente():
    """
    Obtiene la IP real del cliente, considerando proxies inversos (como Railway, Render, Nginx, etc.)
    """
    try:
        # Intentar obtener de X-Forwarded-For (común en Railway/Render/Nginx)
        if request.headers.getlist("X-Forwarded-For"):
            # Tomar la primera dirección de la lista
            ip = request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
            if ip:
                return ip
        # Intentar obtener de X-Real-IP
        ip_real = request.headers.get("X-Real-IP")
        if ip_real:
            return ip_real.strip()
    except Exception:
        # Silenciar si no estamos en un contexto de request activo
        pass
    
    # Caer en remote_addr
    try:
        return request.remote_addr or '0.0.0.0'
    except Exception:
        return '0.0.0.0'


def registrar_bitacora(id_usuario=None, modulo=None, accion=None, ip_acceso=None):
    """
    Registrar en bitácora - IP se obtiene automáticamente si no se especifica o es genérica
    """
    if ip_acceso is None or ip_acceso in ('0.0.0.0', '127.0.0.1'):
        ip_acceso = obtener_ip_cliente()
        
    try:
        with get_db_cursor(commit=True) as cursor:
            # Si no se proporciona usuario, usar el current_user
            if id_usuario is None and current_user.is_authenticated:
                id_usuario = current_user.id
            
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, modulo, accion, ip_acceso))
            
            print(f"📝 Bitácora registrada: {modulo} - {accion} | IP: {ip_acceso}")
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
                        accion=func.__name__
                    )
            except Exception as e:
                print(f"Error en decorador bitácora: {e}")
            
            return result
        return wrapper
    return decorator


def registrar_login_exitoso(username, id_usuario):
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH",
        accion="LOGIN_EXITOSO"
    )


def registrar_login_fallido(username, razon):
    """
    Registrar un intento fallido de login
    
    Args:
        username (str): Nombre de usuario
        razon (str): Razón del fallo
    """
    registrar_bitacora(
        id_usuario=None,
        modulo="AUTH",
        accion=f"LOGIN_FALLIDO: {razon} - Usuario: {username}"
    )


def registrar_logout(id_usuario):
    """
    Registrar un logout en bitácora
    
    Args:
        id_usuario (int): ID del usuario
    """
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH", 
        accion="LOGOUT"
    )