"""
Utilidades de autenticación
"""
import time
import threading
from werkzeug.security import check_password_hash
from flask import g, has_app_context
from flask_login import LoginManager
from config.database import get_db_cursor
from .models import User

# Cache en memoria con TTL de 5 minutos para evitar saturación de BD por Flask-Login
_USER_CACHE = {}
_USER_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 300


def invalidate_user_cache(user_id=None):
    """Invalida el usuario en caché cuando cambie su rol, contraseña o estado"""
    with _USER_CACHE_LOCK:
        if user_id is not None:
            _USER_CACHE.pop(str(user_id), None)
        else:
            _USER_CACHE.clear()


def verify_credentials_debug(username, password):
    """
    Función de debug para verificar credenciales con logs detallados
    
    Args:
        username (str): Nombre de usuario
        password (str): Contraseña
    
    Returns:
        bool: True si las credenciales son válidas, False en caso contrario
    """
    print(f"\n🔍 DEBUG: Verificando credenciales para usuario: '{username}'")
    
    try:
        with get_db_cursor() as cursor:
            # Consulta case-insensitive para estado
            query = """
                SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol, u.Estado
                FROM usuarios u 
                JOIN roles r ON u.ID_Rol = r.ID_Rol 
                WHERE u.NombreUsuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """
            print(f"📝 Ejecutando query: {query}")
            print(f"📝 Parámetros: ({username},)")
            
            cursor.execute(query, (username,))
            user_data = cursor.fetchone()
            
            if user_data:
                print(f"✅ Usuario encontrado en BD:")
                print(f"   ID: {user_data['ID_Usuario']}")
                print(f"   Nombre: {user_data['NombreUsuario']}")
                print(f"   Rol: {user_data['Nombre_Rol']}")
                print(f"   Estado: {user_data['Estado']}")
                print(f"   Hash contraseña: {user_data['Contraseña'][:20]}...")
                
                # Verificar contraseña hasheada
                password_match = check_password_hash(user_data['Contraseña'], password)
                print(f"🔐 Contraseña coincide (hash): {password_match}")
                
                if password_match:
                    print("✅ Credenciales válidas")
                    return True
                else:
                    print("❌ Contraseña incorrecta")
                    return False
            else:
                print("❌ Usuario no encontrado en la base de datos")
                return False
                
    except Exception as e:
        print(f"❌ Error en verify_credentials_debug: {e}")
        return False


def load_user(user_id):
    """
    Cargar un usuario de la BD para Flask-Login con caché de solicitud y TTL
    
    Args:
        user_id (str): ID del usuario
    
    Returns:
        User: Objeto User si existe, None en caso contrario
    """
    if not user_id:
        return None

    str_uid = str(user_id)

    # 1. Caché a nivel de request (g)
    if has_app_context():
        cached_user = getattr(g, f'_current_user_{str_uid}', None)
        if cached_user is not None:
            return cached_user

    # 2. Caché en memoria con TTL
    ahora = time.monotonic()
    with _USER_CACHE_LOCK:
        if str_uid in _USER_CACHE:
            user_inst, expira = _USER_CACHE[str_uid]
            if ahora < expira:
                if has_app_context():
                    setattr(g, f'_current_user_{str_uid}', user_inst)
                return user_inst

    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute(""" 
                SELECT u.ID_Usuario, u.NombreUsuario, r.Nombre_Rol
                FROM usuarios u
                JOIN roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """, (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                user_obj = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                with _USER_CACHE_LOCK:
                    _USER_CACHE[str_uid] = (user_obj, ahora + _CACHE_TTL_SECONDS)
                if has_app_context():
                    setattr(g, f'_current_user_{str_uid}', user_obj)
                return user_obj
            return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        # Respaldo de seguridad: si la BD tuvo un fallo transitorio de reconexión tras inactividad,
        # pero el usuario ya estaba validado en caché, preservamos la sesión en lugar de expulsarlo.
        with _USER_CACHE_LOCK:
            if str_uid in _USER_CACHE:
                user_obj, _ = _USER_CACHE[str_uid]
                _USER_CACHE[str_uid] = (user_obj, ahora + 60)
                if has_app_context():
                    setattr(g, f'_current_user_{str_uid}', user_obj)
                return user_obj
        return None


def setup_login_manager(app):
    """
    Configurar Flask-Login para la aplicación
    
    Args:
        app (Flask): Instancia de la aplicación Flask
    
    Returns:
        LoginManager: Instancia configurada de LoginManager
    """
    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Inicia sesión para acceder a esta página"
    login_manager.login_message_category = "info"
    
    @login_manager.user_loader
    def user_loader(user_id):
        return load_user(user_id)
    
    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, jsonify, redirect, url_for, flash
        accept = request.headers.get('Accept', '')
        if request.path.startswith('/api/') or \
           request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
           ('application/json' in accept and 'text/html' not in accept):
            return jsonify({
                'status': 'error',
                'message': 'Sesión expirada. Por favor, inicie sesión nuevamente.',
                'redirect': url_for('auth.login')
            }), 401
        
        flash("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.", "warning")
        return redirect(url_for('auth.login'))
    
    return login_manager