from flask import Flask, flash, render_template, redirect, url_for, abort, request, session, Response, jsonify, current_app, g
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from weasyprint import HTML
from datetime import datetime, timedelta
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from mysql.connector import Error, pooling
from markupsafe import Markup
import mysql.connector
import functools
from functools import wraps
from datetime import datetime, time
import time
import threading
import traceback
import json
from decimal import Decimal
import logging
import os
import secrets
from dotenv import load_dotenv
import contextlib

load_dotenv()
app = Flask(__name__)
# Configuración de la base de datos
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

# Inicializar connection_pool
connection_pool = None
pool_lock = threading.Lock()

def init_pool():
    """Inicializar el pool con reintentos automaticos"""
    global connection_pool
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with pool_lock:
                connection_pool = mysql.connector.pooling.MySQLConnectionPool(**DB_CONFIG)
            print("Conexión a la base de datos establecida correctamente.")
            return True
        except Error as e:
            print(f"Intentos {attempt + 1} fallados: {e}")
            if attempt < max_retries - 1:
                time.sleep(2*(attempt + 1))  # Espera exponencial
    return False

#inicializar al inicio
init_pool()

def get_db():
    """Obtener conexión de la base de datos con manejo de errores"""
    if 'db' not in g:
        try:
            if connection_pool:
                g.db = connection_pool.get_connection()
            else:
                # Fallback a conexión simple si el pool falla
                config_simple = {k: v for k, v in DB_CONFIG.items() 
                               if k not in ['pool_name', 'pool_size','pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            print("Conexión a BD establecida")
            
        except pooling.PoolError as e:
            print(f"Pool agotado, usando conexion directa: {e}")
            try:
                config_simple = {k: v for k, v in DB_CONFIG.items()
                                if k not in ['pool_name','pool_size','pool_reset_session']}
                g.db = mysql.connector.connect(**config_simple)
            except Error as fallback_error:
                print(f"Fallback tambien fallo: {fallback_error}")
                g.db = None
        except Error as e:
            print(f"Error al conectar a la BD: {e}")
            g.db = None
    return g.db

@app.teardown_appcontext
def close_db(exception):
    """Cerrar conexión al final de cada request"""
    db = g.pop('db', None)
    if db is not None:
        try:
            if db.is_connected():
                db.close()
                print("Conexión a BD cerrada")
            else:
                print("Conexion ya estaba cerrada")
        except Error as e:
            print(f"Error al cerrar conexión: {e}")

@contextlib.contextmanager
def get_db_cursor(commit=False):
    """Context manager para manejar cursor automáticamente"""
    db = get_db()
    if db is None:
        raise Exception("No se pudo conectar a la base de datos")
    
    cursor = None
    try:
        if not db.is_connected():
            print("Reconectando...")
            db.reconnect(attempts=1, delay=0)
    
        cursor = db.cursor(dictionary=True)
        yield cursor
        
        if commit:
            db.commit()
            print("Cambios confirmados en la BD")

    except Exception as e:
        print(f"Error en operacion de BD: {e}")
        if commit:
            try:
                db.rollback()
                print("Rollback realizado en la BD")
            except:
                print("Error al hacer rollback")
        raise e

    finally:
        if cursor:
            try:
                cursor.close()
                print("Cursor cerrado")
            except:
                pass

def test_connection():
    """Probar la conexión a la base de datos"""
    try:
        conn = get_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            print("✅ Conexión a BD exitosa")
            return True
        else:
            print("❌ No se pudo establecer conexión a la BD")
            return False
    except Error as e:
        print(f"❌ Error al probar conexión a la BD: {e}")
        return False

def diagnose_db():
    """Diagnóstico completo de la base de datos"""
    print("\n=== DIAGNÓSTICO DE BASE DE DATOS ===")
    
    # Verificar variables de entorno
    print(f"📋 Variables de entorno:")
    print(f"   DB_USER: {os.environ.get('DB_USER')}")
    print(f"   DB_NAME: {os.environ.get('DB_NAME')}")
    print(f"   DB_HOST: {os.environ.get('DB_HOST')}")
    
    # 1. Verificar conexión
    conn = get_db()
    if not conn:
        print("❌ No se pudo conectar a la BD")
        return False
    
    try:
        # Crear cursor con dictionary=True para obtener resultados como diccionarios
        cursor = conn.cursor(buffered=True, dictionary=True)
        
        # 2. Verificar base de datos
        cursor.execute("SELECT DATABASE() as current_db")
        current_db = cursor.fetchone()['current_db']
        print(f"📊 Base de datos actual: {current_db}")
        
        # 3. Verificar tablas
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables] if tables else []
        print(f"📊 Tablas encontradas: {table_names}")
        
        # 4. Verificar tabla usuarios específicamente
        if 'usuarios' in table_names:
            cursor.execute("DESCRIBE usuarios")
            columns = cursor.fetchall()
            print("📋 Estructura de tabla usuarios:")
            for col in columns:
                print(f"   - {col['Field']}: {col['Type']}")
                
            # 5. Verificar datos en usuarios
            cursor.execute("SELECT COUNT(*) as count FROM usuarios")
            count_result = cursor.fetchone()
            user_count = count_result['count'] if count_result else 0
            print(f"👥 Usuarios en sistema: {user_count}")
            
            # 6. Mostrar algunos usuarios de ejemplo
            if user_count > 0:
                cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM usuarios LIMIT 5")
                sample_users = cursor.fetchall()
                print("👤 Ejemplo de usuarios:")
                for user in sample_users:
                    print(f"   - {user['ID_Usuario']}: {user['NombreUsuario']} ({user['Estado']})")
                    print(f"     Contraseña: {user['Contraseña']}")
        
        # 7. Verificar tabla Roles
        if 'Roles' in table_names:
            cursor.execute("SELECT * FROM Roles")
            roles = cursor.fetchall()
            print("🎭 Roles disponibles:")
            for role in roles:
                print(f"   - {role['ID_Rol']}: {role['Nombre_Rol']}")
        
        else:
            print("❌ Tabla 'usuarios' no encontrada")
            
        cursor.close()
        return True
        
    except Error as e:
        print(f"❌ Error en diagnóstico: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_credentials_debug(username, password):
    """Función de debug para verificar credenciales con logs detallados"""
    print(f"\n🔍 DEBUG: Verificando credenciales para usuario: '{username}'")
    
    try:
        with get_db_cursor() as cursor:
            # Consulta case-insensitive para estado
            query = """
                SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol, u.Estado
                FROM Usuarios u 
                JOIN Roles r ON u.ID_Rol = r.ID_Rol 
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
                print(f"   Hash contraseña: {user_data['Contraseña']}")
                
                # Verificar si la contraseña está hasheada
                is_hashed = user_data['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))
                print(f"   ¿Contraseña hasheada?: {is_hashed}")
                
                if is_hashed:
                    # Verificar contraseña hasheada
                    password_match = check_password_hash(user_data['Contraseña'], password)
                    print(f"🔐 Contraseña coincide (hash): {password_match}")
                else:
                    # Verificar contraseña en texto plano (temporal)
                    password_match = (user_data['Contraseña'] == password)
                    print(f"🔐 Contraseña coincide (texto plano): {password_match}")
                    print("⚠️  ADVERTENCIA: Contraseña en texto plano - debe ser hasheada")
                
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

def registrar_bitacora(id_usuario=None, modulo=None, accion=None, ip_acceso=None):
    """
    Función principal para registrar en la bitácora
    """
    try:
        with get_db_cursor(commit=True) as cursor:
            # Si no se proporciona IP, obtenerla del request
            if ip_acceso is None and request:
                ip_acceso = request.remote_addr
            
            # Si no se proporciona usuario, usar el current_user
            if id_usuario is None and current_user.is_authenticated:
                id_usuario = current_user.id
            
            cursor.execute("""
                INSERT INTO bitacora (ID_Usuario, Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s, %s)
            """, (id_usuario, modulo, accion, ip_acceso))
            
            print(f"Bitácora registrada: {modulo} - {accion} - Usuario: {id_usuario}")
            return True
            
    except Exception as e:
        print(f"Error al registrar en bitácora: {e}")
        return False

def bitacora_decorator(modulo):
    """
    Decorador para automatizar el registro en bitácora
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
    """Registrar login exitoso en bitácora"""
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH",
        accion="LOGIN_EXITOSO",
        ip_acceso=request.remote_addr
    )
    
def registrar_login_fallido(username, razon):
    """Registrar intento fallido de login"""
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO bitacora (Modulo, Accion, IP_Acceso)
                VALUES (%s, %s, %s)
            """, ("AUTH", f"LOGIN_FALLIDO: {razon} - Usuario: {username}", request.remote_addr))
    except Exception as e:
        print(f"Error al registrar login fallido: {e}")

def registrar_logout(id_usuario):
    """Registrar logout en bitácora"""
    registrar_bitacora(
        id_usuario=id_usuario,
        modulo="AUTH", 
        accion="LOGOUT",
        ip_acceso=request.remote_addr
    )

# Configuración de Flask (FUERA del bloque try-except)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(24))
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)
Session(app)

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Inicia sesión para acceder a esta página"
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, id, username, rol):
        self.id = str(id)
        self.username = username
        self.rol = rol

@login_manager.user_loader
def load_user(user_id):
    try:
        with get_db_cursor() as cursor:
            cursor.execute(""" 
                SELECT u.ID_Usuario, u.NombreUsuario, r.Nombre_Rol
                FROM Usuarios u
                JOIN Roles r ON u.ID_Rol = r.ID_Rol
                WHERE u.ID_Usuario = %s AND UPPER(u.Estado) = 'ACTIVO'
            """, (user_id,))
            user_data = cursor.fetchone()
            
            if user_data:
                return User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
            return None
    except Exception as e:
        print(f"Error en load_user: {e}")
        return None

# Decorador Personalizado
def role_requerido(requested_role):
    def decorator(f):
        @login_required
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.rol != requested_role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_requerido('Administrador')(f)

# Rutas de autenticaciones y autorizaciones
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    session.clear()
    
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        print(f"\n Intento de login - Usuario: '{username}', Contraseña: '{password}'")
        
        if not username:
            flash("El nombre de usuario es requerido", "danger")
            registrar_login_fallido(username,"Usuario vacio")
            return render_template('login.html')
        
        if not password:
            flash("La contraseña es requerida", "danger")
            registrar_login_fallido(username, "Contraseña vacia")
            return render_template('login.html')
        
        if len(password) < 4:
            flash("La contraseña debe tener al menos 4 caracteres", "danger")
            return render_template('login.html')
        
        # Debug: verificar credenciales con logging detallado
        credentials_valid = verify_credentials_debug(username, password)
        
        try:
            with get_db_cursor() as cursor:
                # Consulta case-insensitive para estado
                cursor.execute("""
                    SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol 
                    FROM Usuarios u 
                    JOIN Roles r ON u.ID_Rol = r.ID_Rol 
                    WHERE u.NombreUsuario = %s AND UPPER(u.Estado) = 'ACTIVO'
                """, (username,))
                
                user_data = cursor.fetchone()
                
                if user_data:
                    # Verificar si la contraseña está hasheada
                    if user_data['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:')):
                        # Contraseña hasheada
                        if check_password_hash(user_data['Contraseña'], password):
                            user = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                            login_user(user)
                            registrar_login_exitoso(username, user_data['ID_Usuario'])
                            print(f"Usuario {username} ha iniciado sesión - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('dashboard'))
                        else:
                            print("Contraseña incorrecta (hash)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                    else:
                        # Contraseña en texto plano (temporal)
                        if user_data['Contraseña'] == password:
                            user = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                            login_user(user)
                            registrar_login_exitoso(username, user_data['ID_Usuario'])
                            print(f"Usuario {username} ha iniciado sesión (texto plano) - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('dashboard'))
                        else:
                            print("Contraseña incorrecta (texto plano)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                else:
                    print("Usuario no encontrado o inactivo")
                    registrar_login_fallido(username, "contraseña no encontrado o inactivo")
                    flash("Credenciales incorrectas o usuario inactivo.", "danger")
                
        except Exception as e:
            print(f"Error en login: {e}")
            registrar_login_fallido(username, f"Error del sistema: {e}")
            flash("Error interno del sistema. Intente más tarde.", "danger")
        
        return render_template('login.html')

    return render_template('login.html')

@app.route('/reset-admin')
def reset_admin():
    """Reset completo del usuario admin"""
    try:
        with get_db_cursor() as cursor:
            # Resetear a texto plano temporalmente
            cursor.execute("""
                UPDATE Usuarios 
                SET Estado = 'Activo', 
                    Contraseña = 'Admin123$'
                WHERE ID_Usuario = 2
            """)
            
            print("✅ Admin reseteado a texto plano")
            print("   Usuario: Admin")
            print("   Contraseña: Admin123$ (texto plano)")
            
        return """
        <h1>✅ Admin reseteado</h1>
        <p>Ahora prueba iniciar sesión con:</p>
        <ul>
            <li><strong>Usuario:</strong> Admin</li>
            <li><strong>Contraseña:</strong> Admin123$</li>
        </ul>
        <p><a href="/login">Ir al login</a></p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

# RUTAS TEMPORALES PARA FIX - ELIMINAR DESPUÉS DE USAR
@app.route('/fix-admin')
def fix_admin():
    """Ruta temporal para corregir el usuario admin - ELIMINAR DESPUÉS"""
    try:
        with get_db_cursor() as cursor:
            # 1. Corregir estado (case-insensitive)
            cursor.execute("UPDATE Usuarios SET Estado = 'Activo' WHERE ID_Usuario = 2")
            
            # 2. Crear hash válido para la contraseña
            hashed_password = generate_password_hash('Admin123$')
            cursor.execute("UPDATE Usuarios SET Contraseña = %s WHERE ID_Usuario = 2", (hashed_password,))
            
            print("✅ Usuario admin corregido:")
            print(f"   - Estado: Activo")
            print(f"   - Contraseña hash: {hashed_password}")
            print("   - Credenciales: usuario='Admin', contraseña='Admin123$'")
            
        return """
        <h1>✅ Usuario admin corregido</h1>
        <p>Ahora puedes iniciar sesión con:</p>
        <ul>
            <li><strong>Usuario:</strong> Admin</li>
            <li><strong>Contraseña:</strong> Admin123$</li>
        </ul>
        <p><a href="/login">Ir al login</a></p>
        <p style='color: red; font-weight: bold;'>⚠️ RECUERDA ELIMINAR ESTA RUTA /fix-admin DESPUÉS DE USAR</p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@app.route('/check-users')
def check_users():
    """Ruta temporal para ver todos los usuarios - ELIMINAR DESPUÉS"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM Usuarios")
            users = cursor.fetchall()
            
            result = "<h1>👥 Usuarios en el sistema</h1>"
            for user in users:
                result += f"""
                <div style='border: 1px solid #ccc; padding: 10px; margin: 10px;'>
                    <strong>ID:</strong> {user['ID_Usuario']}<br>
                    <strong>Usuario:</strong> {user['NombreUsuario']}<br>
                    <strong>Estado:</strong> {user['Estado']}<br>
                    <strong>Contraseña:</strong> {user['Contraseña']}<br>
                    <strong>¿Hasheada?:</strong> {user['Contraseña'].startswith(('scrypt:', 'pbkdf2:', 'bcrypt:'))}
                </div>
                """
            
            return result + "<p><a href='/login'>Ir al login</a></p>"
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@app.route('/diagnostico', methods=["GET"])
def diagnostico():
    """Página de diagnóstico para verificar el estado de la BD"""
    result = diagnose_db()
    return f"""
    <h1>Diagnóstico de Base de Datos</h1>
    <p>Resultado: {'✅ Éxito' if result else '❌ Fallo'}</p>
    <p>Ver logs detallados en la consola del servidor.</p>
    <p><a href="/login">Ir al login</a> | <a href="/fix-admin">Corregir admin</a> | <a href="/check-users">Ver usuarios</a></p>
    """

@app.route('/logout')
@login_required
def logout():
    registrar_logout(current_user.id)
    logout_user()
    flash("Sesion cerrada exitosamente", "info")
    return redirect(url_for('login'))

# Rutas principales
@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.rol == 'Administrador':
        return render_template('admin/dashboard.html')
    elif current_user.rol == 'Vendedor':
        return render_template('vendedor/dashboard.html')
    elif current_user.rol == 'Jefe Galera':
        return render_template('jefe_galera/dashboard.html')
    else:
        abort(403)

# Dashboard por roles
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM Usuarios WHERE UPPER(Estado) = 'ACTIVO'")
            usuarios_count = cursor.fetchone()['count']
            
            return render_template('admin/dashboard.html', usuarios_count=usuarios_count)
    except Exception as e:
        flash(f"Error al cargar dashboard: {e}", "danger")
        return redirect(url_for('dashboard'))

@app.route('/vendedor/dashboard')
@login_required
def vendedor_dashboard():
    return render_template('vendedor/dashboard.html')

@app.route('/jefe_galera/dashboard')
@login_required
def jefe_galera_dashboard():
    return render_template('jefe_galera/dashboard.html')

## MODULOS DEL ADMINISTRADOR
# CATALOGOS USUARIOS
@app.route('/admin/usuarios')
@admin_required
@bitacora_decorator("USUARIOS")
def admin_usuarios():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa FROM Usuarios u
                JOIN Roles r ON u.ID_Rol = r.ID_Rol
                JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
            """)
            usuarios = cursor.fetchall()
            
            cursor.execute("SELECT * FROM Roles")
            roles = cursor.fetchall()
            
            cursor.execute("SELECT * FROM Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/usuarios.html', usuarios=usuarios, roles=roles, empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar usuarios: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/crear-usuario', methods=['POST'])
@admin_required
@bitacora_decorator("USUARIOS")
def crear_usuario():
    username = request.form.get('username')
    password = request.form.get('password')
    rol_id = request.form.get('rol_id')
    empresa_id = request.form.get('empresa_id')

    if not all([username, password, rol_id, empresa_id]):
        flash("Todos los campos son requeridos", "danger")
        return redirect(url_for('admin_usuarios'))

    hashed_password = generate_password_hash(password)
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO Usuarios (NombreUsuario, Contraseña, ID_Rol, ID_Empresa, Estado)
                VALUES (%s, %s, %s, %s, 'Activo')
            """, (username, hashed_password, rol_id, empresa_id))
            registrar_bitacora(modulo="USUARIOS", accion=f"CREAR_USUARUI: {username}")
            flash("Usuario creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear usuario: {e}", "danger")
    
    return redirect(url_for('admin_usuarios'))

@app.route('/admin/catalog/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def editar_usuario(user_id):
    try:
        with get_db_cursor() as cursor:
            if request.method == 'GET':
                # Obtener datos del usuario a editar
                cursor.execute("""
                    SELECT u.*, r.Nombre_Rol as Rol, e.Nombre_Empresa 
                    FROM Usuarios u
                    JOIN Roles r ON u.ID_Rol = r.ID_Rol
                    JOIN Empresa e ON u.ID_Empresa = e.ID_Empresa
                    WHERE u.ID_Usuario = %s
                """, (user_id,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    flash("Usuario no encontrado", "danger")
                    return redirect(url_for('admin_usuarios'))
                
                # Obtener roles y empresas para el formulario
                cursor.execute("SELECT * FROM Roles")
                roles = cursor.fetchall()
                
                cursor.execute("SELECT * FROM Empresa")
                empresas = cursor.fetchall()
                
                return render_template('admin/catalog/editar_usuario.html', 
                                     usuario=usuario, 
                                     roles=roles, 
                                     empresas=empresas)
            
            elif request.method == 'POST':
                # Procesar el formulario de edición
                username = request.form.get('username')
                rol_id = request.form.get('rol_id')
                empresa_id = request.form.get('empresa_id')
                estado = request.form.get('estado')
                password = request.form.get('password')
                
                if not all([username, rol_id, empresa_id, estado]):
                    flash("Todos los campos son requeridos", "danger")
                    return redirect(url_for('editar_usuario', user_id=user_id))
                
                # Construir la consulta dinámicamente
                update_fields = []
                update_values = []
                
                update_fields.append("NombreUsuario = %s")
                update_values.append(username)
                
                update_fields.append("ID_Rol = %s")
                update_values.append(rol_id)
                
                update_fields.append("ID_Empresa = %s")
                update_values.append(empresa_id)
                
                update_fields.append("Estado = %s")
                update_values.append(estado)
                
                # Si se proporcionó una nueva contraseña, actualizarla
                if password:
                    hashed_password = generate_password_hash(password)
                    update_fields.append("Contraseña = %s")
                    update_values.append(hashed_password)
                
                # Agregar el ID al final de los valores
                update_values.append(user_id)
                
                # Ejecutar la actualización
                query = f"UPDATE Usuarios SET {', '.join(update_fields)} WHERE ID_Usuario = %s"
                cursor.execute(query, update_values)
                
                flash("Usuario actualizado exitosamente", "success")
                return redirect(url_for('admin_usuarios'))
                
    except Exception as e:
        flash(f"Error al editar usuario: {e}", "danger")
        return redirect(url_for('admin_usuarios'))

# CATALOGO BITACORA
@app.route('/admin/bitacora')
@admin_required
def admin_bitacora():
    """Vista principal de la bitácora del sistema"""
    try:
        modulo = request.args.get('modulo')
        fecha_desde = request.args.get('fecha_desde')
        fecha_hasta = request.args.get('fecha_hasta')
        
        with get_db_cursor() as cursor:
            # Construir query con filtros
            query = """
                SELECT b.*, u.NombreUsuario 
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                WHERE 1=1
            """
            params = []
            
            if modulo:
                query += " AND b.Modulo = %s"
                params.append(modulo)
                
            if fecha_desde:
                query += " AND DATE(b.Fecha) >= %s"
                params.append(fecha_desde)
                
            if fecha_hasta:
                query += " AND DATE(b.Fecha) <= %s"
                params.append(fecha_hasta)
            
            query += " ORDER BY b.Fecha DESC LIMIT 200"
            
            cursor.execute(query, params)
            registros = cursor.fetchall()
            
            # Obtener módulos únicos para el dropdown
            cursor.execute("SELECT DISTINCT Modulo FROM bitacora WHERE Modulo IS NOT NULL ORDER BY Modulo")
            modulos = cursor.fetchall()
            
            return render_template('admin/bitacora.html', 
                                 registros=registros, 
                                 modulos=modulos)
            
    except Exception as e:
        flash(f"Error al cargar bitácora: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/bitacora/limpiar', methods=['POST'])
@admin_required
def limpiar_bitacora():
    """Limpiar registros antiguos de la bitácora"""
    try:
        with get_db_cursor(commit=True) as cursor:
            # Mantener solo los últimos 1000 registros
            cursor.execute("""
                DELETE FROM bitacora 
                WHERE ID_Bitacora NOT IN (
                    SELECT ID_Bitacora FROM (
                        SELECT ID_Bitacora FROM bitacora 
                        ORDER BY Fecha DESC 
                        LIMIT 1000
                    ) AS temp
                )
            """)
            
            registros_eliminados = cursor.rowcount
            registrar_bitacora(modulo="BITACORA", accion=f"LIMPIAR_BITACORA: {registros_eliminados} registros eliminados")
            
            flash(f"Bitácora limpiada exitosamente. Se eliminaron {registros_eliminados} registros antiguos.", "success")
            
    except Exception as e:
        flash(f"Error al limpiar bitácora: {e}", "danger")
    
    return redirect(url_for('admin_bitacora'))

@app.route('/admin/bitacora/exportar')
@admin_required
def exportar_bitacora():
    """Exportar bitácora a CSV"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT b.Fecha, u.NombreUsuario, b.Modulo, b.Accion, b.IP_Acceso
                FROM bitacora b 
                LEFT JOIN usuarios u ON b.ID_Usuario = u.ID_Usuario 
                ORDER BY b.Fecha DESC
            """)
            registros = cursor.fetchall()
            
            # Crear respuesta CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Fecha', 'Usuario', 'Módulo', 'Acción', 'IP'])
            
            for registro in registros:
                writer.writerow([
                    registro['Fecha'].strftime('%Y-%m-%d %H:%M:%S'),
                    registro['NombreUsuario'] or 'Sistema',
                    registro['Modulo'] or 'N/A',
                    registro['Accion'] or 'N/A',
                    registro['IP_Acceso'] or 'N/A'
                ])
            
            # Registrar exportación
            registrar_bitacora(modulo="BITACORA", accion="EXPORTAR_BITACORA_CSV")
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=bitacora_sistema.csv"
            response.headers["Content-type"] = "text/csv"
            return response
            
    except Exception as e:
        flash(f"Error al exportar bitácora: {e}", "danger")
        return redirect(url_for('admin_bitacora'))

#CATALOGO EMPRESA
@app.route('/admin/catalog/empresa/empresas', methods=['GET'])
@admin_required
@bitacora_decorator("EMPRESA")
def admin_empresas():
    """Listar todas las empresas"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM Empresa 
                ORDER BY Nombre_Empresa
            """)
            empresas = cursor.fetchall()
            
            return render_template('admin/catalog/empresa/empresas.html', empresas=empresas)
    except Exception as e:
        flash(f'Error al cargar empresas: {str(e)}', 'error')
        return render_template('admin/catalog/empresa/empresas.html', empresas=[])

@app.route('/admin/catalog/empresa/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_CREAR")
def crear_empresa():
    """Crear nueva empresa (GET: mostrar modal, POST: procesar formulario)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado', 'Activo')
            
            # Validaciones básicas
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('admin_empresas'))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO empresa (Nombre_Empresa, Direccion, Telefono, RUC, Estado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nombre, direccion, telefono, ruc, estado))
                
            flash('Empresa creada exitosamente', 'success')
            return redirect(url_for('admin_empresas'))
            
        except Exception as e:
            flash(f'Error al crear empresa: {str(e)}', 'error')
            return redirect(url_for('admin_empresas'))
    
    # GET: Redirigir a la página principal (el modal está en empresas.html)
    return redirect(url_for('admin_empresas'))

@app.route('/admin/catalog/empresa/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EMPRESA_EDITAR")
def editar_empresa(id):
    """Editar empresa (GET: mostrar formulario, POST: procesar edición)"""
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre_empresa')
            direccion = request.form.get('direccion')
            telefono = request.form.get('telefono')
            ruc = request.form.get('ruc')
            estado = request.form.get('estado')
            
            if not nombre:
                flash('El nombre de la empresa es obligatorio', 'error')
                return redirect(url_for('editar_empresa', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    UPDATE empresa 
                    SET Nombre_Empresa = %s, Direccion = %s, Telefono = %s, 
                        RUC = %s, Estado = %s
                    WHERE ID_Empresa = %s
                """, (nombre, direccion, telefono, ruc, estado, id))
                
            flash('Empresa actualizada exitosamente', 'success')
            return redirect(url_for('admin_empresas'))
            
        except Exception as e:
            flash(f'Error al actualizar empresa: {str(e)}', 'error')
            return redirect(url_for('editar_empresa', id=id))
    
    # GET: Mostrar formulario de edición
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Empresa, Nombre_Empresa, Direccion, Telefono, Estado, RUC 
                FROM empresa 
                WHERE ID_Empresa = %s
            """, (id,))
            empresa = cursor.fetchone()
            
            if not empresa:
                flash('Empresa no encontrada', 'error')
                return redirect(url_for('admin_empresas'))
                
            return render_template('admin/catalog/empresa/editar_empresa.html', empresa=empresa)
            
    except Exception as e:
        flash(f'Error al cargar empresa: {str(e)}', 'error')
        return redirect(url_for('admin_empresas'))

# CATALOGO CLIENTES
@app.route('/admin/catalog/client/clientes', methods=['GET'])
@admin_required
@bitacora_decorator("CLIENTES")
def admin_clientes():
    # Valores por defecto
    clientes = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base
            base_query = """
                SELECT c.*, e.Nombre_Empresa
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado = 'ACTIVO' AND c.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM Clientes c WHERE c.Estado = 'ACTIVO' AND c.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (c.Nombre LIKE %s OR c.RUC_CEDULA LIKE %s OR c.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY c.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            clientes = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/client/clientes: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los clientes. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/client/clientes.html", 
                        clientes=clientes, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)

@app.route('/admin/catalog/client/crear-cliente', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-CREAR")
def admin_crear_cliente():
    try:
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()
        ruc_cedula = request.form.get("ruc_cedula", "").strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa', 1)

        if not nombre:
            flash("El nombre del cliente es obligatorio.", "danger")
            return redirect(url_for("admin_clientes"))
        
        if not id_usuario:
            flash("Error de autenticación. Por favor, inicie sesión nuevamente.", "danger")
            return redirect(url_for("admin_clientes"))
        
        with get_db_cursor() as cursor:
            # Verificar que la empresa existe y está activa
            cursor.execute(
                "SELECT 1 FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", 
                (id_empresa,)
            )
            empresa_activa = cursor.fetchone()
            
            if not empresa_activa:
                flash("Empresa no válida o inactiva.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM Clientes WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un cliente con este RUC/Cédula", "danger")
                    return redirect(url_for("admin_clientes"))

            # Insertar nuevo cliente
            cursor.execute("""
                INSERT INTO Clientes (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario))
            
            flash("Cliente agregado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al crear cliente: {str(e)}")
        flash("Error al guardar el cliente", "danger")
    
    return redirect(url_for("admin_clientes"))

@app.route('/admin/catalog/client/editar-cliente/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CLIENTES-EDITAR")
def admin_editar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente existe (sin filtrar por estado para poder reactivar)
            cursor.execute(
                """SELECT c.* 
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # MÉTODO GET - Mostrar formulario
            if request.method == 'GET':
                return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)
            
            # MÉTODO POST - Procesar formulario
            elif request.method == 'POST':
                nombre = request.form.get("nombre", "").strip()
                telefono = request.form.get("telefono", "").strip()
                direccion = request.form.get("direccion", "").strip()
                ruc_cedula = request.form.get("ruc_cedula", "").strip()
                estado = request.form.get("estado", "ACTIVO").strip()

                if not nombre:
                    flash("El nombre del cliente es obligatorio.", "danger")
                    # Redirigir de vuelta al formulario de edición
                    return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)

                # Verificar si el RUC/Cédula ya existe en otro cliente activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM Clientes WHERE RUC_CEDULA = %s AND ID_Cliente != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro cliente activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/client/editar_clientes.html", cliente=cliente)

                # Actualizar cliente
                cursor.execute("""
                    UPDATE Clientes 
                    SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s
                    WHERE ID_Cliente = %s AND ID_Empresa = %s
                """, (nombre, telefono, direccion, ruc_cedula, estado, id, id_empresa))
                
                # Registrar en bitácora
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Cliente {accion} correctamente.", "success")
                
                return redirect(url_for("admin_clientes"))
                
    except Exception as e:
        logging.error(f"Error en edición de cliente: {str(e)}")
        flash("Error al procesar la solicitud", "danger")
        return redirect(url_for("admin_clientes"))
    
    # Fallback en caso de que no se cumpla ninguna condición anterior
    return redirect(url_for("admin_clientes"))

@app.route('/admin/catalog/client/eliminar-cliente/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CLIENTES-ELIMINAR")
def admin_eliminar_cliente(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            # Verificar que el cliente pertenece a la empresa actual y está activo
            cursor.execute(
                """SELECT c.* 
                FROM Clientes c
                INNER JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Cliente = %s AND c.ID_Empresa = %s AND c.Estado = 'ACTIVO' AND e.Estado = 'Activo'""",
                (id, id_empresa)
            )
            cliente = cursor.fetchone()
            
            if not cliente:
                flash("Cliente no encontrado.", "danger")
                return redirect(url_for("admin_clientes"))
            
            # Eliminar (cambiar estado a INACTIVO)
            cursor.execute(
                "UPDATE Clientes SET Estado = 'INACTIVO' WHERE ID_Cliente = %s AND ID_Empresa = %s",
                (id, id_empresa)
            )
            
            flash("Cliente eliminado correctamente.", "success")
            
    except Exception as e:
        logging.error(f"Error al eliminar cliente: {str(e)}")
        flash("Error al eliminar el cliente", "danger")
    
    return redirect(url_for("admin_clientes"))

# CATALOGO PROVEEDORES
@app.route('/admin/catalog/proveedor/proveedores', methods=['GET'])
@admin_required
@bitacora_decorator("PROVEEDORES")
def admin_proveedores():
    # Valores por defecto
    proveedores = []
    page = 1
    per_page = 20
    total = 0
    search_query = ""
    
    try:
        page = request.args.get("page", 1, type=int)
        search_query = request.args.get("q", "").strip()
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            offset = (page - 1) * per_page
            
            # Consulta base
            base_query = """
                SELECT p.*, e.Nombre_Empresa
                FROM Proveedores p
                INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s
            """
            params = [id_empresa]
            
            if search_query:
                base_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                search_param = f"%{search_query}%"
                params.extend([search_param, search_param, search_param])
            
            # Contar total
            count_query = "SELECT COUNT(*) as total FROM Proveedores p WHERE p.Estado = 'ACTIVO' AND p.ID_Empresa = %s"
            count_params = [id_empresa]
            
            if search_query:
                count_query += " AND (p.Nombre LIKE %s OR p.RUC_CEDULA LIKE %s OR p.Telefono LIKE %s)"
                count_params.extend([search_param, search_param, search_param])
            
            cursor.execute(count_query, count_params)
            total_result = cursor.fetchone()
            total = total_result['total'] if total_result else 0
            
            # Obtener datos con paginación
            data_query = base_query + " ORDER BY p.Nombre LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            cursor.execute(data_query, params)
            proveedores = cursor.fetchall()
            
    except Exception as e:
        logging.error(f"Error en ruta /admin/catalog/proveedor/proveedores: {str(e)}", exc_info=True)
        flash("Ocurrió un error al cargar los proveedores. Por favor intenta nuevamente.", "danger")
    
    # Siempre retornamos el template, incluso si hay error
    return render_template("admin/catalog/proveedor/proveedores.html", 
                        proveedores=proveedores, 
                        page=page,
                        per_page=per_page,
                        total=total,
                        search=search_query)
    
@app.route('/admin/catalog/proveedor/crear-proveedor', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-CREAR")
def admin_crear_proveedor():
    try:
        nombre = request.form.get('nombre','').strip()
        telefono = request.form.get('telefono','').strip()
        direccion = request.form.get('direccion','').strip()
        ruc_cedula = request.form.get('ruc_cedula','').strip()
        id_usuario = session.get('id_usuario',1)
        id_empresa = session.get('id_empresa',1)
        
        if not nombre:
            flash("El nombre del proveedor es obligatorio","danger")
            return redirect(url_for('admin_proveedores'))
        
        
        with get_db_cursor() as cursor:
            # Verificar si el RUC/Cédula ya existe (solo si se proporcionó)
            if ruc_cedula:
                cursor.execute(
                    "SELECT 1 FROM Proveedores WHERE RUC_CEDULA = %s AND ID_Empresa = %s AND Estado = 'ACTIVO'", 
                    (ruc_cedula, id_empresa)
                )
                existe = cursor.fetchone()
                if existe:
                    flash("Ya existe un proveedor con este RUC/Cédula", "danger")
                    return redirect(url_for("admin_proveedores"))

            # Insertar nuevo proveedor
            cursor.execute("""
                INSERT INTO Proveedores (Nombre, Telefono, Direccion, RUC_CEDULA, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nombre, telefono, direccion, ruc_cedula, id_empresa, id_usuario))
            
            flash("Proveedor agregado correctamente.", "success")
    except Exception as e:
        logging.error(f"Error al crear proveedor: {str(e)}")
        flash("Error al guardar el proveedor", "danger")
    return redirect(url_for('admin_proveedores'))

@app.route('/admin/catalog/proveedor/editar-proveedor/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-EDITAR")
def admin_editar_proveedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            cursor.execute("""
                           SELECT p.* 
                           FROM Proveedores p
                           INNER JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND e.Estado = 'Activo'
                           """, (id, id_empresa))
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado.", "danger")
                return redirect(url_for("admin_proveedores"))
            
            if request.method == 'GET':
                return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                       proveedor=proveedor)
                
            elif request.method == 'POST':
                nombre = request.form.get('nombre','').strip()
                telefono = request.form.get('telefono','').strip()
                direccion = request.form.get('direccion','').strip()
                ruc_cedula = request.form.get('ruc_cedula','').strip()
                estado = request.form.get('estado','ACTIVO').strip()
                
                if not nombre:
                    flash("El nombre del proveedor es obligatorio","danger")
                    return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                           proveedor=proveedor)
                
                # Verificar si el RUC/Cédula ya existe en otro proveedor activo
                if ruc_cedula and estado == 'ACTIVO':
                    cursor.execute(
                        "SELECT 1 FROM Proveedores WHERE RUC_CEDULA = %s AND ID_Proveedor != %s AND ID_Empresa = %s AND Estado = 'ACTIVO'",
                        (ruc_cedula, id, id_empresa)
                    )
                    ruc_existente = cursor.fetchone()
                    if ruc_existente:
                        flash("Ya existe otro proveedor activo con este RUC/Cédula", "danger")
                        return render_template("admin/catalog/proveedor/editar_proveedor.html",
                                               proveedor=proveedor)
                
                # Actualizar proveedor
                cursor.execute("""
                               UPDATE Proveedores 
                               SET Nombre = %s, Telefono = %s, Direccion = %s, RUC_CEDULA = %s, Estado = %s
                               WHERE ID_Proveedor = %s AND ID_Empresa = %s
                               """, (nombre, telefono, direccion, ruc_cedula, estado, id, id_empresa))
                
                accion = "actualizado" if estado == 'ACTIVO' else "desactivado"
                flash(f"Proveedor {accion} correctamente.","success")
                
                return redirect(url_for("admin_proveedores"))
            
    except Exception as e:
        logging.error(f"Error en edición de proveedor: {str(e)}")
        flash("Error al procesar la solicitud","danger")
        return redirect(url_for("admin_proveedores"))

    return redirect(url_for("admin_proveedores"))

@app.route('/admin/catalog/proveedor/eliminar-proveedor/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("PROVEEDORES-ELIMINAR")
def admin_eliminar_probeedor(id):
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor() as cursor:
            #verificar que el proveedor pertenece a la emprsa
            cursor.execute("""
                           SELECT p.*
                           FROM Proveedores p
                           INNER JOIN empresa e On p.ID_Empresa = e.ID_Empresa
                           WHERE p.ID_Proveedor = %s AND p.ID_Empresa = %s AND p.Estado = 'ACTIVO' AND e.Estado = 'Activo'
                           """, (id, id_empresa)
                        )
            
            proveedor = cursor.fetchone()
            
            if not proveedor:
                flash("Proveedor no encontrado","danger")
                return redirect(url_for("admin_proveedores"))

            #Eliminar (cambiar estado a INACTIVO)
            cursor.execute("""
                           UPDATE Proveedores SET Estado = 'INACTIVO' 
                           WHERE ID_Proveedor = %s AND ID_Empresa = %s
                           """, (id, id_empresa)
                           )
            
            flash("Proveedor eliminado correctamente.","success")
    
    except Exception as e:
        logging.error(f"Error al eliminar proveedor: {str(e)}")
        flash("Error al eliminar el proveedor","danger")
    
    return redirect(url_for("admin_proveedores"))

# CATALOGO MEDIDAS
@app.route('/admin/catalog/medidas/unidades-medidas', methods=['GET'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS")
def admin_unidades_medidas():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Unidad, Descripcion, Abreviatura 
                FROM unidades_medida 
                ORDER BY Descripcion DESC
            """)
            unidades = cursor.fetchall()
            return render_template('admin/catalog/medidas/unidades_medidas.html', 
                                 unidades=unidades)
    except Exception as e:
        flash(f"Error al cargar unidades de medida: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/medidas/crear-unidad', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-CREAR")
def admin_crear_unidad_medida():

    if request.method == 'POST':
        descripcion = request.form.get('descripcion','').strip()
        abreviatura = request.form.get('abreviatura','').strip()

        if not descripcion or not abreviatura:
            flash("Descripción y abreviatura son obligatorias.", "danger")
            return redirect(url_for('admin_unidades_medidas'))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute("""
                    INSERT INTO Unidades_Medida (Nombre_Unidad, Abreviatura)
                    VALUES (%s, %s)
                """, (descripcion, abreviatura))
                
                flash("Unidad de medida creada exitosamente.", "success")
                return redirect(url_for('admin_unidades_medidas'))
            
        except Exception as e:
            flash(f"Error al crear unidad de medida: {e}", "danger")
            return redirect(url_for('admin_unidades_medidas'))
    
    return render_template('admin/catalog/medidas/crear_unidad.html')

@app.route('/admin/catalog/medidas/editar-unidad/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("UNIDAD-MEDIDA-EDITAR")
def admin_editar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            
            if request.method == 'POST':

                descripcion = request.form.get('descripcion','').strip()
                abreviatura = request.form.get('abreviatura','').strip()

                if not descripcion or not abreviatura:
                    flash("Descripción y abreviatura son obligatorias.", "danger")
                    return redirect(url_for('admin_unidades_medidas'))
                
                cursor.execute("""
                    UPDATE Unidades_Medida
                    SET Descripcion = %s, Abreviatura = %s
                    WHERE ID_Unidad = %s
                    """, (descripcion, abreviatura, id))
                
                flash("Unidad de medida actualizada exitosamente.", "success")
                return redirect(url_for('admin_unidades_medidas'))
            
            else:

                #obtener datos actuales
                cursor.execute("""
                    SELECT ID_Unidad, Descripcion, Abreviatura
                    FROM Unidades_Medida
                    WHERE ID_Unidad = %s
                    """, (id,))
                
                unidad = cursor.fetchone()

                if not unidad:
                    flash("Unidad de medida no encontrada.", "danger")
                    return redirect(url_for('admin_unidades_medidas'))
                
                return render_template('admin/catalog/medidas/editar_unidad_medida.html',
                                        unidad=unidad)
        
    except Exception as e:
        flash(f"Error al editar unidad de medida: {e}", "danger")
        return redirect(url_for('admin_unidades_medidas'))

@app.route('/admin/catalog/medidas/unidades-medidas/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("UNIDADES-MEDIDAS-ELIMINAR")
def eliminar_unidad_medida(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si la unidad existe
            cursor.execute("SELECT Descripcion FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            unidad = cursor.fetchone()
            
            if not unidad:
                flash("Unidad de medida no encontrada", "danger")
                return redirect(url_for('admin_unidades_medidas'))
            
            cursor.execute("DELETE FROM unidades_medida WHERE ID_Unidad = %s", (id,))
            
            flash(f"Unidad de medida '{unidad['Descripcion']}' eliminada exitosamente", "success")
            
    except Exception as e:
        flash(f"Error al eliminar unidad de medida: {str(e)}", "danger")
    
    return redirect(url_for('admin_unidades_medidas'))

# CATALOGO CATEGORIAS
@app.route('/admin/catalog/categorias/categorias', methods=['GET'])
@admin_required
@bitacora_decorator("CATEGORIAS")
def admin_categorias():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY ID_Categoria DESC
            """)
            categorias = cursor.fetchall()
            return render_template('admin/catalog/categorias/categorias.html', 
                                 categorias=categorias)
    except Exception as e:
        flash(f"Error al cargar categorías: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/categorias/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_CREAR")
def admin_categorias_crear():
    try:
        descripcion = request.form.get('descripcion')
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO categorias_producto (Descripcion) 
                VALUES (%s)
            """, (descripcion,))
            
        flash("Categoría creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

@app.route('/admin/catalog/categorias/editar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_EDITAR")
def admin_categorias_editar(id):
    try:
        descripcion = request.form.get('descripcion')
        
        if not descripcion:
            flash("La descripción es requerida", "danger")
            return redirect(url_for('admin_categorias'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE categorias_producto 
                SET Descripcion = %s 
                WHERE ID_Categoria = %s
            """, (descripcion, id))
            
        flash("Categoría actualizada exitosamente", "success")
    except Exception as e:
        flash(f"Error al actualizar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

@app.route('/admin/catalog/categorias/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("CATEGORIAS_ELIMINAR")
def admin_categorias_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                DELETE FROM categorias_producto 
                WHERE ID_Categoria = %s
            """, (id,))
            
        flash("Categoría eliminada exitosamente", "success")
    except Exception as e:
        flash(f"Error al eliminar categoría: {str(e)}", "danger")
    
    return redirect(url_for('admin_categorias'))

# CATALOGO METODOS DE PAGO
@app.route('/admin/catalog/metodospagos/metodo-pagos', methods=['GET'])
@admin_required
@bitacora_decorator("METODOS-PAGO")
def admin_metodos_pago():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago, Nombre 
                FROM Metodos_Pago 
                ORDER BY ID_MetodoPago DESC
            """)
            metodos = cursor.fetchall()
            return render_template('admin/catalog/metodospagos/metodo_pagos.html', 
                                 metodos=metodos)
    except Exception as e:
        flash(f"Error al cargar métodos de pago: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/catalog/metodospagos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-CREAR")
def admin_metodos_pago_crear():
    try:
        nombre = request.form.get('nombre', '').strip()

        if not nombre:
            flash("El nombre del método de pago es requerido", "danger")
            return redirect(url_for('admin_metodos_pago'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Metodos_Pago (Nombre) 
                VALUES (%s)
            """, (nombre,))

        flash("Método de pago creado exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear método de pago: {str(e)}", "danger")
    return redirect(url_for('admin_metodos_pago'))

@app.route('/admin/catalog/metodospagos/editar/<int:id>', methods=['GET','POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-EDITAR")
def admin_metodos_pago_editar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # GET
            if request.method == 'GET':
                cursor.execute("""
                    SELECT ID_MetodoPago, Nombre
                    FROM Metodos_Pago
                    WHERE ID_MetodoPago = %s 
                               """,(id,))
                
                metodo = cursor.fetchone()

                if not metodo:
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                return render_template('admin/catalog/metodospagos/editar_metodo_pago.html',
                                       metodo=metodo)
            
            #POST
            elif request.method == 'POST':
                nombre = request.form.get('nombre', '').strip()

                if not nombre:
                    flash("El nombre del método de pago es requerido", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                cursor.execute("""
                        SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s   
                        """, (id,))
                
                if not cursor.fetchone():
                    flash("Método de pago no encontrado.", "danger")
                    return redirect(url_for('admin_metodos_pago'))
                
                cursor.execute("""
                    UPDATE Metodos_Pago
                    SET Nombre = %s
                    WHERE ID_MetodoPago = %s
                    """, (nombre, id))
                
                flash("Metodo d epago actualizado exitosamente", "success")
                return redirect(url_for('admin_metodos_pago'))

    except Exception as e:
        flash(f"Error al editar método de pago: {str(e)}", "danger")
        return redirect(url_for('admin_metodos_pago'))

@app.route('/admin/catalog/metodospagos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("METODOS-PAGO-ELIMINAR")
def admin_metodos_pago_eliminar(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT ID_MetodoPago FROM Metodos_Pago WHERE ID_MetodoPago = %s
            """, (id,))

            if not cursor.fetchone():
                flash("Método de pago no encontrado.", "danger")
                return redirect(url_for('admin_metodos_pago'))
            
            cursor.execute("""
                DELETE FROM Metodos_Pago
                WHERE ID_MetodoPago = %s
            """, (id,))

        flash("Metodos de pago eliminado exitosamente", "success")
            
    except Exception as e:
        #Manejar error de integridad referencial
        if "foreing key constraint" in str(e).lower():
            flash("No se puede eliminar el método de pago porque está asociado a otros registros.", "danger")
        else:
            flash(f"Error al eliminar método de pago: {str(e)}", "danger")
    
    return redirect(url_for('admin_metodos_pago'))

#CATALOGO MOVIMINETOS DE INVENTARIO
@app.route('/admin/catalog/movimientos/movimientos-inventario', methods=['GET'])
@admin_required
@bitacora_decorator("MOVIMIENTOS-INVENTARIO")
def admin_movimientos_inventario():
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                SELECT * FROM Catalogo_Movimientos ORDER BY ID_TipoMovimiento""")
            movimientos = cursor.fetchall()
            return render_template('admin/catalog/movimientos/movimientos_inventario.html', 
                                 movimientos=movimientos)
    except Exception as e:
        flash(f"Error al cargar movimientos de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/catalog/movimientos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR-MOVIMIENTO-INVENTARIO")
def admin_crear_movimiento():
    try:
        descripcion = request.form.get('descripcion')
        adicion = request.form.get('adicion')
        letra = request.form.get('letra')
        
        if not descripcion or not letra:
            flash("Descripción y Letra son campos obligatorios", "warning")
            return redirect(url_for('admin_movimientos_inventario'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute(
                "INSERT INTO Catalogo_Movimientos (Descripcion, Adicion, Letra) VALUES (%s, %s, %s)",
                (descripcion, adicion, letra)
            )
            
        flash("Movimiento de inventario creado exitosamente", "success")
        return redirect(url_for('admin_movimientos_inventario'))
        
    except Exception as e:
        flash(f"Error al crear movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_movimientos_inventario'))
            
@app.route('/admin/catalog/movimientos/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR-MOVIMIENTO-INVENTARIO")
def admin_editar_movimiento(id):
    try:
        if request.method == 'POST':
            descripcion = request.form.get('descripcion')
            adicion = request.form.get('adicion')
            letra = request.form.get('letra')
            
            if not descripcion or not letra:
                flash("Descripción y Letra son campos obligatorios", "warning")
                return redirect(url_for('admin_editar_movimiento', id=id))
            
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE Catalogo_Movimientos SET Descripcion = %s, Adicion = %s, Letra = %s WHERE ID_TipoMovimiento = %s",
                    (descripcion, adicion, letra, id)
                )
                
            flash("Movimiento de inventario actualizado exitosamente", "success")
            return redirect(url_for('admin_movimientos_inventario'))
        
        # GET - Cargar datos del movimiento
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin_movimientos_inventario'))
                
        return render_template('admin/catalog/movimientos/editar_movimiento.html', movimiento=movimiento)
        
    except Exception as e:
        flash(f"Error al editar movimiento de inventario: {str(e)}", "danger")
        return redirect(url_for('admin_movimientos_inventario'))

@app.route('/admin/catalog/movimientos/eliminar/<int:id>', methods=['POST'])
@admin_required
@bitacora_decorator("ELIMINAR-MOVIMIENTO-INVENTARIO")
def admin_eliminar_movimiento(id):
    try:
        with get_db_cursor(commit=True) as cursor:
            # Verificar si el movimiento existe
            cursor.execute("SELECT * FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento de inventario no encontrado", "danger")
                return redirect(url_for('admin_movimientos_inventario'))
            
            # Eliminar el movimiento
            cursor.execute("DELETE FROM Catalogo_Movimientos WHERE ID_TipoMovimiento = %s", (id,))
            
        flash("Movimiento de inventario eliminado exitosamente", "success")
        
    except Exception as e:
        flash(f"Error al eliminar movimiento de inventario: {str(e)}", "danger")
    
    return redirect(url_for('admin_movimientos_inventario'))

# MODULO BODEGA
@app.route('/admin/bodega', methods=['GET'])
@admin_required
@bitacora_decorator("BODEGA")
def admin_bodega():
    try:
        with get_db_cursor() as cursor:
            # Obtener bodegas con información de empresa
            cursor.execute("""
                SELECT b.*, e.Nombre_Empresa 
                FROM Bodegas b
                INNER JOIN Empresa e ON b.ID_Empresa = e.ID_Empresa
                ORDER BY b.ID_Bodega DESC
            """)
            bodegas = cursor.fetchall()
            
            # Obtener lista de empresas para el modal de creación
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM Empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/bodega.html', 
                                 bodegas=bodegas,
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodegas: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/bodega/crear', methods=['POST'])
@admin_required
@bitacora_decorator("BODEGA-CREAR")
def admin_bodega_crear():
    try:
        nombre = request.form.get('nombre', '').strip()
        ubicacion = request.form.get('ubicacion', '').strip()
        id_empresa = request.form.get('id_empresa')

        if not nombre:
            flash("El nombre de la bodega es requerido", "danger")
            return redirect(url_for('admin_bodega'))
        
        if not id_empresa:
            flash("La empresa es requerida", "danger")
            return redirect(url_for('admin_bodega'))
        
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO Bodegas (Nombre, Ubicacion, ID_Empresa) 
                VALUES (%s, %s, %s)
            """, (nombre, ubicacion, id_empresa))

        flash("Bodega creada exitosamente", "success")
    except Exception as e:
        flash(f"Error al crear bodega: {str(e)}", "danger")
    return redirect(url_for('admin_bodega'))

@app.route('/admin/bodega/editar/<int:id>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("BODEGA_EDITAR")
def admin_editar_bodega(id):
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        ubicacion = request.form.get('ubicacion')
        id_empresa = request.form.get('id_empresa')
        estado = request.form.get('estado', 'activa')
        
        if not nombre:
            flash("El nombre de la bodega es obligatorio", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
        
        if not id_empresa:
            flash("La empresa es obligatoria", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
        
        try:
            with get_db_cursor(commit=True) as cursor:
                cursor.execute(
                    "UPDATE Bodegas SET Nombre = %s, Ubicacion = %s, Estado = %s, ID_Empresa = %s WHERE ID_Bodega = %s",
                    (nombre, ubicacion, estado, id_empresa, id)
                )
                flash("Bodega actualizada exitosamente", "success")
                return redirect(url_for('admin_bodega'))
        except Exception as e:
            flash(f"Error al actualizar bodega: {str(e)}", "danger")
            return redirect(url_for('admin_editar_bodega', id=id))
    
    # GET - Cargar datos de la bodega y empresas
    try:
        with get_db_cursor() as cursor:
            # Obtener datos de la bodega
            cursor.execute("SELECT * FROM Bodegas WHERE ID_Bodega = %s", (id,))
            bodega = cursor.fetchone()
            
            if not bodega:
                flash("Bodega no encontrada", "danger")
                return redirect(url_for('admin_bodega'))
            
            # Obtener lista de empresas para el dropdown
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM Empresa WHERE Estado = 'Activo' ORDER BY Nombre_Empresa")
            empresas = cursor.fetchall()
            
            return render_template('admin/bodega/editar_bodega.html', 
                                 bodega=bodega, 
                                 empresas=empresas)
    except Exception as e:
        flash(f"Error al cargar bodega: {str(e)}", "danger")
        return redirect(url_for('admin_bodega'))

#CATALOGO PRODUCTOS - BODEGA
@app.route('/admin/bodega/productos', methods=['GET'])
@admin_required
@bitacora_decorator("PRODUCTOS")
def admin_productos():
    try:
        with get_db_cursor() as cursor:
            # Consulta de productos - Sumando existencias de Inventario_Bodega
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion,
                    p.Unidad_Medida,
                    um.Descripcion as Nombre_Unidad,
                    um.Abreviatura,
                    COALESCE(SUM(ib.Existencias), 0) as Existencias,
                    p.Estado,
                    p.ID_Categoria,
                    cp.Descripcion as Nombre_Categoria,
                    p.Precio_Venta,
                    p.ID_Empresa,
                    e.Nombre_Empresa,
                    p.Fecha_Creacion,
                    p.Usuario_Creador,
                    u.NombreUsuario as Usuario_Creador_Nombre,
                    p.Stock_Minimo,
                    (SELECT COUNT(*) FROM Inventario_Bodega ib2 WHERE ib2.ID_Producto = p.ID_Producto) as Bodegas_Con_Stock
                FROM Productos p
                LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto
                -- Cambio en WHERE: 'activo' en lugar de 1
                WHERE p.Estado = 'activo'
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida, 
                         um.Descripcion, um.Abreviatura, p.Estado, p.ID_Categoria,
                         cp.Descripcion, p.Precio_Venta, p.ID_Empresa, e.Nombre_Empresa,
                         p.Fecha_Creacion, p.Usuario_Creador, u.NombreUsuario, p.Stock_Minimo
                ORDER BY p.ID_Producto DESC
            """)
            productos = cursor.fetchall()
            
            # Resto del código sigue igual...
            cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
            categorias = cursor.fetchall()
            
            cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM Unidades_Medida")
            unidades = cursor.fetchall()
            
            cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
            empresas = cursor.fetchall()
            
            cursor.execute("""
                SELECT b.ID_Bodega, b.Nombre, b.ID_Empresa, e.Nombre_Empresa 
                FROM Bodegas b 
                JOIN empresa e ON b.ID_Empresa = e.ID_Empresa 
                WHERE b.Estado = 'activa'
                ORDER BY e.Nombre_Empresa, b.Nombre
            """)
            bodegas = cursor.fetchall()
            
            return render_template('admin/bodega/producto/productos.html', 
                                 productos=productos,
                                 categorias=categorias,
                                 unidades=unidades,
                                 empresas=empresas,
                                 bodegas=bodegas)
    except Exception as e:
        flash(f'Error al cargar productos: {str(e)}', 'error')
        return render_template('admin/bodega/producto/productos.html',
                                productos=[], 
                                categorias=[], 
                                unidades=[], 
                                empresas=[],
                                bodegas=[])
        
@app.route('/admin/bodega/productos/crear', methods=['POST'])
@admin_required
@bitacora_decorator("CREAR_PRODUCTO")
def admin_crear_producto():
    try:
        # Obtener datos del formulario
        cod_producto = request.form.get('COD_Producto')
        descripcion = request.form.get('Descripcion')
        id_unidad_medida = request.form.get('Unidad_Medida')
        id_categoria = request.form.get('ID_Categoria')
        precio_venta = request.form.get('Precio_Venta')
        id_empresa = request.form.get('ID_Empresa', 1)
        stock_minimo = request.form.get('Stock_Minimo', 5)
        cantidad_inicial = request.form.get('Cantidad_Inicial')
        id_bodega = request.form.get('ID_Bodega')
        estado = request.form.get('Estado', 'activo')
        usuario_creador = session.get('id_usuario', 1)

        print(f"DEBUG: Datos recibidos - Descripcion: {descripcion}, Bodega: {id_bodega}, Empresa: {id_empresa}")

        # Validaciones básicas
        if not all([descripcion, id_unidad_medida, id_categoria]):
            flash('Descripción, unidad de medida y categoría son campos obligatorios', 'error')
            return redirect(url_for('admin_productos'))

        if not id_bodega:
            flash('Debe seleccionar una bodega para el inventario inicial', 'error')
            return redirect(url_for('admin_productos'))

        # Validar y convertir valores
        try:
            cantidad_inicial = float(cantidad_inicial) if cantidad_inicial else 0
        except (ValueError, TypeError):
            cantidad_inicial = 0
            
        try:
            precio_venta = float(precio_venta) if precio_venta else 0.0
        except (ValueError, TypeError):
            precio_venta = 0.0
            
        try:
            stock_minimo = float(stock_minimo) if stock_minimo else 5.0
        except (ValueError, TypeError):
            stock_minimo = 5.0

        try:
            id_unidad_medida = int(id_unidad_medida)
        except (ValueError, TypeError):
            flash('Unidad de medida no válida', 'error')
            return redirect(url_for('admin_productos'))
            
        try:
            id_categoria = int(id_categoria)
        except (ValueError, TypeError):
            flash('Categoría no válida', 'error')
            return redirect(url_for('admin_productos'))
            
        try:
            id_empresa = int(id_empresa)
        except (ValueError, TypeError):
            id_empresa = 1
            
        try:
            id_bodega = int(id_bodega)
        except (ValueError, TypeError):
            flash('Bodega no válida', 'error')
            return redirect(url_for('admin_productos'))

        with get_db_cursor(commit=True) as cursor:
            print(f"DEBUG: Verificando bodega ID: {id_bodega}")
            
            # Verificar que la bodega existe y está activa
            cursor.execute("""
                SELECT ID_Bodega, ID_Empresa FROM Bodegas 
                WHERE ID_Bodega = %s AND Estado = 'activa'
            """, (id_bodega,))
            
            bodega_data = cursor.fetchone()
            print(f"DEBUG: Datos bodega obtenidos: {bodega_data}")
            
            if not bodega_data:
                flash('La bodega seleccionada no es válida', 'error')
                return redirect(url_for('admin_productos'))
            
            # Manejar tanto diccionarios como tuplas
            if isinstance(bodega_data, dict):
                # Si es diccionario (cursorclass=DictCursor)
                bodega_id = bodega_data.get('ID_Bodega')
                bodega_empresa_id = bodega_data.get('ID_Empresa')
            else:
                # Si es tupla (cursorclass por defecto)
                bodega_id = bodega_data[0]
                bodega_empresa_id = bodega_data[1]
            
            print(f"DEBUG: Bodega ID: {bodega_id}, Empresa Bodega: {bodega_empresa_id}, Empresa Form: {id_empresa}")
            
            # Verificar que la bodega pertenece a la empresa del producto
            if bodega_empresa_id != id_empresa:
                flash('La bodega seleccionada no pertenece a la empresa del producto', 'error')
                return redirect(url_for('admin_productos'))

            # Verificar si el código de producto ya existe
            if cod_producto:
                cursor.execute("SELECT ID_Producto FROM Productos WHERE COD_Producto = %s", (cod_producto,))
                if cursor.fetchone():
                    flash('El código de producto ya existe', 'error')
                    return redirect(url_for('admin_productos'))
            else:
                # Generar código automático si no se proporciona
                cursor.execute("""
                    SELECT COALESCE(MAX(CAST(COD_Producto AS UNSIGNED)), 0) + 1 
                    FROM Productos 
                    WHERE COD_Producto REGEXP '^[0-9]+$'
                """)
                result = cursor.fetchone()
                
                # Manejar tanto diccionarios como tuplas
                if isinstance(result, dict):
                    max_cod = result.get(list(result.keys())[0])  # Primer valor del diccionario
                else:
                    max_cod = result[0] if result else 0
                    
                cod_producto = str(max_cod + 1) if max_cod else "1"
                print(f"DEBUG: Código generado: {cod_producto}")

            # Insertar nuevo producto
            print(f"DEBUG: Insertando producto...")
            cursor.execute("""
                INSERT INTO Productos (
                    COD_Producto, Descripcion, Unidad_Medida, Estado,
                    ID_Categoria, Precio_Venta, ID_Empresa, Usuario_Creador, Stock_Minimo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cod_producto, descripcion, id_unidad_medida, estado,
                id_categoria, precio_venta, id_empresa, usuario_creador, stock_minimo
            ))

            producto_id = cursor.lastrowid
            print(f"DEBUG: Producto creado con ID: {producto_id}")

            # Insertar en Inventario_Bodega con la cantidad inicial
            cursor.execute("""
                INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Existencias = Existencias + VALUES(Existencias)
            """, (id_bodega, producto_id, cantidad_inicial))

        flash(f'Producto "{descripcion}" creado exitosamente con {cantidad_inicial} unidades en la bodega seleccionada', 'success')
        
    except Exception as e:
        print(f"ERROR DETALLADO: {str(e)}")
        import traceback
        print(traceback.format_exc())
        flash(f'Error al crear producto: {str(e)}', 'error')
    
    return redirect(url_for('admin_productos'))

@app.route('/admin/bodegas/por-empresa/<int:id_empresa>')
@admin_required
def obtener_bodegas_por_empresa(id_empresa):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 'activa'
                ORDER BY Nombre
            """, (id_empresa,))
            bodegas = cursor.fetchall()
        
        return jsonify({
            'bodegas': bodegas
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/bodega/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("EDITAR_PRODUCTO")
def admin_editar_producto(id_producto):
    try:
        if request.method == 'POST':
            # ========== PROCESAR FORMULARIO POST ==========
            # Obtener datos del formulario
            cod_producto = request.form.get('COD_Producto', '').strip()
            descripcion = request.form.get('Descripcion', '').strip()
            unidad_medida = request.form.get('Unidad_Medida')
            id_categoria = request.form.get('ID_Categoria')
            precio_venta = request.form.get('Precio_Venta', 0)
            id_empresa = request.form.get('ID_Empresa')
            stock_minimo = request.form.get('Stock_Minimo', 5)
            estado = request.form.get('Estado', 'activo')  # Cambiado: 'activo' por defecto

            # Validaciones
            if not descripcion:
                flash('La descripción es obligatoria', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            if not unidad_medida or not id_categoria or not id_empresa:
                flash('Unidad de medida, categoría y empresa son campos obligatorios', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            # Validar estado
            if estado not in ['activo', 'inactivo']:
                estado = 'activo'

            # Convertir valores numéricos
            try:
                precio_venta = float(precio_venta) if precio_venta else 0
                stock_minimo = float(stock_minimo) if stock_minimo else 5
                
                # Validar valores positivos
                if precio_venta < 0:
                    flash('El precio de venta no puede ser negativo', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))
                    
                if stock_minimo < 0:
                    flash('El stock mínimo no puede ser negativo', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))
                    
            except (ValueError, TypeError):
                flash('Error en los valores numéricos', 'error')
                return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            with get_db_cursor(commit=True) as cursor:
                # Verificar si el código de producto ya existe en otro producto
                if cod_producto:
                    cursor.execute("""
                        SELECT ID_Producto FROM Productos 
                        WHERE COD_Producto = %s AND ID_Producto != %s
                    """, (cod_producto, id_producto))
                    if cursor.fetchone():
                        flash('El código de producto ya existe en otro producto', 'error')
                        return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                # Verificar que las referencias existan
                cursor.execute("SELECT ID_Unidad FROM Unidades_Medida WHERE ID_Unidad = %s", (unidad_medida,))
                if not cursor.fetchone():
                    flash('La unidad de medida seleccionada no existe', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Categoria FROM categorias_producto WHERE ID_Categoria = %s", (id_categoria,))
                if not cursor.fetchone():
                    flash('La categoría seleccionada no existe', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                cursor.execute("SELECT ID_Empresa FROM empresa WHERE ID_Empresa = %s AND Estado = 'Activo'", (id_empresa,))
                if not cursor.fetchone():
                    flash('La empresa seleccionada no existe o está inactiva', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

                # Actualizar producto
                cursor.execute("""
                    UPDATE Productos SET
                        COD_Producto = %s,
                        Descripcion = %s,
                        Unidad_Medida = %s,
                        ID_Categoria = %s,
                        Precio_Venta = %s,
                        ID_Empresa = %s,
                        Stock_Minimo = %s,
                        Estado = %s
                    WHERE ID_Producto = %s
                """, (
                    cod_producto or None,  # Guardar como NULL si está vacío
                    descripcion, 
                    unidad_medida, 
                    id_categoria,
                    precio_venta, 
                    id_empresa, 
                    stock_minimo, 
                    estado,  # Ahora string 'activo'/'inactivo'
                    id_producto
                ))

                # Verificar si se actualizó algún registro
                if cursor.rowcount == 0:
                    flash('No se pudo actualizar el producto. Puede que no exista.', 'error')
                    return redirect(url_for('admin_editar_producto', id_producto=id_producto))

            flash('Producto actualizado exitosamente', 'success')
            return redirect(url_for('admin_productos'))

        else:
            # ========== CARGAR FORMULARIO GET ==========
            with get_db_cursor() as cursor:
                # Obtener el producto específico (sin Existencias de Productos)
                cursor.execute("""
                    SELECT 
                        p.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida,
                        um.Descripcion as Nombre_Unidad,
                        um.Abreviatura,
                        p.Estado,  -- Ahora 'activo' o 'inactivo'
                        p.ID_Categoria,
                        cp.Descripcion as Nombre_Categoria,
                        p.Precio_Venta,
                        p.ID_Empresa,
                        e.Nombre_Empresa,
                        p.Fecha_Creacion,
                        p.Usuario_Creador,
                        u.NombreUsuario as Usuario_Creador_Nombre,
                        p.Stock_Minimo,
                        -- Calcular existencias totales sumando Inventario_Bodega
                        COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales
                    FROM Productos p
                    LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                    LEFT JOIN empresa e ON p.ID_Empresa = e.ID_Empresa
                    LEFT JOIN usuarios u ON p.Usuario_Creador = u.ID_Usuario
                    LEFT JOIN Inventario_Bodega ib ON p.ID_Producto = ib.ID_Producto
                    WHERE p.ID_Producto = %s
                    GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, p.Unidad_Medida,
                             um.Descripcion, um.Abreviatura, p.Estado, p.ID_Categoria,
                             cp.Descripcion, p.Precio_Venta, p.ID_Empresa, e.Nombre_Empresa,
                             p.Fecha_Creacion, p.Usuario_Creador, u.NombreUsuario, p.Stock_Minimo
                """, (id_producto,))
                producto = cursor.fetchone()
                
                if not producto:
                    flash('Producto no encontrado', 'error')
                    return redirect(url_for('admin_productos'))
                
                # Convertir a diccionario si es necesario
                if isinstance(producto, dict):
                    producto_data = producto
                else:
                    # Si es tupla, convertir a diccionario
                    producto_data = {
                        'ID_Producto': producto[0],
                        'COD_Producto': producto[1],
                        'Descripcion': producto[2],
                        'Unidad_Medida': producto[3],
                        'Nombre_Unidad': producto[4],
                        'Abreviatura': producto[5],
                        'Estado': producto[6],  # 'activo' o 'inactivo'
                        'ID_Categoria': producto[7],
                        'Nombre_Categoria': producto[8],
                        'Precio_Venta': producto[9],
                        'ID_Empresa': producto[10],
                        'Nombre_Empresa': producto[11],
                        'Fecha_Creacion': producto[12],
                        'Usuario_Creador': producto[13],
                        'Usuario_Creador_Nombre': producto[14],
                        'Stock_Minimo': producto[15],
                        'Existencias_Totales': producto[16] or 0
                    }
                
                print(f"DEBUG - Estado del producto: {producto_data.get('Estado')}")
                print(f"DEBUG - Existencias totales: {producto_data.get('Existencias_Totales')}")
                
                # Obtener datos para los dropdowns
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto")
                categorias = cursor.fetchall()
                
                cursor.execute("SELECT ID_Unidad, Descripcion, Abreviatura FROM Unidades_Medida")
                unidades = cursor.fetchall()
                
                cursor.execute("SELECT ID_Empresa, Nombre_Empresa FROM empresa WHERE Estado = 'Activo'")
                empresas = cursor.fetchall()
                
                # CONSULTA PARA INVENTARIO POR BODEGA (sin cambios)
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega, 
                        b.Nombre as Nombre_Bodega,
                        e.Nombre_Empresa,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM Bodegas b
                    JOIN empresa e ON b.ID_Empresa = e.ID_Empresa
                    LEFT JOIN Inventario_Bodega ib ON b.ID_Bodega = ib.ID_Bodega AND ib.ID_Producto = %s
                    WHERE b.Estado = 'activa'
                    ORDER BY e.Nombre_Empresa, b.Nombre
                """, (id_producto,))
                inventario_bodegas = cursor.fetchall()
                
                fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M')
                
                return render_template('admin/bodega/producto/editar_producto.html', 
                                     producto=producto_data,
                                     categorias=categorias,
                                     unidades=unidades,
                                     empresas=empresas,
                                     inventario_bodegas=inventario_bodegas,
                                     fecha_actual=fecha_actual)
                
    except Exception as e:
        flash(f'Error al procesar producto: {str(e)}', 'error')
        traceback.print_exc()
        return redirect(url_for('admin_productos'))
    
@app.route('/admin/bodega/productos/activar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("ACTIVAR_PRODUCTO")
def admin_activar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Productos 
                SET Estado = 'activo'  -- Cambiado de 1 a 'activo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            # Verificar si se actualizó
            if cursor.rowcount > 0:
                flash('Producto activado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al activar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin_productos'))

@app.route('/admin/bodega/productos/desactivar/<int:id_producto>', methods=['POST'])
@admin_required
@bitacora_decorator("DESACTIVAR_PRODUCTO")
def admin_desactivar_producto(id_producto):
    try:
        with get_db_cursor(commit=True) as cursor:
            cursor.execute("""
                UPDATE Productos 
                SET Estado = 'inactivo'  -- Cambiado de 0 a 'inactivo'
                WHERE ID_Producto = %s
            """, (id_producto,))
            
            # Verificar si se actualizó
            if cursor.rowcount > 0:
                flash('Producto desactivado exitosamente', 'success')
            else:
                flash('Producto no encontrado', 'error')
                
    except Exception as e:
        flash(f'Error al desactivar producto: {str(e)}', 'error')
        
    return redirect(url_for('admin_productos'))

#MODULO PRODUCTOS - COMPRAS
@app.route('/admin/compras/compras-entradas', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS")
def admin_compras_entradas():
    try:
        with get_db_cursor() as cursor:
            # Consulta 1: Obtener las entradas para la tabla
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    p.Nombre as Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    cm.Letra,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'Activa'
                        WHEN mi.Estado = 'Anulada' THEN 'Anulada'
                        ELSE mi.Estado 
                    END as Estado,
                    COALESCE(detalle.Total_Productos, 0) as Total_Productos,
                    COALESCE(detalle.Total_Compra, 0) as Total_Compra
                FROM Movimientos_Inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN (
                    SELECT 
                        ID_Movimiento,
                        COUNT(*) as Total_Productos,
                        SUM(COALESCE(Subtotal, 0)) as Total_Compra
                    FROM Detalle_Movimientos_Inventario
                    GROUP BY ID_Movimiento
                ) detalle ON mi.ID_Movimiento = detalle.ID_Movimiento
                WHERE (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC
                LIMIT 15
            """)
            entradas = cursor.fetchall()
            
            # **CONSULTA 2: Capital Invertido TOTAL (Contado + Crédito)**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Total
                FROM Movimientos_Inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN Detalle_Movimientos_Inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_total = cursor.fetchone()
            capital_total = resultado_total['Capital_Total'] if resultado_total else 0.0
            
            # **CONSULTA 3: Capital Invertido SOLO AL CONTADO**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Contado
                FROM Movimientos_Inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN Detalle_Movimientos_Inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CONTADO'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_contado = cursor.fetchone()
            capital_contado = resultado_contado['Capital_Contado'] if resultado_contado else 0.0
            
            # **CONSULTA 4: Capital en CRÉDITO (deudas pendientes)**
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(dmi.Subtotal), 0) as Capital_Credito
                FROM Movimientos_Inventario mi
                INNER JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                INNER JOIN Detalle_Movimientos_Inventario dmi ON mi.ID_Movimiento = dmi.ID_Movimiento
                WHERE mi.Estado = 'Activa'
                    AND mi.Tipo_Compra = 'CREDITO'
                    AND (cm.Adicion = 'ENTRADA' OR cm.Letra = 'E')
                    AND (cm.Descripcion LIKE '%compra%' OR cm.Descripcion LIKE '%COMPRA%')
            """)
            resultado_credito = cursor.fetchone()
            capital_credito = resultado_credito['Capital_Credito'] if resultado_credito else 0.0
            
            # **VALIDACIÓN**: Asegurar que Total = Contado + Crédito
            diferencia = abs(capital_total - (capital_contado + capital_credito))
            if diferencia > 0.01:  # Tolerancia de 1 centavo
                print(f"ADVERTENCIA: Discrepancia en cálculos. Total: {capital_total}, Contado: {capital_contado}, Crédito: {capital_credito}")
            
            # Inicializar contadores para las entradas mostradas
            total_compras = len(entradas)
            total_invertido_lista = 0.0  # Solo las 15 mostradas
            total_productos_activos = 0
            contado_activas = 0
            credito_activas = 0
            
            # Calcular estadísticas solo para las entradas mostradas
            for entrada in entradas:
                if entrada['Estado'] == 'Activa':
                    total_invertido_lista += float(entrada['Total_Compra'] or 0)
                    total_productos_activos += int(entrada['Total_Productos'] or 0)
                    
                    if entrada['Tipo_Compra'] == 'CONTADO':
                        contado_activas += 1
                    elif entrada['Tipo_Compra'] == 'CREDITO':
                        credito_activas += 1
            
            return render_template('admin/compras/compras_entradas.html', 
                                 entradas=entradas,
                                 total_invertido=total_invertido_lista,
                                 capital_total=capital_total,           # Total (Contado + Crédito)
                                 capital_contado=capital_contado,       # Solo contado
                                 capital_credito=capital_credito,       # Solo crédito
                                 total_productos_activos=total_productos_activos,
                                 contado_activas=contado_activas,
                                 credito_activas=credito_activas,
                                 total_compras=total_compras)
    except Exception as e:
        flash(f'Error al cargar entradas de compras: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/compras/compras-entradas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-CREAR")
def admin_crear_compra():
    try:
        if request.method == 'GET':
            id_empresa = session.get('id_empresa', 1)
            
            with get_db_cursor(True) as cursor:  
                cursor.execute("SELECT ID_Proveedor, Nombre FROM Proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # CONSULTA CORREGIDA: Información básica de productos
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                        p.ID_Categoria, 
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_empresa,))
                productos = cursor.fetchall()
                
                return render_template('admin/compras/crear_compra.html',
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias)
        
        elif request.method == 'POST':
            # Obtener datos del formulario

            id_usuario_creacion = current_user.id

            id_tipo_movimiento = 1
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            id_usuario_creacion
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario - SIN LOTE Y FECHA_VENCIMIENTO
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            precios_unitarios = request.form.getlist('precios_unitarios[]')
            
            print(f"Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_creacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            # Construir lista de productos - SIN LOTE Y FECHA_VENCIMIENTO
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    precio_unitario = round(float(precios_unitarios[i]) if precios_unitarios[i] and precios_unitarios[i] != '' else costo_unitario, 2)
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_creacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin_crear_compra'))
            
            # USAR TRANSACCIÓN CON COMMIT
            with get_db_cursor(commit=True) as cursor:
                # Calcular total de la compra
                total_compra = sum(
                    producto['cantidad'] * producto['costo_unitario'] 
                    for producto in productos
                )
                
                # Insertar movimiento principal
                cursor.execute("""
                    INSERT INTO Movimientos_Inventario (
                        ID_TipoMovimiento, N_Factura_Externa, Fecha, ID_Proveedor, 
                        Tipo_Compra, Observacion, ID_Empresa, ID_Bodega, 
                        ID_Usuario_Creacion, ID_Usuario_Modificacion, Estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    session.get('id_empresa', 1),
                    id_bodega,
                    id_usuario,
                    id_usuario,
                    1  # Estado activo/completado
                ))
                
                id_movimiento = cursor.lastrowid
                print(f"Movimiento creado con ID: {id_movimiento}")
                
                # Insertar detalles del movimiento - SIN LOTE Y FECHA_VENCIMIENTO
                for producto in productos:
                    subtotal = round(producto['cantidad'] * producto['costo_unitario'], 2)
                    
                    # Insertar detalle del movimiento
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        producto['cantidad'],
                        producto['costo_unitario'],
                        producto['precio_unitario'],
                        subtotal,
                        id_usuario
                    ))
                    
                    # Actualizar Inventario_Bodega (existencias por bodega)
                    cursor.execute("""
                        SELECT ID_Producto FROM Inventario_Bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['id_producto']))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        # Actualizar existencias si ya existe
                        cursor.execute("""
                            UPDATE Inventario_Bodega 
                            SET Existencias = Existencias + %s 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (producto['cantidad'], id_bodega, producto['id_producto']))
                    else:
                        # Insertar nuevo registro si no existe
                        cursor.execute("""
                            INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['id_producto'], producto['cantidad']))
                
                    # CREAR CUENTA POR PAGAR SI ES CRÉDITO
                    if tipo_compra == 'CREDITO' and id_proveedor:
                        if not fecha_vencimiento:
                            from datetime import datetime, timedelta
                            fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                            fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO Cuentas_Por_Pagar (
                                ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                                Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                                Saldo_Pendiente, ID_Usuario_Creacion, Estado
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento,
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            session.get('id_empresa', 1),
                            total_compra,
                            id_usuario,
                            'Pendiente'  # NUEVO CAMPO REQUERIDO
                        ))
                
                flash(f'Compra creada exitosamente', 'success')
                return redirect(url_for('admin_compras_entradas'))            
    except Exception as e:
        print(f"Error completo al crear compra: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error al crear compra: {str(e)}', 'error')
        return redirect(url_for('admin_crear_compra'))
    
# RUTAS AUXILIARES PARA COMPRAS - CORREGIDAS (BASADAS EN MOVIMIENTOS_INVENTARIO)
@app.route('/admin/compras/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_compra(id_categoria):
    """
    Obtiene productos filtrados por categoría usando inventario_bodega
    RUTA FUNCIONANDO: ✅
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega para la empresa'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            if id_categoria == 0:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_bodega, id_empresa))
            else:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        COALESCE(p.Precio_Venta, 0) as Precio_Venta,
                        p.ID_Categoria,
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                        AND ib.ID_Bodega = %s
                    WHERE p.Estado = 'activo'
                    AND p.ID_Categoria = %s 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    ORDER BY p.Descripcion
                """, (id_bodega, id_categoria, id_empresa))
            
            productos = cursor.fetchall()
            productos_list = [{
                'id': p['ID_Producto'],
                'codigo': p['COD_Producto'],
                'descripcion': p['Descripcion'],
                'existencias': float(p['Existencias']),
                'precio_venta': float(p['Precio_Venta']),
                'id_categoria': p['ID_Categoria'],
                'categoria': p['Categoria'],
                'unidad_medida': p['Unidad_Medida'],
                'simbolo_medida': p['Simbolo_Medida']
            } for p in productos]
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ Error al obtener productos: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/compras/verificar-existencias/<int:id_producto>')
@admin_required
def verificar_existencias_producto(id_producto):
    """
    Verifica existencias de un producto usando inventario_bodega
    RUTA FUNCIONANDO: ✅
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # Obtener bodega de la empresa
            cursor.execute("""
                SELECT ID_Bodega FROM bodegas 
                WHERE ID_Empresa = %s AND Estado = 1 LIMIT 1
            """, (id_empresa,))
            bodega_result = cursor.fetchone()
            
            if not bodega_result:
                return jsonify({'error': 'No se encontró bodega'}), 404
            
            id_bodega = bodega_result['ID_Bodega']
            
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion,
                    COALESCE(p.Precio_Venta, 0) as Precio_Venta,
                    um.Descripcion as Unidad_Medida,
                    COALESCE(ib.Existencias, 0) as Existencias
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE p.ID_Producto = %s 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND p.Estado = 'activo'
            """, (id_bodega, id_producto, id_empresa))
            
            producto = cursor.fetchone()
            
            if producto:
                return jsonify({
                    'id_producto': producto['ID_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']),
                    'precio_venta': float(producto['Precio_Venta']),
                    'unidad_medida': producto['Unidad_Medida']
                })
            else:
                return jsonify({'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f"❌ Error al verificar existencias: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/compras/categorias-productos')
@admin_required
def obtener_categorias_productos_compra():
    """
    Obtiene todas las categorías de productos
    RUTA FUNCIONANDO: ✅
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            categorias_list = [{
                'id': c['ID_Categoria'],
                'descripcion': c['Descripcion']
            } for c in categorias]
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"❌ Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500

def obtener_id_bodega_empresa(id_empresa=None):
    """
    Obtiene el ID de la bodega principal de una empresa
    FUNCIÓN AUXILIAR: ✅
    """
    if id_empresa is None:
        id_empresa = session.get('id_empresa', 1)
    
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Bodega 
                FROM bodegas 
                WHERE ID_Empresa = %s 
                AND Estado = 1
                LIMIT 1
            """, (id_empresa,))
            
            result = cursor.fetchone()
            return result['ID_Bodega'] if result else None
    except Exception as e:
        print(f"❌ Error al obtener bodega: {str(e)}")
        return None

@app.route('/admin/compras/compras-entradas/editar/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-EDITAR")
def admin_editar_compra(id_movimiento):
    try:
        if request.method == 'GET':
            with get_db_cursor(True) as cursor:
                # Obtener datos del movimiento principal
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.ID_TipoMovimiento,
                        mi.N_Factura_Externa,
                        mi.Fecha,
                        mi.ID_Proveedor,
                        mi.Tipo_Compra,
                        mi.Observacion,
                        mi.ID_Bodega,
                        mi.ID_Usuario_Creacion,
                        cm.Descripcion as Tipo_Movimiento_Desc,
                        (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                         WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra,
                        mi.Estado
                    FROM Movimientos_Inventario mi
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE mi.ID_Movimiento = %s AND mi.Estado = 1
                """, (id_movimiento,))
                
                movimiento = cursor.fetchone()
                
                if not movimiento:
                    flash('Compra no encontrada o ha sido anulada', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # Obtener detalles del movimiento - CORREGIDO: Sin Lote y Fecha_Vencimiento
                cursor.execute("""
                    SELECT 
                        dmi.ID_Detalle_Movimiento,
                        dmi.ID_Producto,
                        p.COD_Producto,
                        p.Descripcion as Producto_Desc,
                        COALESCE((
                            SELECT SUM(dmi2.Cantidad) 
                            FROM detalle_movimientos_inventario dmi2
                            INNER JOIN Movimientos_Inventario mi2 ON dmi2.ID_Movimiento = mi2.ID_Movimiento
                            WHERE dmi2.ID_Producto = p.ID_Producto
                            AND mi2.ID_TipoMovimiento = 1  -- Solo compras
                            AND mi2.Estado = 1
                        ), 0) as Existencias,
                        dmi.Cantidad,
                        dmi.Costo_Unitario,
                        dmi.Precio_Unitario,
                        dmi.Subtotal
                    FROM detalle_movimientos_inventario dmi
                    INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles = cursor.fetchall()
                
                # Obtener tipos de movimiento de entrada/compra
                cursor.execute("""
                    SELECT ID_TipoMovimiento, Descripcion, Letra, Adicion
                    FROM catalogo_movimientos 
                    WHERE Adicion = 'ENTRADA' OR Letra = 'E'
                    ORDER BY Descripcion
                """)
                tipos_movimiento = cursor.fetchall()
                
                # Obtener proveedores activos
                cursor.execute("SELECT ID_Proveedor, Nombre FROM Proveedores WHERE Estado = 'ACTIVO' ORDER BY Nombre")
                proveedores = cursor.fetchall()
                
                # Obtener bodegas activas
                cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 'activa'")
                bodegas = cursor.fetchall()
                
                # Obtener categorías de productos
                cursor.execute("SELECT ID_Categoria, Descripcion FROM categorias_producto ORDER BY Descripcion")
                categorias = cursor.fetchall()
                
                # Obtener productos activos CON PRECIO_VENTA y UNIDAD DE MEDIDA
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion,
                        p.Precio_Venta, 
                        p.ID_Categoria, 
                        c.Descripcion as Categoria,
                        um.Descripcion as Unidad_Medida,
                        um.Abreviatura as Simbolo_Medida
                    FROM Productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                    WHERE p.Estado = 'activo'
                    ORDER BY c.Descripcion, p.Descripcion
                """)
                productos = cursor.fetchall()
                
                # Verificar si existe cuenta por pagar
                cursor.execute("""
                    SELECT ID_Cuenta, Saldo_Pendiente, Monto_Movimiento
                    FROM Cuentas_Por_Pagar 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento,))
                cuenta_por_pagar = cursor.fetchone()
                
                return render_template('admin/compras/editar_compra.html',
                                    movimiento=movimiento,
                                    detalles=detalles,
                                    tipos_movimiento=tipos_movimiento,
                                    proveedores=proveedores,
                                    bodegas=bodegas,
                                    productos=productos,
                                    categorias=categorias,
                                    cuenta_por_pagar=cuenta_por_pagar)
        
        elif request.method == 'POST':
            id_usuario_modificacion = current_user.id
            
            # Obtener datos del formulario
            id_tipo_movimiento = request.form.get('id_tipo_movimiento')
            n_factura_externa = request.form.get('n_factura_externa')
            fecha = request.form.get('fecha')
            id_proveedor = request.form.get('id_proveedor')
            tipo_compra = request.form.get('tipo_compra', 'CONTADO')
            observacion = request.form.get('observacion')
            id_bodega = request.form.get('id_bodega')
            fecha_vencimiento = request.form.get('fecha_vencimiento')
            
            # Obtener productos del formulario - CORREGIDO: Sin lotes y fechas de vencimiento
            productos = []
            producto_ids = request.form.getlist('productos[]')
            cantidades = request.form.getlist('cantidades[]')
            costos_unitarios = request.form.getlist('costos_unitarios[]')
            precios_unitarios = request.form.getlist('precios_unitarios[]')
            
            print(f"[EDIT] Datos recibidos - Productos: {len(producto_ids)}, IDs: {producto_ids}")
            
            # Validar datos requeridos
            if not all([id_tipo_movimiento, fecha, id_bodega, id_usuario_modificacion]):
                flash('Todos los campos obligatorios deben ser completados', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            # Validar que hay productos
            if not producto_ids or len(producto_ids) == 0:
                flash('Debe agregar al menos un producto', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            # Construir lista de productos - CORREGIDO: Sin lotes y fechas de vencimiento
            for i in range(len(producto_ids)):
                if producto_ids[i] and cantidades[i] and costos_unitarios[i]:
                    cantidad = round(float(cantidades[i]), 2)
                    costo_unitario = round(float(costos_unitarios[i]), 2)
                    precio_unitario = round(float(precios_unitarios[i]) if precios_unitarios[i] and precios_unitarios[i] != '' else costo_unitario, 2)
                    
                    productos.append({
                        'id_producto': producto_ids[i],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'precio_unitario': precio_unitario
                    })
            
            # Validar usuario
            try:
                id_usuario = int(id_usuario_modificacion)
                if id_usuario <= 0:
                    raise ValueError("ID debe ser mayor a 0")
            except (ValueError, TypeError) as e:
                print(f"[EDIT] Error en ID usuario: {e}")
                flash('ID de usuario no válido', 'error')
                return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))
            
            # USAR get_db_cursor(True) para transacción automática
            with get_db_cursor(True) as cursor:
                # 1. Verificar que el movimiento existe y está activo
                cursor.execute("""
                    SELECT Estado, ID_Bodega, Tipo_Compra, ID_Proveedor 
                    FROM Movimientos_Inventario 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento,))
                movimiento_actual = cursor.fetchone()
                
                if not movimiento_actual:
                    flash('Movimiento no encontrado', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                if movimiento_actual['Estado'] != 1:
                    flash('No se puede editar un movimiento anulado', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                bodega_anterior = movimiento_actual['ID_Bodega']
                print(f"[EDIT] Reversando existencias de movimiento {id_movimiento} de bodega {bodega_anterior}")
                
                # 2. Reversar existencias de productos anteriores
                cursor.execute("""
                    SELECT dmi.ID_Producto, dmi.Cantidad 
                    FROM detalle_movimientos_inventario dmi
                    WHERE dmi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles_anteriores = cursor.fetchall()
                
                for detalle in detalles_anteriores:
                    cursor.execute("""
                        UPDATE Inventario_Bodega 
                        SET Existencias = Existencias - %s 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (detalle['Cantidad'], bodega_anterior, detalle['ID_Producto']))
                    print(f"[EDIT] Reversado producto {detalle['ID_Producto']} en bodega {bodega_anterior}: -{detalle['Cantidad']} unidades")
                
                # 3. Eliminar detalles anteriores
                cursor.execute("DELETE FROM detalle_movimientos_inventario WHERE ID_Movimiento = %s", (id_movimiento,))
                print(f"[EDIT] Detalles anteriores eliminados")
                
                # 4. Actualizar movimiento principal
                cursor.execute("""
                    UPDATE Movimientos_Inventario 
                    SET ID_TipoMovimiento = %s,
                        N_Factura_Externa = %s,
                        Fecha = %s,
                        ID_Proveedor = %s,
                        Tipo_Compra = %s,
                        Observacion = %s,
                        ID_Bodega = %s,
                        ID_Usuario_Modificacion = %s,
                        Fecha_Modificacion = NOW()
                    WHERE ID_Movimiento = %s
                """, (
                    id_tipo_movimiento,
                    n_factura_externa,
                    fecha,
                    id_proveedor if id_proveedor else None,
                    tipo_compra,
                    observacion,
                    id_bodega,
                    id_usuario,
                    id_movimiento
                ))
                print(f"[EDIT] Movimiento principal actualizado")
                
                # 5. Insertar nuevos detalles y actualizar existencias
                total_compra = 0
                for producto in productos:
                    cantidad = producto['cantidad']
                    costo_unitario = producto['costo_unitario']
                    subtotal = round(cantidad * costo_unitario, 2)
                    total_compra += subtotal
                    
                    # Insertar detalle - CORREGIDO: Sin Lote y Fecha_Vencimiento
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                            Precio_Unitario, Subtotal, ID_Usuario_Creacion
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        producto['id_producto'],
                        cantidad,
                        costo_unitario,
                        producto['precio_unitario'],
                        subtotal,
                        id_usuario
                    ))
                    
                    # Actualizar Inventario_Bodega
                    cursor.execute("""
                        SELECT ID_Producto FROM Inventario_Bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['id_producto']))
                    
                    existing_record = cursor.fetchone()
                    
                    if existing_record:
                        cursor.execute("""
                            UPDATE Inventario_Bodega 
                            SET Existencias = Existencias + %s 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (cantidad, id_bodega, producto['id_producto']))
                    else:
                        cursor.execute("""
                            INSERT INTO Inventario_Bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['id_producto'], cantidad))
                    
                    print(f"[EDIT] Producto {producto['id_producto']} agregado en bodega {id_bodega}: +{cantidad} unidades")
                
                print(f"[EDIT] Total compra actualizado: C$ {total_compra:.2f}")
                
                # 6. Manejar cuenta por pagar
                cursor.execute("SELECT ID_Cuenta FROM Cuentas_Por_Pagar WHERE ID_Movimiento = %s", (id_movimiento,))
                cuenta_existente = cursor.fetchone()
                
                # Si la compra es a crédito y hay proveedor
                if tipo_compra == 'CREDITO' and id_proveedor:
                    if not fecha_vencimiento:
                        from datetime import datetime, timedelta
                        fecha_compra = datetime.strptime(fecha, '%Y-%m-%d')
                        fecha_vencimiento = (fecha_compra + timedelta(days=30)).strftime('%Y-%m-%d')
                    
                    if cuenta_existente:
                        # Actualizar cuenta existente
                        cursor.execute("""
                            UPDATE Cuentas_Por_Pagar 
                            SET Fecha = %s,
                                ID_Proveedor = %s,
                                Num_Documento = %s,
                                Observacion = %s,
                                Fecha_Vencimiento = %s,
                                Tipo_Movimiento = %s,
                                Monto_Movimiento = %s,
                                Saldo_Pendiente = %s,
                                ID_Usuario_Creacion = %s
                            WHERE ID_Movimiento = %s
                        """, (
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito editada',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            total_compra,
                            id_usuario,
                            id_movimiento
                        ))
                        print(f"[EDIT] Cuenta por pagar actualizada")
                    else:
                        # Crear nueva cuenta
                        cursor.execute("""
                            INSERT INTO Cuentas_Por_Pagar (
                                ID_Movimiento, Fecha, ID_Proveedor, Num_Documento, Observacion,
                                Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento, ID_Empresa,
                                Saldo_Pendiente, ID_Usuario_Creacion
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento,
                            fecha,
                            id_proveedor,
                            n_factura_externa or '',
                            observacion or 'Compra a crédito',
                            fecha_vencimiento,
                            id_tipo_movimiento,
                            total_compra,
                            session.get('id_empresa', 1),
                            total_compra,
                            id_usuario
                        ))
                        print(f"[EDIT] Nueva cuenta por pagar creada")
                elif cuenta_existente:
                    # Si antes era crédito y ahora es contado, eliminar la cuenta
                    cursor.execute("DELETE FROM Cuentas_Por_Pagar WHERE ID_Movimiento = %s", (id_movimiento,))
                    print(f"[EDIT] Cuenta por pagar eliminada (cambio a contado)")
                
                flash('Compra actualizada exitosamente', 'success')
                print(f"[EDIT] Compra {id_movimiento} actualizada exitosamente")
                return redirect(url_for('admin_compras_entradas'))
                
    except Exception as e:
        print(f" Error editando compra: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.method == 'GET':
            flash(f'Error al cargar formulario de edición: {str(e)}', 'error')
            return redirect(url_for('admin_compras_entradas'))
        else:
            flash(f'Error al actualizar compra: {str(e)}', 'error')
            return redirect(url_for('admin_editar_compra', id_movimiento=id_movimiento))

@app.route('/admin/compras/compras-entradas/anular/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-ANULAR")
def admin_anular_compra(id_movimiento):
    """Anular una compra existente - CON get_db_cursor"""
    
    # Si es GET, mostrar información detallada de la compra
    if request.method == 'GET':
        try:
            with get_db_cursor(commit=False) as cursor:
                # CONSULTA RÁPIDA - Solo datos básicos
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.N_Factura_Externa,
                        mi.Fecha,
                        mi.Tipo_Compra,
                        mi.Estado,
                        p.Nombre as Proveedor,
                        b.Nombre as Bodega,
                        cm.Adicion,
                        cm.Letra,
                        (
                            SELECT COUNT(*) 
                            FROM Detalle_Movimientos_Inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ) as Total_Productos,
                        (
                            SELECT SUM(COALESCE(Subtotal, 0))
                            FROM Detalle_Movimientos_Inventario 
                            WHERE ID_Movimiento = mi.ID_Movimiento
                        ) as Total_Compra
                    FROM Movimientos_Inventario mi
                    LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE mi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                compra = cursor.fetchone()
                
                if not compra:
                    return jsonify({'success': False, 'error': 'Compra no encontrada'}), 404
                
                if compra['Estado'] != 'Activa':
                    # CORREGIDO: Cambiado "venta" por "compra"
                    estado_texto = "anulada" if compra['Estado'] == 'Anulada' else compra['Estado'].lower()
                    return jsonify({'success': False, 'error': f'La compra #{id_movimiento} ya está {estado_texto}'}), 400
                
                # Verificar que sea un movimiento de entrada
                if compra['Adicion'] != 'ENTRADA' and compra['Letra'] != 'E':
                    # CORREGIDO: Mensaje más específico
                    return jsonify({'success': False, 'error': f'El movimiento #{id_movimiento} no es una entrada de compra válida'}), 400
                
                # Obtener parámetro para saber qué datos cargar
                carga_completa = request.args.get('completa', '0') == '1'
                
                datos_respuesta = {
                    'success': True,
                    'compra': {
                        'id': compra['ID_Movimiento'],
                        'factura': compra['N_Factura_Externa'] or 'Sin factura',
                        'tipo_compra': compra['Tipo_Compra'],
                        'fecha': compra['Fecha'].strftime('%d/%m/%Y') if compra['Fecha'] else 'N/A',
                        'total': float(compra['Total_Compra'] or 0),
                        'total_formateado': f"C${float(compra['Total_Compra'] or 0):,.2f}",
                        'proveedor': compra['Proveedor'] or 'Proveedor General',
                        'bodega': compra['Bodega'] or 'N/A',
                        'estado': compra['Estado'],
                        'total_productos': compra['Total_Productos'] or 0,
                        'carga_completa': carga_completa
                    }
                }
                
                # SOLO si se solicita carga completa, obtener productos
                if carga_completa:
                    cursor.execute("""
                        SELECT 
                            p.COD_Producto,
                            p.Descripcion,
                            p.Unidad_Medida,
                            dmi.Cantidad,
                            dmi.Costo_Unitario,
                            dmi.Subtotal,
                            COALESCE(ib.Existencias, 0) as Stock_Actual
                        FROM Detalle_Movimientos_Inventario dmi
                        INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                        LEFT JOIN inventario_bodega ib ON ib.ID_Producto = p.ID_Producto 
                            AND ib.ID_Bodega = (SELECT ID_Bodega FROM Movimientos_Inventario WHERE ID_Movimiento = %s)
                        WHERE dmi.ID_Movimiento = %s
                        ORDER BY p.Descripcion
                    """, (id_movimiento, id_movimiento))
                    
                    productos = cursor.fetchall()
                    
                    if productos:
                        productos_formateados = []
                        total_cantidad = 0
                        stock_suficiente = True
                        
                        for producto in productos:
                            cantidad = float(producto['Cantidad'] or 0)
                            stock_actual = float(producto['Stock_Actual'] or 0)
                            suficiente = stock_actual >= cantidad
                            
                            if not suficiente:
                                stock_suficiente = False
                            
                            productos_formateados.append({
                                'codigo': producto['COD_Producto'],
                                'descripcion': producto['Descripcion'],
                                'unidad': producto['Unidad_Medida'],
                                'cantidad': cantidad,
                                'costo_unitario': float(producto['Costo_Unitario'] or 0),
                                'subtotal': float(producto['Subtotal'] or 0),
                                'stock_actual': stock_actual,
                                'suficiente_stock': suficiente
                            })
                            
                            total_cantidad += cantidad
                        
                        datos_respuesta['compra']['productos'] = productos_formateados
                        datos_respuesta['compra']['total_cantidad'] = total_cantidad
                        datos_respuesta['compra']['stock_suficiente'] = stock_suficiente
                
                return jsonify(datos_respuesta)
                
        except Exception as e:
            print(f"Error en GET anular compra {id_movimiento}: {str(e)}")
            return jsonify({'success': False, 'error': 'Error al obtener datos de la compra'}), 500
    
    # Si es POST, procesar la anulación
    elif request.method == 'POST':
        try:
            # Obtener datos del formulario
            id_usuario_anulacion = current_user.id
            motivo_anulacion = request.form.get('motivo_anulacion', '').strip()
            
            # Validaciones básicas
            if not id_usuario_anulacion:
                flash('Error: No se especificó el usuario que realiza la anulación', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            try:
                id_usuario = int(id_usuario_anulacion)
            except (ValueError, TypeError):
                flash('Error: ID de usuario inválido', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            if not motivo_anulacion:
                motivo_anulacion = f"Compra anulada por usuario ID {id_usuario}"
            
            # USAR TRANSACCIÓN CON get_db_cursor
            with get_db_cursor(commit=True) as cursor:
                # 1. Verificar que el movimiento existe y está activo
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        mi.Estado,
                        mi.Tipo_Compra,
                        mi.ID_Bodega,
                        mi.ID_Proveedor,
                        mi.N_Factura_Externa,
                        mi.Observacion,
                        mi.Fecha,
                        mi.ID_TipoMovimiento,
                        mi.ID_Empresa,
                        cm.Adicion as Tipo_Movimiento_Adicion,
                        cm.Letra as Tipo_Movimiento_Letra,
                        (SELECT SUM(Subtotal) 
                         FROM Detalle_Movimientos_Inventario 
                         WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra
                    FROM Movimientos_Inventario mi
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE mi.ID_Movimiento = %s
                    FOR UPDATE
                """, (id_movimiento,))
                
                movimiento = cursor.fetchone()
                
                if not movimiento:
                    flash('Error: Compra no encontrada', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                if movimiento['Estado'] != 'Activa':
                    # CORREGIDO: Mensaje específico para compra
                    flash(f'Error: La compra ya está {movimiento["Estado"].lower()}', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # Verificar que sea un movimiento de entrada
                if movimiento['Tipo_Movimiento_Adicion'] != 'ENTRADA' and movimiento['Tipo_Movimiento_Letra'] != 'E':
                    flash('Error: Este movimiento no es una entrada/compra válida', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # Extraer datos
                id_bodega = movimiento['ID_Bodega']
                total_compra = float(movimiento['Total_Compra'] or 0)
                tipo_compra = movimiento['Tipo_Compra']
                id_proveedor = movimiento['ID_Proveedor']
                n_factura_externa = movimiento['N_Factura_Externa']
                id_empresa = movimiento['ID_Empresa']
                
                # 2. Obtener detalles de productos
                cursor.execute("""
                    SELECT 
                        dmi.ID_Producto, 
                        dmi.Cantidad, 
                        dmi.Costo_Unitario,
                        dmi.Subtotal,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida
                    FROM Detalle_Movimientos_Inventario dmi
                    INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.ID_Movimiento = %s
                """, (id_movimiento,))
                
                detalles = cursor.fetchall()
                
                if not detalles:
                    flash('Error: No se encontraron productos en esta compra', 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # 3. Verificar existencias
                productos_sin_stock = []
                for detalle in detalles:
                    producto_id = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    
                    cursor.execute("""
                        SELECT Existencias 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                        FOR UPDATE
                    """, (id_bodega, producto_id))
                    
                    inventario = cursor.fetchone()
                    
                    if not inventario:
                        # Crear registro si no existe
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, 0)
                        """, (id_bodega, producto_id))
                        existencias_actuales = 0
                    else:
                        existencias_actuales = float(inventario['Existencias'] or 0)
                    
                    if existencias_actuales < cantidad:
                        productos_sin_stock.append({
                            'codigo': detalle['COD_Producto'],
                            'descripcion': detalle['Descripcion'],
                            'existencias': existencias_actuales,
                            'cantidad': cantidad
                        })
                
                if productos_sin_stock:
                    # CORREGIDO: Cambiado "venta" por "compra"
                    error_msg = "No se puede anular la compra por falta de stock:<br><ul>"
                    for prod in productos_sin_stock:
                        error_msg += f"<li>{prod['codigo']} - {prod['descripcion']}: Existencias ({prod['existencias']}) < Cantidad a reversar ({prod['cantidad']})</li>"
                    error_msg += "</ul>"
                    flash(Markup(error_msg), 'error')
                    return redirect(url_for('admin_compras_entradas'))
                
                # 4. Reversar existencias
                productos_reversados = []
                for detalle in detalles:
                    producto_id = detalle['ID_Producto']
                    cantidad = float(detalle['Cantidad'])
                    costo_unitario = float(detalle['Costo_Unitario'] or 0)
                    
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, producto_id))
                    
                    productos_reversados.append({
                        'id': producto_id,
                        'codigo': detalle['COD_Producto'],
                        'descripcion': detalle['Descripcion'],
                        'cantidad': cantidad,
                        'costo_unitario': costo_unitario,
                        'subtotal': float(detalle['Subtotal'] or 0)
                    })
                
                # 5. OPCIONAL: Buscar tipo de movimiento para SALIDA
                cursor.execute("""
                    SELECT ID_TipoMovimiento 
                    FROM catalogo_movimientos 
                    WHERE Descripcion = 'Anulacion Compra' OR ID_TipoMovimiento = 9
                    LIMIT 1
                """)
                
                tipo_salida = cursor.fetchone()
                id_movimiento_salida = None
                
                if tipo_salida:
                    id_tipo_movimiento_salida = tipo_salida['ID_TipoMovimiento']
                    
                    # Crear movimiento de salida (contramovimiento)
                    cursor.execute("""
                        INSERT INTO Movimientos_Inventario (
                            ID_TipoMovimiento,
                            N_Factura_Externa,
                            Fecha,
                            ID_Proveedor,
                            Tipo_Compra,
                            Observacion,
                            ID_Empresa,
                            ID_Bodega,
                            ID_Usuario_Creacion,
                            Estado
                        ) VALUES (
                            %s,
                            CONCAT('ANUL-COMPRA-', %s),
                            CURDATE(),
                            %s,
                            'CONTADO',
                            %s,
                            %s,
                            %s,
                            %s,
                            'Activa'
                        )
                    """, (
                        id_tipo_movimiento_salida,
                        n_factura_externa or str(id_movimiento),
                        id_proveedor,
                        f"Contramovimiento por anulación de compra #{id_movimiento} - {motivo_anulacion[:100]}",
                        id_empresa,
                        id_bodega,
                        id_usuario
                    ))
                    
                    id_movimiento_salida = cursor.lastrowid
                    
                    # Registrar detalles de salida
                    for detalle in detalles:
                        cursor.execute("""
                            INSERT INTO Detalle_Movimientos_Inventario (
                                ID_Movimiento,
                                ID_Producto,
                                Cantidad,
                                Costo_Unitario,
                                Precio_Unitario,
                                Subtotal,
                                ID_Usuario_Creacion
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            id_movimiento_salida,
                            detalle['ID_Producto'],
                            -detalle['Cantidad'],
                            detalle['Costo_Unitario'],
                            0,
                            -detalle['Subtotal'],
                            id_usuario
                        ))
                
                # 6. Marcar movimiento original como anulado
                nueva_observacion = (
                    f"{movimiento['Observacion'] or ''}\n"
                    f"[ANULADA] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"por usuario {id_usuario}. Motivo: {motivo_anulacion}"
                )
                
                if len(nueva_observacion) > 65535:
                    nueva_observacion = nueva_observacion[:65530] + "..."
                
                cursor.execute("""
                    UPDATE Movimientos_Inventario 
                    SET Estado = 'Anulada',
                        ID_Usuario_Modificacion = %s,
                        Fecha_Modificacion = NOW(),
                        Observacion = %s
                    WHERE ID_Movimiento = %s
                """, (id_usuario, nueva_observacion, id_movimiento))
                
                # 7. Si es compra a crédito, actualizar cuenta por pagar
                if tipo_compra == 'CREDITO' and id_proveedor:
                    cursor.execute("""
                        UPDATE cuentas_por_pagar 
                        SET Saldo_Pendiente = 0,
                            Estado = 'Anulada',
                            Observacion = CONCAT(
                                COALESCE(Observacion, ''), 
                                ' | ANULADA ', 
                                DATE_FORMAT(NOW(), '%%d/%%m/%%Y %%H:%%i'), 
                                ' - Compra #', %s
                            )
                        WHERE ID_Movimiento = %s 
                        AND Saldo_Pendiente > 0
                    """, (id_movimiento, id_movimiento))
                
                # 8. Registrar en bitácora adicional
                try:
                    cursor.execute("""
                        INSERT INTO bitacora 
                        (ID_Usuario, Fecha, Modulo, Accion, IP_Acceso)
                        VALUES (%s, NOW(), 'COMPRAS', 'ANULACION_COMPRA', %s)
                    """, (id_usuario, request.remote_addr or '127.0.0.1'))
                except Exception as e:
                    print(f"Nota: No se pudo registrar en bitácora: {e}")
                
                # 9. Mensaje de éxito - CORREGIDO: Todo referente a "compra"
                info_contramovimiento = ""
                if id_movimiento_salida:
                    info_contramovimiento = f"<br>• Se generó contramovimiento de salida #{id_movimiento_salida}"
                
                mensaje = Markup(
                    f"✅ <strong>Compra anulada exitosamente</strong><br>"
                    f"• Número de compra: #{id_movimiento}<br>"
                    f"• Factura: {n_factura_externa or 'N/A'}<br>"
                    f"• Total compra: C${total_compra:,.2f}<br>"
                    f"• Productos reversados: {len(productos_reversados)}"
                    f"{info_contramovimiento}"
                )
                
                flash(mensaje, 'success')
            
            return redirect(url_for('admin_compras_entradas'))
            
        except Exception as e:
            print(f"Error al anular compra {id_movimiento}: {str(e)}")
            traceback.print_exc()
            flash(f'Error al anular compra: {str(e)}', 'error')
            return redirect(url_for('admin_compras_entradas'))
    
@app.route('/admin/compras/compras-entradas/detalle-completo/<int:id_movimiento>', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-ENTRADAS-DETALLE-COMPLETO")
def admin_detalle_compra_completo(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # CONSULTA PRINCIPAL CORREGIDA
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    mi.ID_TipoMovimiento,
                    mi.N_Factura_Externa,
                    mi.Fecha,
                    mi.ID_Proveedor,
                    p.Nombre as Proveedor,
                    p.RUC_CEDULA as RUC_Proveedor,
                    p.Direccion as Direccion_Proveedor,
                    p.Telefono as Telefono_Proveedor,
                    mi.Tipo_Compra,
                    mi.Observacion,
                    mi.ID_Bodega,
                    b.Nombre as Bodega,
                    b.Ubicacion as Direccion_Bodega,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.Fecha_Creacion,
                    u_mod.NombreUsuario as Usuario_Modificacion,
                    mi.Fecha_Modificacion,
                    mi.Estado,
                    (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Compra,
                    (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                     WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Productos
                FROM Movimientos_Inventario mi
                LEFT JOIN Proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN Bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN usuarios u_mod ON mi.ID_Usuario_Modificacion = u_mod.ID_Usuario
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash('Compra no encontrada', 'error')
                return redirect(url_for('admin_compras_entradas'))
            
            # DETALLES CORREGIDOS - SIN LOTE Y FECHA_VENCIMIENTO
            cursor.execute("""
                SELECT 
                    dmi.ID_Detalle_Movimiento,
                    dmi.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto_Desc,
                    COALESCE(ib.Existencias, 0) as Existencias_Actuales,
                    dmi.Cantidad,
                    dmi.Costo_Unitario,
                    dmi.Precio_Unitario,
                    dmi.Subtotal,
                    um.Descripcion as Unidad_Medida,
                    um.Abreviatura as Simbolo_Medida
                FROM detalle_movimientos_inventario dmi
                INNER JOIN Productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN Unidades_Medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON dmi.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (movimiento['ID_Bodega'], id_movimiento))
            
            detalles = cursor.fetchall()
            
            # CUENTAS POR PAGAR CORREGIDA
            cursor.execute("""
                SELECT 
                    ID_Cuenta,
                    Fecha_Vencimiento,
                    Monto_Movimiento,
                    Saldo_Pendiente
                FROM Cuentas_Por_Pagar 
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta_por_pagar = cursor.fetchone()
            
            # Calcular total de cantidad
            total_cantidad = sum([detalle['Cantidad'] for detalle in detalles]) if detalles else 0
            
            now = datetime.now().date()
            
            return render_template(
                'admin/compras/detalle_compra.html',
                movimiento=movimiento,
                detalles=detalles,
                cuenta_por_pagar=cuenta_por_pagar,
                total_cantidad=total_cantidad,
                now=now,
                title="Detalles de Compra"
            )
                                
    except Exception as e:
        print(f"Error al cargar detalle completo de compra: {str(e)}")
        flash(f'Error al cargar detalles: {str(e)}', 'error')
        return redirect(url_for('admin_compras_entradas'))

# CUENTAS POR PAGAR 
@app.route('/admin/compras/cxpagar/cuentas-por-pagar', methods=['GET'])
@admin_required
@bitacora_decorator("COMPRAS-CUENTAS-POR-PAGAR")
def admin_cuentas_por_pagar():
    try:
        # Obtener parámetro de filtro de estado
        filtro_estado = request.args.get('estado', 'Pendiente')
        
        with get_db_cursor(True) as cursor:
            # Construir consulta dinámica según filtro
            query = """
                SELECT 
                    cpp.ID_Cuenta,
                    cpp.Fecha,
                    cpp.ID_Proveedor,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    cpp.Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado,
                    u.NombreUsuario as Usuario_Creacion,
                    DATEDIFF(cpp.Fecha_Vencimiento, CURDATE()) as dias_vencimiento
                FROM Cuentas_Por_Pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON cpp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE 1=1
            """
            
            params = []
            
            # Aplicar filtro de estado
            if filtro_estado == 'Pendiente':
                query += " AND cpp.Estado = 'Pendiente' AND cpp.Saldo_Pendiente > 0"
            elif filtro_estado == 'Pagada':
                query += " AND cpp.Estado = 'Pagada'"
            elif filtro_estado == 'Anulada':
                query += " AND cpp.Estado = 'Anulada'"
            elif filtro_estado == 'Todas':
                # No aplicar filtro
                pass
                
            query += " ORDER BY cpp.Fecha_Vencimiento ASC"
            
            cursor.execute(query, params)
            cuentas = cursor.fetchall()
            
            # Calcular estadísticas solo para cuentas pendientes
            cuentas_pendientes = [c for c in cuentas if c['Estado'] == 'Pendiente']
            total_pendiente = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas_pendientes if cuenta['Saldo_Pendiente'])
            cuentas_vencidas = sum(1 for cuenta in cuentas_pendientes if cuenta['dias_vencimiento'] and cuenta['dias_vencimiento'] < 0)
            
            return render_template('admin/compras/cxpagar/cuentas_por_pagar.html', 
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 cuentas_vencidas=cuentas_vencidas,
                                 filtro_estado=filtro_estado,
                                 total_cuentas=len(cuentas))
    except Exception as e:
        print(f"Error al cargar cuentas por pagar: {str(e)}")
        flash(f'Error al cargar cuentas por pagar: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/compras/cuentas-por-pagar/pagar', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("COMPRAS-REGISTRAR-PAGO")
def registrar_pago_cuenta():
    try:
        if request.method == 'GET':
            # Cargar métodos de pago para el formulario
            with get_db_cursor(True) as cursor:
                cursor.execute("SELECT ID_MetodoPago, Nombre FROM metodos_pago ORDER BY Nombre")
                metodos_pago = cursor.fetchall()
                
                # Obtener información de la cuenta si se proporciona ID
                id_cuenta = request.args.get('id_cuenta')
                cuenta_info = None
                if id_cuenta:
                    cursor.execute("""
                        SELECT 
                            cpp.ID_Cuenta,
                            cpp.Saldo_Pendiente,
                            cpp.ID_Proveedor,
                            p.Nombre as Proveedor,
                            cpp.Num_Documento,
                            cpp.Monto_Movimiento,
                            cpp.Estado  -- NUEVO: Incluir el campo Estado
                        FROM Cuentas_Por_Pagar cpp
                        LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                        WHERE cpp.ID_Cuenta = %s
                        AND cpp.Estado = 'Pendiente'  -- NUEVO: Solo cuentas pendientes
                    """, (id_cuenta,))
                    cuenta_info = cursor.fetchone()
                    
                    # Validar que la cuenta existe y está pendiente
                    if not cuenta_info:
                        flash('Cuenta no encontrada o ya está pagada/anulada', 'error')
                        return redirect(url_for('admin_cuentas_por_pagar'))
                
                return render_template('admin/compras/cxpagar/registrar_pago.html',
                                     metodos_pago=metodos_pago,
                                     cuenta_info=cuenta_info)
        
        elif request.method == 'POST':
            # Procesar el pago
            id_cuenta = request.form['id_cuenta']
            monto_pago = float(request.form['monto_pago'])
            fecha_pago = request.form['fecha_pago']
            id_metodo_pago = request.form['id_metodo_pago']
            detalles_metodo = request.form.get('detalles_metodo', '')
            comentarios = request.form.get('comentarios_pago', '')
            id_usuario = session.get('user_id', 1)
            
            with get_db_cursor() as cursor:
                # Obtener información completa de la cuenta
                cursor.execute("""
                    SELECT 
                        cpp.Saldo_Pendiente,
                        cpp.ID_Proveedor,
                        p.Nombre as Proveedor,
                        cpp.Num_Documento,
                        cpp.Monto_Movimiento,
                        cpp.Estado,  -- NUEVO: Incluir el campo Estado
                        cpp.ID_Movimiento  -- Para referencia
                    FROM Cuentas_Por_Pagar cpp
                    LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                    WHERE cpp.ID_Cuenta = %s
                """, (id_cuenta,))
                
                cuenta = cursor.fetchone()
                
                if not cuenta:
                    flash('Cuenta no encontrada', 'error')
                    return redirect(url_for('admin_cuentas_por_pagar'))
                
                # NUEVO: Validar que la cuenta esté pendiente
                if cuenta['Estado'] != 'Pendiente':
                    flash(f'Esta cuenta ya está {cuenta["Estado"].lower()}. No se pueden registrar más pagos.', 'error')
                    return redirect(url_for('admin_cuentas_por_pagar'))
                
                saldo_actual = float(cuenta['Saldo_Pendiente'])
                proveedor = cuenta['Proveedor']
                num_documento = cuenta['Num_Documento']
                monto_total = float(cuenta['Monto_Movimiento'])
                
                # Validaciones
                if monto_pago <= 0:
                    flash('El monto a pagar debe ser mayor a cero', 'error')
                    return redirect(url_for('registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                if monto_pago > saldo_actual:
                    flash(f'El monto a pagar (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})', 'error')
                    return redirect(url_for('registrar_pago_cuenta', id_cuenta=id_cuenta))
                
                # Calcular nuevo saldo
                nuevo_saldo = saldo_actual - monto_pago
                
                # Determinar el nuevo estado
                nuevo_estado = 'Pagada' if nuevo_saldo == 0 else 'Pendiente'
                
                # Registrar el pago en la tabla pagos_cuentaspagar
                cursor.execute("""
                    INSERT INTO pagos_cuentaspagar 
                    (ID_Cuenta, Fecha, Monto, ID_MetodoPago, Detalles_Metodo, Comentarios, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (id_cuenta, f"{fecha_pago} 00:00:00", monto_pago, id_metodo_pago, 
                      detalles_metodo, comentarios, id_usuario))
                
                # Actualizar saldo pendiente y estado en la cuenta
                cursor.execute("""
                    UPDATE Cuentas_Por_Pagar 
                    SET Saldo_Pendiente = %s,
                        Estado = %s  -- NUEVO: Actualizar el estado
                    WHERE ID_Cuenta = %s
                """, (nuevo_saldo, nuevo_estado, id_cuenta))
                
                # Mensaje de éxito
                if nuevo_saldo == 0:
                    mensaje = f'¡Cuenta completamente pagada! Se registró pago de ${monto_pago:,.2f} para {proveedor}.'
                else:
                    mensaje = f'Pago de ${monto_pago:,.2f} registrado correctamente para {proveedor}. Saldo restante: ${nuevo_saldo:,.2f}'
                
                flash(mensaje, 'success')
                return redirect(url_for('admin_cuentas_por_pagar'))
                
    except Exception as e:
        print(f"Error al registrar pago: {str(e)}")
        flash(f'Error al registrar pago: {str(e)}', 'error')
        return redirect(url_for('admin_cuentas_por_pagar'))

# Ruta para ver historial de pagos de una cuenta
@app.route('/admin/compras/cuentas-por-pagar/<int:id_cuenta>/pagos', methods=['GET'])
@admin_required
def historial_pagos_cuenta(id_cuenta):
    """Muestra el historial de pagos de una cuenta específica"""
    try:
        with get_db_cursor(True) as cursor:
            # 1. Obtener información básica de la cuenta
            cursor.execute("""
                SELECT 
                    cpp.ID_Cuenta,
                    DATE(cpp.Fecha) as Fecha,
                    p.Nombre as Proveedor,
                    cpp.Num_Documento,
                    cpp.Observacion,
                    DATE(cpp.Fecha_Vencimiento) as Fecha_Vencimiento,
                    cpp.Monto_Movimiento,
                    cpp.Saldo_Pendiente,
                    cpp.Estado
                FROM cuentas_por_pagar cpp
                LEFT JOIN Proveedores p ON cpp.ID_Proveedor = p.ID_Proveedor
                WHERE cpp.ID_Cuenta = %s
            """, (id_cuenta,))
            
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash('Cuenta no encontrada', 'error')
                return redirect(url_for('admin_cuentas_por_pagar'))
            
            # 2. Obtener historial de pagos (ajustado a tu estructura)
            cursor.execute("""
                SELECT 
                    pcp.ID_Pago,
                    DATE(pcp.Fecha) as Fecha_Pago,
                    TIME(pcp.Fecha) as Hora_Pago,
                    pcp.Monto,
                    mp.Nombre as Metodo_Pago,
                    pcp.Detalles_Metodo,
                    pcp.Comentarios,
                    u.NombreUsuario as Usuario_Registro
                FROM pagos_cuentaspagar pcp
                LEFT JOIN metodos_pago mp ON pcp.ID_MetodoPago = mp.ID_MetodoPago
                LEFT JOIN usuarios u ON pcp.ID_Usuario_Creacion = u.ID_Usuario
                WHERE pcp.ID_Cuenta = %s
                ORDER BY pcp.Fecha DESC
            """, (id_cuenta,))
            
            pagos = cursor.fetchall()
            
            # 3. Calcular total pagado
            total_pagado = 0.0
            for pago in pagos:
                if pago['Monto']:
                    total_pagado += float(pago['Monto'])
            
            # 4. Renderizar template
            return render_template('admin/compras/cxpagar/historial_pagos.html', 
                                cuenta=cuenta,
                                pagos=pagos,
                                total_pagado=total_pagado,
                                total_cuenta=float(cuenta['Monto_Movimiento']) if cuenta['Monto_Movimiento'] else 0.0)
            
    except Exception as e:
        print(f"Error al cargar historial de pagos (ID: {id_cuenta}): {str(e)}")
        flash(f'Error al cargar historial de pagos: {str(e)}', 'error')
        return redirect(url_for('admin_cuentas_por_pagar'))

#MODULO VENTAS
@app.route('/admin/ventas/ventas-salidas', methods=['GET'])
@admin_required
@bitacora_decorator("VENTAS-SALIDAS")
def admin_ventas_salidas():
    try:
        # Obtener parámetro de filtro si existe
        estado_filtro = request.args.get('estado', 'todas').upper()
        
        with get_db_cursor(True) as cursor:
            # Construir la condición WHERE según el filtro
            where_condition = ""
            if estado_filtro == 'ACTIVAS':
                where_condition = "WHERE f.Estado = 'Activa'"
            elif estado_filtro == 'ANULADAS':
                where_condition = "WHERE f.Estado = 'Anulada'"
            
            # Usar subconsulta para obtener solo el movimiento más reciente de cada venta
            cursor.execute(f"""
                SELECT 
                    f.ID_Factura,
                    f.Fecha,
                    f.Observacion,
                    f.ID_Usuario_Creacion,
                    f.Credito_Contado,
                    f.Estado as Estado_Factura,  -- ¡Importante: usar el estado de factura!
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.ID_Movimiento,
                    mi.Tipo_Compra,
                    mi.Estado as Estado_Movimiento,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento,
                    (SELECT COUNT(*) FROM Detalle_Facturacion df 
                     WHERE df.ID_Factura = f.ID_Factura) as Total_Productos,
                    COALESCE((SELECT SUM(Total) FROM Detalle_Facturacion df 
                     WHERE df.ID_Factura = f.ID_Factura), 0) as Total_Venta,
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        WHEN f.Credito_Contado = 0 THEN 'CONTADO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado,
                    -- Estado formateado para mostrar (usando factura, no movimiento)
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 'ACTIVA'
                        WHEN f.Estado = 'Anulada' THEN 'ANULADA'
                        ELSE UPPER(f.Estado)
                    END as Estado_Formateado,
                    -- Agregar clase CSS para colorear según estado
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 'badge-success'
                        WHEN f.Estado = 'Anulada' THEN 'badge-danger'
                        ELSE 'badge-secondary'
                    END as Estado_Clase,
                    (SELECT COUNT(*) FROM Cuentas_Por_Cobrar cpc 
                     WHERE cpc.ID_Factura = f.ID_Factura 
                     AND cpc.Estado IN ('Pendiente', 'Vencida')) as Tiene_Credito_Pendiente
                FROM Facturacion f
                LEFT JOIN Clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                -- Obtener solo el movimiento más reciente para cada factura
                LEFT JOIN (
                    SELECT mi1.*
                    FROM Movimientos_Inventario mi1
                    INNER JOIN (
                        SELECT ID_Factura_Venta, MAX(Fecha_Creacion) as Ultima_Fecha
                        FROM Movimientos_Inventario 
                        WHERE ID_Factura_Venta IS NOT NULL
                        GROUP BY ID_Factura_Venta
                    ) mi2 ON mi1.ID_Factura_Venta = mi2.ID_Factura_Venta 
                          AND mi1.Fecha_Creacion = mi2.Ultima_Fecha
                ) mi ON f.ID_Factura = mi.ID_Factura_Venta
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                {where_condition}
                ORDER BY f.Fecha DESC, f.ID_Factura DESC
            """)
            ventas = cursor.fetchall()
            
            # Obtener estadísticas por estado para mostrar en los filtros (usando factura)
            cursor.execute("""
                SELECT 
                    f.Estado,
                    COUNT(*) as cantidad,
                    COALESCE(SUM(df.Total), 0) as total_monto
                FROM Facturacion f
                LEFT JOIN Detalle_Facturacion df ON f.ID_Factura = df.ID_Factura
                GROUP BY f.Estado
            """)
            estadisticas_estado = cursor.fetchall()
            
            # Calcular estadísticas de forma segura
            total_ventas = len(ventas)
            ventas_contado = sum(1 for v in ventas if v.get('Credito_Contado') == 0)
            ventas_credito = sum(1 for v in ventas if v.get('Credito_Contado') == 1)
            ventas_activas = sum(1 for v in ventas if v.get('Estado_Factura') == 'Activa')
            ventas_anuladas = sum(1 for v in ventas if v.get('Estado_Factura') == 'Anulada')
            
            # Manejar valores None en Total_Venta
            monto_total = 0
            for v in ventas:
                total_venta = v.get('Total_Venta')
                if total_venta is not None:
                    try:
                        monto_total += float(total_venta)
                    except (TypeError, ValueError):
                        monto_total += 0
            
            return render_template('admin/ventas/ventas_salidas.html', 
                                 ventas=ventas,
                                 total_ventas=total_ventas,
                                 ventas_contado=ventas_contado,
                                 ventas_credito=ventas_credito,
                                 ventas_activas=ventas_activas,
                                 ventas_anuladas=ventas_anuladas,
                                 monto_total=monto_total,
                                 estado_filtro=estado_filtro,
                                 estadisticas_estado=estadisticas_estado)
    except Exception as e:
        flash(f'Error al cargar ventas: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/ventas/crear', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("CREAR_VENTA")
def admin_crear_venta():
    try:
        # Obtener ID de empresa y usuario desde la sesión
        id_empresa = session.get('id_empresa',1)
        id_usuario = current_user.id
        
        if not id_empresa:
            flash('No se pudo determinar la empresa', 'error')
            return redirect(url_for('admin_ventas_salidas'))
        
        if not id_usuario:
            flash('Usuario no autenticado', 'error')
            return redirect(url_for('admin_ventas_salidas'))

        with get_db_cursor(True) as cursor:
            # Obtener el ID_TipoMovimiento para VENTAS
            cursor.execute("""
                SELECT ID_TipoMovimiento, Descripcion, Letra 
                FROM catalogo_movimientos 
                WHERE Descripcion LIKE '%Venta%' OR Letra = 'S' 
                LIMIT 1
            """)
            tipo_movimiento = cursor.fetchone()
            
            if not tipo_movimiento:
                flash('Error: No se encontró el tipo de movimiento para ventas en el catálogo', 'error')
                return redirect(url_for('admin_ventas_salidas'))
            
            id_tipo_movimiento = tipo_movimiento['ID_TipoMovimiento']
            
            # Obtener datos para el formulario
            cursor.execute("""
                SELECT ID_Cliente, Nombre, RUC_CEDULA 
                FROM clientes 
                WHERE Estado = 'ACTIVO' AND (ID_Empresa = %s OR ID_Empresa IS NULL)
                ORDER BY Nombre
            """, (id_empresa,))
            clientes = cursor.fetchall()
            
            # Obtener bodega principal
            cursor.execute("SELECT ID_Bodega, Nombre FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_principal = cursor.fetchone()
            if not bodega_principal:
                flash('Error: No hay bodegas activas en el sistema', 'error')
                return redirect(url_for('admin_ventas_salidas'))
            
            id_bodega_principal = bodega_principal['ID_Bodega']
            
            # Obtener categorías de productos
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            # Obtener productos SOLO de la bodega principal
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    COALESCE(ib.Existencias, 0) as Existencias,
                    COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                    p.ID_Categoria,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                WHERE p.Estado = 1 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega_principal, id_empresa))
            productos = cursor.fetchall()
            
            # Obtener datos de la empresa
            cursor.execute("SELECT Nombre_Empresa, RUC, Direccion, Telefono FROM empresa WHERE ID_Empresa = %s", (id_empresa,))
            empresa_data = cursor.fetchone()

        # Si es POST, procesar el formulario
        if request.method == 'POST':
            print("📨 Iniciando procesamiento de venta...")
            
            # Obtener datos del formulario
            id_cliente = request.form.get('id_cliente','').strip()
            tipo_venta = request.form.get('tipo_venta')
            observacion = request.form.get('observacion', '')
            
            # Obtener productos del formulario
            productos_ids = request.form.getlist('producto_id[]')
            cantidades = request.form.getlist('cantidad[]')
            precios = request.form.getlist('precio[]')
            
            print(f"Datos recibidos - Cliente: {id_cliente}, Tipo: {tipo_venta}")
            print(f"Productos recibidos: {len(productos_ids)}")
            
            # Validaciones básicas
            if not id_cliente or not tipo_venta:
                error_msg = 'Cliente y tipo de venta son obligatorios'
                print(f"❌ {error_msg}")
                flash(error_msg, 'error')
                return render_template('admin/ventas/crear_venta.html',
                                    clientes=clientes,
                                    bodega_principal=bodega_principal,
                                    productos=productos,
                                    categorias=categorias,
                                    empresa=empresa_data,
                                    id_tipo_movimiento=id_tipo_movimiento)
            
            if not productos_ids or len(productos_ids) == 0:
                error_msg = 'Debe agregar al menos un producto a la venta'
                print(f"❌ {error_msg}")
                flash(error_msg, 'error')
                return render_template('admin/ventas/crear_venta.html',
                                    clientes=clientes,
                                    bodega_principal=bodega_principal,
                                    productos=productos,
                                    categorias=categorias,
                                    empresa=empresa_data,
                                    id_tipo_movimiento=id_tipo_movimiento)

            # Usar otro contexto para la transacción de la venta
            with get_db_cursor(True) as cursor:
                # 1. Crear factura
                cursor.execute("""
                    INSERT INTO Facturacion (
                        Fecha, IDCliente, Credito_Contado, Observacion, 
                        ID_Empresa, ID_Usuario_Creacion
                    )
                    VALUES (CURDATE(), %s, %s, %s, %s, %s)
                """, (
                    id_cliente,
                    1 if tipo_venta == 'credito' else 0,
                    observacion,
                    id_empresa,
                    id_usuario
                ))
                
                # Obtener el ID de la factura recién insertada
                cursor.execute("SELECT LAST_INSERT_ID() as id_factura")
                id_factura = cursor.fetchone()['id_factura']
                print(f"🧾 Factura creada: #{id_factura}")
                
                total_venta = 0
                
                # 2. Procesar productos y crear detalles de facturación
                for i in range(len(productos_ids)):
                    id_producto = productos_ids[i]
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    precio = float(precios[i]) if precios[i] else 0
                    
                    if cantidad <= 0 or precio <= 0:
                        continue
                    
                    total_linea = cantidad * precio
                    total_venta += total_linea
                    
                    # Obtener datos del producto para validación
                    cursor.execute("SELECT COD_Producto, Descripcion FROM productos WHERE ID_Producto = %s", (id_producto,))
                    producto_data = cursor.fetchone()
                    
                    if not producto_data:
                        raise Exception(f"Producto con ID {id_producto} no encontrado")
                    
                    # Verificar stock disponible en la BODEGA PRINCIPAL
                    cursor.execute("""
                        SELECT COALESCE(Existencias, 0) as Stock 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega_principal, id_producto))
                    
                    stock = cursor.fetchone()
                    stock_actual = stock['Stock'] if stock else 0
                    
                    if stock_actual < cantidad:
                        raise Exception(f'Stock insuficiente para: {producto_data["Descripcion"]}. Stock actual: {stock_actual}')
                    
                    # Insertar detalle de facturación
                    cursor.execute("""
                        INSERT INTO Detalle_Facturacion (
                            ID_Factura, ID_Producto, Cantidad, Costo, Total
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (id_factura, id_producto, cantidad, precio, total_linea))
                    
                    # Actualizar inventario en la BODEGA PRINCIPAL
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_principal, id_producto))
                    
                    print(f" Producto {id_producto}: {cantidad} x C${precio} = C${total_linea}")
                
                print(f"Total venta: C${total_venta:,.2f}")
                
                # 3. Registrar movimiento de inventario (VENTA)
                cursor.execute("""
                    INSERT INTO Movimientos_Inventario (
                        ID_TipoMovimiento, ID_Bodega, Fecha, Tipo_Compra,
                        Observacion, ID_Empresa, ID_Usuario_Creacion, Estado,
                        ID_Factura_Venta
                    )
                    VALUES (%s, %s, CURDATE(), %s, %s, %s, %s, 1, %s)
                """, (
                    id_tipo_movimiento,
                    id_bodega_principal,
                    'CREDITO' if tipo_venta == 'credito' else 'CONTADO',
                    observacion or 'Venta realizada',
                    id_empresa,
                    id_usuario,
                    id_factura
                ))
                
                # Obtener el ID del movimiento de inventario
                cursor.execute("SELECT LAST_INSERT_ID() as id_movimiento")
                id_movimiento = cursor.fetchone()['id_movimiento']
                print(f"📋 Movimiento de inventario creado: #{id_movimiento}")
                
                # 4. Insertar detalles del movimiento de inventario (CORREGIDA)
                for i in range(len(productos_ids)):
                    id_producto = productos_ids[i]
                    cantidad = float(cantidades[i]) if cantidades[i] else 0
                    precio = float(precios[i]) if precios[i] else 0
                    
                    if cantidad <= 0 or precio <= 0:
                        continue
                    
                    # Obtener información adicional del producto
                    cursor.execute("""
                        SELECT COD_Producto, Descripcion 
                        FROM productos 
                        WHERE ID_Producto = %s
                    """, (id_producto,))
                    producto_info = cursor.fetchone()
                    
                    subtotal = cantidad * precio
                    
                    # CORRECCIÓN: Insertar detalle del movimiento de inventario con la nueva estructura
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, ID_Producto, Cantidad, 
                            Costo_Unitario, Precio_Unitario, Subtotal,
                            ID_Usuario_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento,
                        id_producto,
                        cantidad,
                        precio,  # Costo_Unitario
                        precio,  # Precio_Unitario
                        subtotal,
                        id_usuario
                    ))
                    print(f"  Detalle movimiento creado para producto: {producto_info['COD_Producto']}")
                
                # 5. Si es crédito, crear cuenta por cobrar
                if tipo_venta == 'credito':
                    cursor.execute("""
                        INSERT INTO Cuentas_Por_Cobrar (
                            Fecha, ID_Cliente, Num_Documento, Observacion,
                            Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                            ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion
                        )
                        VALUES (CURDATE(), %s, %s, %s, DATE_ADD(CURDATE(), INTERVAL 30 DAY), 
                                1, %s, %s, %s, %s, %s)
                    """, (
                        id_cliente,
                        f'FAC-{id_factura:05d}',
                        observacion or 'Venta a crédito',
                        total_venta,
                        id_empresa,
                        total_venta,
                        id_factura,
                        id_usuario
                    ))
                    print(f"💳 Cuenta por cobrar creada para factura #{id_factura}")
                
                success_msg = f'✅ Venta creada exitosamente! Factura # {id_factura} - Total: C${total_venta:,.2f}'
                print(f"🎯 {success_msg}")
                flash(success_msg, 'success')
                
                # Retornar JSON en lugar de redirección para manejar mejor el frontend
                return jsonify({
                    'success': True,
                    'message': success_msg,
                    'id_factura': id_factura,
                    'total_venta': total_venta,
                    'redirect_url': url_for('admin_generar_ticket', id_factura=id_factura)
                })
        
        # Si es GET, mostrar el formulario
        return render_template('admin/ventas/crear_venta.html',
                            clientes=clientes,
                            bodega_principal=bodega_principal,
                            productos=productos,
                            categorias=categorias,
                            empresa=empresa_data,
                            id_tipo_movimiento=id_tipo_movimiento)
            
    except Exception as e:
        error_msg = f' Error al procesar venta: {str(e)}'
        print(f"{error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Si es POST, retornar error en JSON
        if request.method == 'POST':
            return jsonify({
                'success': False,
                'error': error_msg
            }), 500
        
        # Si es GET, mostrar error normal
        flash(error_msg, 'error')
        return render_template('admin/ventas/crear_venta.html',
                            clientes=clientes if 'clientes' in locals() else [],
                            bodega_principal=bodega_principal if 'bodega_principal' in locals() else None,
                            productos=productos if 'productos' in locals() else [],
                            categorias=categorias if 'categorias' in locals() else [],
                            empresa=empresa_data if 'empresa_data' in locals() else None,
                            id_tipo_movimiento=id_tipo_movimiento if 'id_tipo_movimiento' in locals() else None)
      
# RUTAS AUXILIARES SIMPLIFICADAS - UNA SOLA BODEGA
@app.route('/admin/ventas/productos-por-categoria/<int:id_categoria>')
@admin_required
def obtener_productos_por_categoria_venta(id_categoria):
    """
    Endpoint para obtener productos filtrados por categoría - UNA SOLA BODEGA
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [VENTAS] Filtrando productos - Categoría: {id_categoria}, Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            if id_categoria == 0:  # Todas las categorías
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion, 
                        COALESCE(ib.Existencias, 0) as Existencias,
                        COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                        p.ID_Categoria,
                        c.Descripcion as Categoria
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                    WHERE p.Estado = 1 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    AND COALESCE(ib.Existencias, 0) > 0
                    ORDER BY c.Descripcion, p.Descripcion
                """, (id_bodega, id_empresa))
            else:
                cursor.execute("""
                    SELECT 
                        p.ID_Producto, 
                        p.COD_Producto, 
                        p.Descripcion, 
                        COALESCE(ib.Existencias, 0) as Existencias,
                        COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                        p.ID_Categoria,
                        c.Descripcion as Categoria
                    FROM productos p
                    LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                    LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                    WHERE p.Estado = 1 
                    AND p.ID_Categoria = %s 
                    AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                    AND COALESCE(ib.Existencias, 0) > 0
                    ORDER BY p.Descripcion
                """, (id_bodega, id_categoria, id_empresa))
            
            productos = cursor.fetchall()
            print(f"✅ [VENTAS] Productos encontrados: {len(productos)} para categoría {id_categoria}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'id': producto['ID_Producto'],
                    'codigo': producto['COD_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': float(producto['Existencias']),
                    'precio_venta': float(producto['Precio_Venta']),
                    'id_categoria': producto['ID_Categoria'],
                    'categoria': producto['Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ [VENTAS] Error al obtener productos por categoría: {str(e)}")
        import traceback
        print(f"❌ [VENTAS] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/ventas/verificar-stock/<int:id_producto>')
@admin_required
def verificar_stock_producto(id_producto):
    """
    Endpoint para verificar stock en tiempo real - UNA SOLA BODEGA
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [STOCK] Verificando stock - Producto: {id_producto}, Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Producto,
                    p.Descripcion,
                    COALESCE(ib.Existencias, 0) as Existencias,
                    b.Nombre as Bodega
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                LEFT JOIN bodegas b ON ib.ID_Bodega = b.ID_Bodega
                WHERE p.ID_Producto = %s 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND p.Estado = 1
            """, (id_bodega, id_producto, id_empresa))
            
            producto = cursor.fetchone()
            
            if producto:
                stock = float(producto['Existencias'])
                print(f"✅ [STOCK] Producto {id_producto}: {stock} unidades en {producto['Bodega']}")
                
                return jsonify({
                    'id_producto': producto['ID_Producto'],
                    'descripcion': producto['Descripcion'],
                    'existencias': stock,
                    'bodega': producto['Bodega']
                })
            else:
                print(f"❌ [STOCK] Producto {id_producto} no encontrado en bodega {id_bodega}")
                return jsonify({'error': 'Producto no encontrado'}), 404
                
    except Exception as e:
        print(f"❌ [STOCK] Error al verificar stock: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/ventas/categorias-productos')
@admin_required
def obtener_categorias_productos_venta():
    """
    Endpoint para obtener todas las categorías
    """
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Categoria, Descripcion 
                FROM categorias_producto 
                ORDER BY Descripcion
            """)
            categorias = cursor.fetchall()
            
            categorias_list = []
            for categoria in categorias:
                categorias_list.append({
                    'id': categoria['ID_Categoria'],
                    'descripcion': categoria['Descripcion']
                })
            
            return jsonify(categorias_list)
            
    except Exception as e:
        print(f"❌ [VENTAS] Error al obtener categorías: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/ventas/bodega-principal')
@admin_required
def obtener_bodega_principal():
    """
    Endpoint para obtener la bodega principal
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT ID_Bodega, Nombre 
                FROM bodegas 
                WHERE Estado = 1 
                AND (ID_Empresa = %s OR ID_Empresa IS NULL)
                ORDER BY ID_Bodega 
                LIMIT 1
            """, (id_empresa,))
            
            bodega = cursor.fetchone()
            
            if bodega:
                return jsonify({
                    'id_bodega': bodega['ID_Bodega'],
                    'nombre': bodega['Nombre']
                })
            else:
                return jsonify({'error': 'No hay bodegas activas'}), 404
                
    except Exception as e:
        print(f"❌ [BODEGA] Error al obtener bodega principal: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/ventas/ticket/<int:id_factura>')
@admin_required
def admin_generar_ticket(id_factura):
    try:
        with get_db_cursor(True) as cursor:
            # Obtener datos de la factura desde la base de datos
            cursor.execute("""
                SELECT 
                    f.ID_Factura,
                    f.Fecha,
                    f.Observacion,
                    f.Credito_Contado,
                    f.ID_Usuario_Creacion,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    u.NombreUsuario as Usuario,
                    e.ID_Empresa,
                    COALESCE(e.Nombre_Empresa, 'MI EMPRESA') as Nombre_Empresa,
                    COALESCE(e.RUC, 'RUC NO CONFIGURADO') as RUC_Empresa,
                    COALESCE(e.Direccion, '') as Direccion_Empresa,
                    COALESCE(e.Telefono, '') as Telefono_Empresa,
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado
                FROM Facturacion f
                LEFT JOIN Clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa e ON f.ID_Empresa = e.ID_Empresa
                WHERE f.ID_Factura = %s
            """, (id_factura,))
            factura = cursor.fetchone()
            
            if not factura:
                flash('Factura no encontrada', 'error')
                return redirect(url_for('admin_ventas_salidas'))
            
            # Obtener detalles de la factura
            cursor.execute("""
                SELECT 
                    df.ID_Detalle,
                    df.Cantidad,
                    df.Costo as Precio,
                    df.Total as Subtotal,
                    p.ID_Producto,
                    COALESCE(p.COD_Producto, 'N/A') as COD_Producto,
                    COALESCE(p.Descripcion, 'PRODUCTO ELIMINADO') as Producto,
                    cat.Descripcion as Categoria
                FROM Detalle_Facturacion df
                LEFT JOIN Productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
                WHERE df.ID_Factura = %s
                ORDER BY df.ID_Detalle
            """, (id_factura,))
            detalles = cursor.fetchall()
            
            # Verificar que hay detalles
            if not detalles:
                flash('La factura no tiene detalles de productos', 'error')
                return redirect(url_for('admin_ventas_salidas'))
            
            # Calcular total
            total_venta = sum(float(detalle['Subtotal'] or 0) for detalle in detalles)
            
            # Obtener información del movimiento de inventario
            cursor.execute("""
                SELECT 
                    mi.ID_Movimiento,
                    b.Nombre as Bodega,
                    cm.Descripcion as Tipo_Movimiento
                FROM Movimientos_Inventario mi
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.ID_Factura_Venta = %s
            """, (id_factura,))
            movimiento = cursor.fetchone()
            
            # Verificar si tiene cuenta por cobrar
            cursor.execute("""
                SELECT 
                    Saldo_Pendiente,
                    Fecha_Vencimiento
                FROM Cuentas_Por_Cobrar 
                WHERE ID_Factura = %s AND Saldo_Pendiente > 0
            """, (id_factura,))
            cuenta_cobrar = cursor.fetchone()
            
            # Obtener hora exacta actual para el ticket
            hora_emision = datetime.now()
            
            # Preparar datos para el ticket
            ticket_data = {
                'id_factura': factura['ID_Factura'],
                'fecha': factura['Fecha'],  # Fecha original de la factura
                'hora_emision': hora_emision,  # Hora exacta de emisión del ticket
                'cliente': factura['Cliente'] or 'Consumidor Final',
                'ruc_cliente': factura['RUC_Cliente'] or 'Consumidor Final',
                'tipo_venta': factura['Tipo_Venta_Formateado'],
                'observacion': factura['Observacion'],
                'usuario': factura['Usuario'] or 'Usuario No Especificado',
                'detalles': detalles,
                'total': total_venta,
                'empresa': {
                    'nombre': factura['Nombre_Empresa'],
                    'ruc': factura['RUC_Empresa'],
                    'direccion': factura['Direccion_Empresa'],
                    'telefono': factura['Telefono_Empresa']
                },
                'movimiento': movimiento,
                'tiene_credito': cuenta_cobrar is not None,
                'cuenta_cobrar': cuenta_cobrar
            }
            
            return render_template('admin/ventas/ticket_venta.html', 
                                 ticket=ticket_data)
                             
    except Exception as e:
        flash(f'Error al generar ticket: {str(e)}', 'error')
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin_ventas_salidas'))

@app.route('/admin/ventas/todos-productos')
@admin_required
def obtener_todos_productos_venta():
    """
    Endpoint para obtener TODOS los productos activos con stock
    """
    try:
        id_empresa = session.get('id_empresa', 1)
        
        # Obtener la bodega principal
        with get_db_cursor(True) as cursor:
            cursor.execute("SELECT ID_Bodega FROM bodegas WHERE Estado = 1 ORDER BY ID_Bodega LIMIT 1")
            bodega_result = cursor.fetchone()
            id_bodega = bodega_result['ID_Bodega'] if bodega_result else 1
        
        print(f"🔍 [VENTAS] Cargando TODOS los productos - Bodega: {id_bodega}")
        
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    COALESCE(ib.Existencias, 0) as Existencias,
                    COALESCE(p.Precio_Venta, 0) as Precio_Venta, 
                    p.ID_Categoria,
                    c.Descripcion as Categoria
                FROM productos p
                LEFT JOIN categorias_producto c ON p.ID_Categoria = c.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto AND ib.ID_Bodega = %s
                WHERE p.Estado = 1 
                AND (p.ID_Empresa = %s OR p.ID_Empresa IS NULL)
                AND COALESCE(ib.Existencias, 0) > 0
                ORDER BY c.Descripcion, p.Descripcion
            """, (id_bodega, id_empresa))
            
            productos = cursor.fetchall()
            print(f"✅ [VENTAS] Total productos encontrados: {len(productos)}")
            
            productos_list = []
            for producto in productos:
                productos_list.append({
                    'ID_Producto': producto['ID_Producto'],
                    'COD_Producto': producto['COD_Producto'],
                    'Descripcion': producto['Descripcion'],
                    'Existencias': float(producto['Existencias']),
                    'Precio_Venta': float(producto['Precio_Venta']),
                    'ID_Categoria': producto['ID_Categoria'],
                    'Categoria': producto['Categoria']
                })
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"❌ [VENTAS] Error al obtener todos los productos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/ventas/detalles/<int:id_factura>', methods=['GET'])
@admin_required
@bitacora_decorator("DETALLES_VENTA")
def admin_detalles_venta(id_factura):
    try:
        # Obtener ID de empresa desde la sesión
        id_empresa = session.get('id_empresa', 1)
        
        with get_db_cursor(True) as cursor:
            # 1. Obtener información general de la factura - VERSIÓN CORREGIDA
            cursor.execute("""
                SELECT 
                    f.ID_Factura,
                    DATE_FORMAT(f.Fecha, '%d/%m/%Y') as Fecha_Formateada, 
                    f.Fecha as Fecha_Original,
                    f.Observacion,
                    f.ID_Usuario_Creacion,
                    f.Credito_Contado,
                    f.Estado as Estado_Factura,
                    f.ID_Empresa,
                    c.ID_Cliente,
                    c.Nombre as Cliente,
                    c.RUC_CEDULA as RUC_Cliente,
                    c.Direccion as Direccion_Cliente,
                    c.Telefono as Telefono_Cliente,
                    u.NombreUsuario as Usuario_Creacion,
                    mi.ID_Movimiento,
                    mi.Estado as Estado_Movimiento,
                    mi.ID_Bodega,
                    COALESCE(b.Nombre, 'BODEGA PRINCIPAL') as Bodega,
                    e.Nombre_Empresa,
                    e.RUC as RUC_Empresa,
                    e.Direccion as Direccion_Empresa,
                    e.Telefono as Telefono_Empresa,
                    -- Formatear tipo de venta (CORRECTO - usa facturacion.Credito_Contado)
                    CASE 
                        WHEN f.Credito_Contado = 1 THEN 'CRÉDITO'
                        ELSE 'CONTADO'
                    END as Tipo_Venta_Formateado,
                    -- Campo adicional para compatibilidad
                    f.Credito_Contado as Tipo_Venta_Numerico,
                    -- Estado de factura (varias versiones para compatibilidad)
                    f.Estado as Estado_Factura,  -- 'Activa'/'Anulada'
                    UPPER(f.Estado) as Estado_Factura_Formateado,  -- 'ACTIVA'/'ANULADA'
                    CASE 
                        WHEN f.Estado = 'Activa' THEN 1
                        ELSE 0
                    END as Estado_Factura_Numerico,
                    -- Estado del movimiento (varias versiones para compatibilidad)
                    COALESCE(mi.Estado, 'NO APLICA') as Estado_Movimiento_Formateado,  -- 'Activa'/'Anulada'/'NO APLICA'
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 'ACTIVO'
                        WHEN mi.Estado = 'Anulada' THEN 'ANULADO'
                        ELSE 'NO APLICA'
                    END as Estado_Movimiento_Mayusculas,
                    CASE 
                        WHEN mi.Estado = 'Activa' THEN 1
                        WHEN mi.Estado = 'Anulada' THEN 0
                        ELSE -1
                    END as Estado_Movimiento_Numerico,
                    -- Calcular total de la factura
                    (SELECT COALESCE(SUM(Total), 0) 
                     FROM detalle_facturacion 
                     WHERE ID_Factura = f.ID_Factura) as Total_Factura,
                    -- Obtener tipo de movimiento si existe
                    cm.Descripcion as Tipo_Movimiento
                FROM facturacion f
                LEFT JOIN Clientes c ON f.IDCliente = c.ID_Cliente
                LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa e ON f.ID_Empresa = e.ID_Empresa
                LEFT JOIN movimientos_inventario mi ON mi.ID_Factura_Venta = f.ID_Factura
                LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE f.ID_Factura = %s 
                  AND f.ID_Empresa = %s
                LIMIT 1
            """, (id_factura, id_empresa))
            
            factura = cursor.fetchone()
            
            if not factura:
                flash('Factura no encontrada o no pertenece a su empresa', 'error')
                return redirect(url_for('admin_ventas_salidas'))
            
            # 2. Obtener detalles de los productos vendidos - VERSIÓN CORREGIDA
            cursor.execute("""
                SELECT 
                    df.ID_Detalle,
                    df.ID_Producto,
                    p.COD_Producto,
                    p.Descripcion as Producto,
                    df.Cantidad,
                    df.Costo as Precio_Unitario,
                    df.Total as Subtotal,
                    cat.Descripcion as Categoria,
                    COALESCE(
                        (SELECT Descripcion 
                         FROM unidades_medida um 
                         WHERE um.ID_Unidad = p.Unidad_Medida),
                        'UNIDAD'
                    ) as Unidad_Medida,
                    -- Obtener existencia actual en la bodega de la venta
                    COALESCE(
                        (SELECT Existencias 
                         FROM inventario_bodega ib
                         WHERE ib.ID_Producto = p.ID_Producto 
                           AND ib.ID_Bodega = %s),
                        0
                    ) as Existencia_Actual,
                    -- Obtener cantidad del movimiento (si existe)
                    COALESCE(
                        (SELECT dmi.Cantidad 
                         FROM detalle_movimientos_inventario dmi
                         WHERE dmi.ID_Producto = p.ID_Producto
                           AND dmi.ID_Movimiento = %s),
                        df.Cantidad
                    ) as Cantidad_Movimiento
                FROM detalle_facturacion df
                INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                LEFT JOIN categorias_producto cat ON p.ID_Categoria = cat.ID_Categoria
                WHERE df.ID_Factura = %s
                ORDER BY df.ID_Detalle
            """, (factura['ID_Bodega'] or 1, factura['ID_Movimiento'], id_factura))
            
            detalles = cursor.fetchall()
            
            # 3. Calcular totales
            total_productos = len(detalles)
            total_venta = sum(float(detalle.get('Subtotal', 0)) for detalle in detalles)
            
            # 4. Verificar si tiene crédito pendiente
            cursor.execute("""
                SELECT 
                    COUNT(*) as Tiene_Credito_Pendiente,
                    COALESCE(SUM(Saldo_Pendiente), 0) as Saldo_Pendiente_Total,
                    GROUP_CONCAT(Num_Documento SEPARATOR ', ') as Documentos_Credito,
                    MAX(Fecha_Vencimiento) as Fecha_Vencimiento_Max
                FROM Cuentas_Por_Cobrar 
                WHERE ID_Factura = %s 
                  AND Saldo_Pendiente > 0
                  AND Estado = 1
            """, (id_factura,))
            
            credito_info = cursor.fetchone()
            tiene_credito_pendiente = credito_info['Tiene_Credito_Pendiente'] > 0
            
            # 5. Obtener historial de pagos si es crédito
            pagos = []
            if tiene_credito_pendiente:
                cursor.execute("""
                    SELECT 
                        Fecha_Pago,
                        Monto_Pago,
                        Observacion,
                        Forma_Pago,
                        Numero_Comprobante
                    FROM Pagos_Cuentas_Cobrar
                    WHERE ID_Cuenta_Cobrar IN (
                        SELECT ID_Cuenta_Cobrar 
                        FROM Cuentas_Por_Cobrar 
                        WHERE ID_Factura = %s
                    )
                    ORDER BY Fecha_Pago DESC
                """, (id_factura,))
                pagos = cursor.fetchall()
            
            # 6. Obtener datos del movimiento de inventario (si existe) - VERSIÓN CORREGIDA
            movimiento_info = None
            if factura['ID_Movimiento']:
                cursor.execute("""
                    SELECT 
                        mi.ID_Movimiento,
                        DATE_FORMAT(mi.Fecha, '%d/%m/%Y') as Fecha_Formateada,
                        mi.Fecha,
                        mi.Observacion,
                        mi.ID_Usuario_Creacion,
                        mi.Estado,
                        mi.ID_Bodega,
                        DATE_FORMAT(mi.Fecha, '%d/%m/%Y %H:%i') as Fecha_Completa,
                        cm.Descripcion as Tipo_Movimiento,
                        b.Nombre as Nombre_Bodega,
                        u.NombreUsuario as Usuario_Creacion
                    FROM movimientos_inventario mi
                    LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                    WHERE mi.ID_Movimiento = %s
                """, (factura['ID_Movimiento'],))
                movimiento_info = cursor.fetchone()
            
            # DEBUG: Imprimir información para verificar
            print(f"DEBUG - Factura ID: {factura['ID_Factura']}")
            print(f"DEBUG - Fecha Formateada: {factura['Fecha_Formateada']}")
            print(f"DEBUG - Tipo Venta Formateado: {factura['Tipo_Venta_Formateado']}")
            print(f"DEBUG - Estado Factura: {factura['Estado_Factura']}")
            
            return render_template('admin/ventas/detalle_venta.html',
                                 factura=factura,
                                 detalles=detalles,
                                 movimiento_info=movimiento_info,
                                 total_productos=total_productos,
                                 total_venta=total_venta,
                                 tiene_credito_pendiente=tiene_credito_pendiente,
                                 credito_info=credito_info,
                                 pagos=pagos,
                                 hoy=datetime.now())
                                 
    except Exception as e:
        flash(f'Error al cargar detalles de la venta: {str(e)}', 'error')
        print(f"Error detallado: {traceback.format_exc()}")
        return redirect(url_for('admin_ventas_salidas'))

@app.route('/admin/ventas/anular/<int:id_factura>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("ANULAR_VENTA")
def admin_anular_venta(id_factura):
    """Anular una venta/factura existente - GET para mostrar datos, POST para procesar"""
    
    # Obtener datos de sesión
    id_empresa = session.get('id_empresa', 1)
    id_usuario = current_user.id
    
    if not id_empresa:
        return jsonify({'success': False, 'error': 'No se pudo determinar la empresa'}), 400
    
    if request.method == 'GET':
        # ============ OBTENER DATOS PARA MOSTRAR EN MODAL ============
        try:
            with get_db_cursor(True) as cursor:
                # 1. OBTENER DATOS PRINCIPALES DE LA FACTURA
                # NOTA: Usar Fecha_Creacion en lugar de Fecha para obtener hora también
                cursor.execute("""
                    SELECT 
                        f.ID_Factura,
                        f.Fecha,
                        f.Fecha_Creacion,
                        f.Estado,
                        f.Credito_Contado,
                        f.Observacion,
                        f.IDCliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        b.Nombre as bodega_nombre,
                        u.NombreUsuario as vendedor,
                        cpc.ID_Movimiento as id_cuenta_cobrar,
                        cpc.Estado as estado_cuenta,
                        cpc.Saldo_Pendiente,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y') as fecha_corta,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y') as fecha_creacion_corta,
                        DATE_FORMAT(f.Fecha_Creacion, '%d/%m/%Y %H:%i') as fecha_completa,
                        DATE_FORMAT(f.Fecha_Creacion, '%H:%i') as hora
                    FROM facturacion f
                    LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                    LEFT JOIN usuarios u ON f.ID_Usuario_Creacion = u.ID_Usuario
                    LEFT JOIN cuentas_por_cobrar cpc ON f.ID_Factura = cpc.ID_Factura
                    LEFT JOIN movimientos_inventario mi ON f.ID_Factura = mi.ID_Factura_Venta AND mi.Estado = 'Activa'
                    LEFT JOIN bodegas b ON mi.ID_Bodega = b.ID_Bodega
                    WHERE f.ID_Factura = %s 
                    AND f.ID_Empresa = %s
                """, (id_factura, id_empresa))
                
                venta = cursor.fetchone()
                
                if not venta:
                    return jsonify({'success': False, 'error': 'Venta/Factura no encontrada'}), 404
                
                if venta['Estado'] != 'Activa':
                    return jsonify({
                        'success': False, 
                        'error': f'Esta venta ya está {venta["Estado"].lower()}'
                    }), 400
                
                # 2. OBTENER PRODUCTOS DE LA VENTA
                cursor.execute("""
                    SELECT 
                        df.ID_Producto,
                        df.Cantidad,
                        df.Costo as precio_unitario,
                        df.Total as subtotal,
                        p.COD_Producto as codigo,
                        p.Descripcion,
                        p.Unidad_Medida
                    FROM detalle_facturacion df
                    INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                    WHERE df.ID_Factura = %s
                    ORDER BY df.ID_Detalle
                """, (id_factura,))
                
                productos = cursor.fetchall()
                
                # 3. CALCULAR TOTALES
                total_productos = len(productos)
                total_cantidad = sum(float(p['Cantidad']) for p in productos)
                total_venta = sum(float(p['subtotal']) for p in productos) if productos else 0
                
                # 4. FORMATEAR DATOS PARA EL FRONTEND
                datos_venta = {
                    'id_factura': venta['ID_Factura'],
                    'fecha': venta['fecha_completa'],  # Formato: dd/mm/yyyy HH:MM
                    'fecha_corta': venta['fecha_corta'],  # Formato: dd/mm/yyyy (de Fecha_Creacion)
                    'hora': venta['hora'],  # Formato: HH:MM (de Fecha_Creacion)
                    'fecha_raw': venta['Fecha'].isoformat() if venta['Fecha'] else None,
                    'fecha_creacion_raw': venta['Fecha_Creacion'].isoformat() if venta['Fecha_Creacion'] else None,
                    'estado': venta['Estado'],
                    'tipo_venta': 'CONTADO' if venta['Credito_Contado'] == 0 else 'CRÉDITO',
                    'tipo_venta_raw': venta['Credito_Contado'],
                    'cliente': venta['cliente_nombre'] or 'Consumidor Final',
                    'cliente_ruc': venta['cliente_ruc'] or 'N/A',
                    'bodega': venta['bodega_nombre'] or 'No especificada',
                    'vendedor': venta['vendedor'] or 'Sistema',
                    'observacion': venta['Observacion'] or '',
                    'total_venta': total_venta,
                    'total_venta_formateado': f"C${total_venta:,.2f}",
                    'total_productos': total_productos,
                    'total_cantidad': total_cantidad,
                    'tiene_cuenta_cobrar': venta['id_cuenta_cobrar'] is not None,
                    'estado_cuenta': venta['estado_cuenta'],
                    'saldo_pendiente': float(venta['Saldo_Pendiente']) if venta['Saldo_Pendiente'] else 0,
                    'productos': [
                        {
                            'id': p['ID_Producto'],
                            'codigo': p['codigo'],
                            'descripcion': p['Descripcion'],
                            'cantidad': float(p['Cantidad']),
                            'precio_unitario': float(p['precio_unitario']),
                            'subtotal': float(p['subtotal']),
                            'unidad_medida': p['Unidad_Medida']
                        }
                        for p in productos
                    ]
                }
                
                return jsonify({
                    'success': True,
                    'venta': datos_venta,
                    'usuario_actual': {
                        'id': id_usuario,
                        'nombre': current_user.NombreUsuario if hasattr(current_user, 'NombreUsuario') else 'Usuario'
                    }
                })
                
        except Exception as e:
            print(f"❌ Error obteniendo datos de venta #{id_factura}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return jsonify({
                'success': False,
                'error': f'Error interno al obtener datos: {str(e)}'
            }), 500
    
    elif request.method == 'POST':
        # ============ PROCESAR ANULACIÓN ============
        try:
            print(f"🔄 Iniciando anulación de venta #{id_factura}...")
            
            # Verificar usuario
            if not id_usuario:
                flash('Usuario no autenticado', 'error')
                return redirect(url_for('admin_ventas_salidas'))

            # Obtener motivo de anulación
            motivo_anulacion = request.form.get('motivo_anulacion', 'Anulación por usuario').strip()
            
            if not motivo_anulacion:
                motivo_anulacion = 'Anulación sin especificar motivo'
            
            with get_db_cursor(True) as cursor:
                # 1. VERIFICAR LA FACTURA/VENTA Y OBTENER DATOS COMPLETOS
                cursor.execute("""
                    SELECT 
                        f.ID_Factura,
                        f.Fecha,
                        f.Fecha_Creacion,
                        f.Estado,
                        f.Credito_Contado,
                        f.Observacion,
                        f.IDCliente,
                        c.Nombre as cliente_nombre,
                        c.RUC_CEDULA as cliente_ruc,
                        cpc.ID_Movimiento as id_cuenta_cobrar,
                        cpc.Estado as estado_cuenta,
                        cpc.Saldo_Pendiente,
                        mi.ID_Movimiento as id_movimiento_original,
                        mi.ID_Bodega as id_bodega_original
                    FROM facturacion f
                    LEFT JOIN clientes c ON f.IDCliente = c.ID_Cliente
                    LEFT JOIN cuentas_por_cobrar cpc ON f.ID_Factura = cpc.ID_Factura
                    LEFT JOIN movimientos_inventario mi ON f.ID_Factura = mi.ID_Factura_Venta AND mi.Estado = 'Activa'
                    WHERE f.ID_Factura = %s 
                    AND f.ID_Empresa = %s
                """, (id_factura, id_empresa))
                
                venta = cursor.fetchone()
                
                if not venta:
                    flash('Venta/Factura no encontrada', 'error')
                    return redirect(url_for('admin_ventas_salidas'))
                
                if venta['Estado'] != 'Activa':
                    flash(f'Esta venta ya está {venta["Estado"].lower()}', 'warning')
                    return redirect(url_for('admin_ventas_salidas'))
                
                # Validar cuenta por cobrar si es crédito
                if venta['Credito_Contado'] == 1 and venta['id_cuenta_cobrar']:
                    if venta['estado_cuenta'] == 'Pagada':
                        flash('No se puede anular una venta con cuenta por cobrar ya pagada', 'error')
                        return redirect(url_for('admin_ventas_salidas'))
                    elif venta['estado_cuenta'] == 'Anulada':
                        flash('La cuenta por cobrar ya está anulada', 'warning')
                        return redirect(url_for('admin_ventas_salidas'))
                
                print(f"📋 Venta #{id_factura} encontrada - Cliente: {venta['cliente_nombre']}")
                
                # 2. OBTENER LOS PRODUCTOS VENDIDOS CON SU COSTO ACTUAL
                cursor.execute("""
                    SELECT 
                        df.ID_Producto,
                        df.Cantidad,
                        df.Costo,
                        df.Total as subtotal,
                        p.COD_Producto,
                        p.Descripcion,
                        p.Unidad_Medida
                    FROM detalle_facturacion df
                    INNER JOIN productos p ON df.ID_Producto = p.ID_Producto
                    WHERE df.ID_Factura = %s
                """, (id_factura,))
                
                productos_vendidos = cursor.fetchall()
                
                if not productos_vendidos:
                    flash('No hay productos en esta venta', 'error')
                    return redirect(url_for('admin_ventas_salidas'))
                
                print(f"📦 Productos a revertir: {len(productos_vendidos)}")
                
                # 3. DETERMINAR BODEGA
                id_bodega = None
                nombre_bodega = ""
                
                if venta['id_bodega_original']:
                    id_bodega = venta['id_bodega_original']
                    cursor.execute("SELECT Nombre FROM bodegas WHERE ID_Bodega = %s", (id_bodega,))
                    bodega = cursor.fetchone()
                    nombre_bodega = bodega['Nombre'] if bodega else "Desconocida"
                    print(f"🏪 Bodega original encontrada: {nombre_bodega} (#{id_bodega})")
                else:
                    cursor.execute("""
                        SELECT ID_Bodega, Nombre 
                        FROM bodegas 
                        WHERE Estado = 1 
                        LIMIT 1
                    """)
                    bodega = cursor.fetchone()
                    if bodega:
                        id_bodega = bodega['ID_Bodega']
                        nombre_bodega = bodega['Nombre']
                        print(f"🏪 Usando bodega principal: {nombre_bodega} (#{id_bodega})")
                    else:
                        flash('Error: No hay bodegas activas', 'error')
                        return redirect(url_for('admin_ventas_salidas'))
                
                # 4. VERIFICAR TIPO DE MOVIMIENTO DE ANULACIÓN
                cursor.execute("""
                    SELECT ID_TipoMovimiento, Descripcion 
                    FROM catalogo_movimientos 
                    WHERE ID_TipoMovimiento = 10
                """)
                
                tipo_entrada = cursor.fetchone()
                
                if not tipo_entrada:
                    flash('Error: Tipo de movimiento de anulación no encontrado (ID 10)', 'error')
                    return redirect(url_for('admin_ventas_salidas'))
                
                print(f"📊 Tipo de movimiento de anulación: {tipo_entrada['Descripcion']}")
                
                # 5. CREAR MOVIMIENTO DE ANULACIÓN PRIMERO (ENTRADA)
                observacion_movimiento = f'Anulación venta #{id_factura} - Cliente: {venta["cliente_nombre"]} - Motivo: {motivo_anulacion}'
                
                cursor.execute("""
                    INSERT INTO movimientos_inventario (
                        ID_TipoMovimiento, 
                        ID_Bodega, 
                        Fecha, 
                        Tipo_Compra,
                        Observacion, 
                        ID_Empresa, 
                        ID_Usuario_Creacion, 
                        Estado,
                        ID_Factura_Venta,
                        Fecha_Creacion
                    )
                    VALUES (
                        %s, %s, CURDATE(), 'CONTADO',
                        %s,
                        %s, %s, 'Activa', %s,
                        NOW()
                    )
                """, (
                    tipo_entrada['ID_TipoMovimiento'], 
                    id_bodega,
                    observacion_movimiento,
                    id_empresa,
                    id_usuario,
                    id_factura
                ))
                
                id_movimiento_nuevo = cursor.lastrowid
                print(f"📦 Movimiento de anulación creado: #{id_movimiento_nuevo}")
                
                # 6. CREAR DETALLE DEL MOVIMIENTO DE ANULACIÓN Y DEVOLVER PRODUCTOS
                total_devolucion = 0
                productos_devueltos = []
                
                for producto in productos_vendidos:
                    cantidad = float(producto['Cantidad'])
                    costo = float(producto['Costo'])
                    subtotal = float(producto['subtotal'])
                    total_devolucion += subtotal
                    
                    # Crear detalle del movimiento
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario (
                            ID_Movimiento, 
                            ID_Producto, 
                            Cantidad, 
                            Costo_Unitario, 
                            Precio_Unitario, 
                            Subtotal,
                            ID_Usuario_Creacion,
                            Fecha_Creacion
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        id_movimiento_nuevo,
                        producto['ID_Producto'],
                        cantidad,
                        costo,
                        costo,
                        subtotal,
                        id_usuario
                    ))
                    
                    # Devolver productos al inventario (actualizar existencias)
                    cursor.execute("""
                        SELECT Existencias 
                        FROM inventario_bodega 
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (id_bodega, producto['ID_Producto']))
                    
                    inventario = cursor.fetchone()
                    
                    if inventario:
                        nuevas_existencias = float(inventario['Existencias']) + cantidad
                        cursor.execute("""
                            UPDATE inventario_bodega 
                            SET Existencias = %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (nuevas_existencias, id_bodega, producto['ID_Producto']))
                    else:
                        cursor.execute("""
                            INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                            VALUES (%s, %s, %s)
                        """, (id_bodega, producto['ID_Producto'], cantidad))
                    
                    productos_devueltos.append({
                        'codigo': producto['COD_Producto'],
                        'descripcion': producto['Descripcion'],
                        'cantidad': cantidad,
                        'precio': costo,
                        'total': subtotal
                    })
                    
                    print(f"  ✅ Devuelto: {cantidad} x {producto['COD_Producto']} = C${subtotal:,.2f}")
                
                print(f"💰 Total devuelto al inventario: C${total_devolucion:,.2f}")
                
                # 7. ANULAR MOVIMIENTO DE INVENTARIO ORIGINAL (si existe)
                if venta['id_movimiento_original']:
                    cursor.execute("""
                        UPDATE movimientos_inventario 
                        SET Estado = 'Anulada',
                            Observacion = CONCAT(COALESCE(Observacion, ''), ' | ANULADO: ', %s),
                            Fecha_Modificacion = NOW(),
                            ID_Usuario_Modificacion = %s
                        WHERE ID_Movimiento = %s
                    """, (motivo_anulacion, id_usuario, venta['id_movimiento_original']))
                    
                    if cursor.rowcount > 0:
                        print(f"📋 Movimiento de inventario original #{venta['id_movimiento_original']} anulado")
                else:
                    print(f"⚠️  No se encontró movimiento de inventario original para la venta #{id_factura}")
                
                # 8. ANULAR LA FACTURA
                nueva_observacion = f"{venta['Observacion'] or ''} | ANULADA: {motivo_anulacion}"
                cursor.execute("""
                    UPDATE facturacion 
                    SET Estado = 'Anulada',
                        Observacion = %s
                    WHERE ID_Factura = %s
                """, (nueva_observacion, id_factura))
                
                print(f"📝 Factura #{id_factura} ANULADA")
                
                # 9. ANULAR CUENTA POR COBRAR SI ES CRÉDITO
                if venta['Credito_Contado'] == 1 and venta['id_cuenta_cobrar']:
                    try:
                        # Verificar primero si existe la cuenta por cobrar
                        cursor.execute("""
                            SELECT Estado, Saldo_Pendiente 
                            FROM cuentas_por_cobrar 
                            WHERE ID_Movimiento = %s
                        """, (venta['id_cuenta_cobrar'],))
                        
                        cuenta_existente = cursor.fetchone()
                        
                        if cuenta_existente:
                            print(f"🔍 Estado actual cuenta #{venta['id_cuenta_cobrar']}: {cuenta_existente[0]}, Saldo: {cuenta_existente[1]}")
                            
                            # Actualizar la cuenta por cobrar
                            cursor.execute("""
                                UPDATE cuentas_por_cobrar 
                                SET Estado = 'Anulada',
                                    Saldo_Pendiente = 0,
                                    Observacion = CASE 
                                        WHEN Observacion IS NULL OR Observacion = '' 
                                        THEN CONCAT('ANULADA: ', %s, ' | Fecha: ', CURDATE())
                                        ELSE CONCAT(Observacion, ' | ANULADA: ', %s, ' | Fecha: ', CURDATE())
                                    END
                                WHERE ID_Movimiento = %s
                                AND Estado != 'Anulada'  -- Solo actualizar si no está ya anulada
                            """, (motivo_anulacion, motivo_anulacion, venta['id_cuenta_cobrar']))
                            
                            # Verificar si se actualizó alguna fila
                            if cursor.rowcount > 0:
                                print(f"✅ Cuenta por cobrar #{venta['id_cuenta_cobrar']} anulada exitosamente")
                                
                                # Confirmar la actualización
                                cursor.execute("""
                                    SELECT Estado, Saldo_Pendiente, Observacion 
                                    FROM cuentas_por_cobrar 
                                    WHERE ID_Movimiento = %s
                                """, (venta['id_cuenta_cobrar'],))
                                
                                resultado = cursor.fetchone()
                                if resultado:
                                    print(f"📋 Nuevo estado: {resultado[0]}, Saldo: {resultado[1]}")
                                    print(f"📝 Observación actualizada: {resultado[2]}")
                            else:
                                print(f"⚠️  Cuenta por cobrar #{venta['id_cuenta_cobrar']} ya estaba anulada o no existe")
                        else:
                            print(f"❌ Cuenta por cobrar #{venta['id_cuenta_cobrar']} no encontrada")
                            
                    except Exception as e:
                        print(f"❌ Error al anular cuenta por cobrar #{venta['id_cuenta_cobrar']}: {e}")
                
                # 10. VERIFICAR QUE TODO SE HAYA REGISTRADO CORRECTAMENTE
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = %s
                """, (id_movimiento_nuevo,))
                
                detalle_count = cursor.fetchone()['count']
                
                if detalle_count != len(productos_vendidos):
                    flash(f'⚠️  Advertencia: Se crearon {detalle_count} registros de detalle pero se esperaban {len(productos_vendidos)}', 'warning')
                
                # 11. MENSAJE DE CONFIRMACIÓN
                mensaje = f'✅ VENTA ANULADA EXITOSAMENTE<br>'
                mensaje += f'<strong>Factura #{id_factura}</strong><br>'
                mensaje += f'Cliente: {venta["cliente_nombre"]}<br>'
                mensaje += f'Total Anulado: C${total_devolucion:,.2f}<br>'
                mensaje += f'Productos devueltos: {len(productos_devueltos)}<br>'
                mensaje += f'Movimiento de anulación: #{id_movimiento_nuevo}'
                
                if venta['Credito_Contado'] == 1:
                    mensaje += '<br>✅ <em>Crédito anulado</em>'
                
                flash(mensaje, 'success')
                print(f"🎯 Venta #{id_factura} anulada exitosamente")
                print(f"📋 Movimiento de anulación: #{id_movimiento_nuevo}")
                print(f"📦 Productos devueltos: {len(productos_devueltos)}")
                print(f"💰 Total: C${total_devolucion:,.2f}")
                
                return redirect(url_for('admin_ventas_salidas'))
                
        except Exception as e:
            error_msg = f'❌ Error al anular venta #{id_factura}: {str(e)}'
            print(f"{error_msg}")
            import traceback
            traceback.print_exc()
            
            flash(error_msg, 'error')
            return redirect(url_for('admin_ventas_salidas'))

#CUENTAS POR COBRAR
@app.route('/admin/ventas/cxcobrar/cuentas-por-cobrar')
@admin_required
@bitacora_decorator("CUENTAS-POR-COBRAR")
def admin_cuentascobrar():
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    c.Observacion,
                    c.Fecha_Vencimiento,
                    c.Monto_Movimiento,
                    c.Saldo_Pendiente,
                    c.ID_Factura,
                    CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0')) as NumeroFactura,
                    e.Nombre_Empresa,
                    CASE 
                        WHEN c.Saldo_Pendiente = 0 THEN 'Pagado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0 THEN 'Vencido'
                        ELSE 'Pendiente'
                    END as Estado,
                    DATEDIFF(CURDATE(), c.Fecha_Vencimiento) as DiasVencido,
                    DATEDIFF(c.Fecha_Vencimiento, CURDATE()) as DiasRestantes,
                    c.Estado as EstadoDB
                FROM Cuentas_Por_Cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN facturacion f ON c.ID_Factura = f.ID_Factura
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.Estado IN ('Pendiente', 'Vencida')
                ORDER BY 
                    CASE 
                        WHEN c.Fecha_Vencimiento < CURDATE() AND c.Saldo_Pendiente > 0 THEN 1
                        WHEN c.Estado = 'Vencida' THEN 2
                        ELSE 3
                    END,
                    c.Fecha_Vencimiento ASC,
                    c.Fecha DESC
            """)
            cuentas = cursor.fetchall()
            
            # Calcular totales solo de las cuentas filtradas
            total_pendiente = sum(cuenta['Monto_Movimiento'] for cuenta in cuentas)
            total_saldo = sum(cuenta['Saldo_Pendiente'] for cuenta in cuentas)

            hoy = datetime.now().date()
            
            return render_template('admin/ventas/cxcobrar/cuentas_cobrar.html',
                                 cuentas=cuentas,
                                 total_pendiente=total_pendiente,
                                 total_saldo=total_saldo,
                                 hoy=hoy)
    except Exception as e:
        flash(f"Error al cargar cuentas por cobrar: {e}")
        return redirect(url_for('admin_dashboard'))
    
@app.route('/admin/ventas/cxcobrar/registrar-pago/<int:id_movimiento>', methods=['GET', 'POST'])
@admin_required
@bitacora_decorator("REGISTRAR-PAGO-CXC")
def admin_registrar_pago(id_movimiento):
    if request.method == 'POST':
        try:
            # Convertir el monto del formulario a Decimal
            from decimal import Decimal
            monto_pago_str = request.form['monto']
            monto_pago = Decimal(monto_pago_str)
            
            id_metodo_pago = request.form['metodo_pago']
            comentarios = request.form.get('comentarios', '')
            detalles_metodo = request.form.get('detalles_metodo', '')
            
            with get_db_cursor(True) as cursor:
                # Verificar saldo pendiente y datos de la cuenta
                cursor.execute("""
                    SELECT c.Saldo_Pendiente, c.ID_Cliente, c.Monto_Movimiento, cl.Nombre as NombreCliente
                    FROM Cuentas_Por_Cobrar c
                    LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                    WHERE c.ID_Movimiento = %s
                """, (id_movimiento,))
                resultado = cursor.fetchone()
                
                if not resultado:
                    flash("Cuenta por cobrar no encontrada")
                    return redirect(url_for('admin_cuentascobrar'))
                
                # Asegurar que saldo_actual sea Decimal
                saldo_actual = Decimal(str(resultado['Saldo_Pendiente']))
                
                # Validaciones con Decimal
                if monto_pago <= Decimal('0'):
                    flash("El monto del pago debe ser mayor a cero")
                    return redirect(url_for('admin_registrar_pago', id_movimiento=id_movimiento))
                
                if monto_pago > saldo_actual:
                    flash(f"El monto del pago (${monto_pago:,.2f}) no puede ser mayor al saldo pendiente (${saldo_actual:,.2f})")
                    return redirect(url_for('admin_registrar_pago', id_movimiento=id_movimiento))
                
                # Registrar pago - convertir a float para la base de datos
                cursor.execute("""
                    INSERT INTO Pagos_CuentasCobrar 
                    (ID_Movimiento, Monto, ID_MetodoPago, Comentarios, Detalles_Metodo, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento,
                    float(monto_pago),  # Convertir a float para la inserción
                    id_metodo_pago,
                    comentarios,
                    detalles_metodo,
                    current_user.id
                ))
                
                # Actualizar saldo pendiente - ambos son Decimal para la operación
                nuevo_saldo = saldo_actual - monto_pago
                
                # Convertir a float para la actualización en la base de datos
                cursor.execute("""
                    UPDATE Cuentas_Por_Cobrar 
                    SET Saldo_Pendiente = %s 
                    WHERE ID_Movimiento = %s
                """, (float(nuevo_saldo), id_movimiento))
                
                # Determinar estado final
                estado_final = "Cancelado" if nuevo_saldo == Decimal('0') else "Pendiente"
                
                flash(f"✅ Pago de ${float(monto_pago):,.2f} registrado exitosamente. Saldo restante: ${float(nuevo_saldo):,.2f} - Estado: {estado_final}")
                return redirect(url_for('admin_detalle_cuentacobrar', id_movimiento=id_movimiento))
                
        except ValueError as e:
            flash(f"❌ Error: El monto ingresado no es válido")
            return redirect(url_for('admin_registrar_pago', id_movimiento=id_movimiento))
        except Exception as e:
            flash(f"❌ Error al registrar pago: {e}")
            return redirect(url_for('admin_registrar_pago', id_movimiento=id_movimiento))
    
    # GET: Cargar datos para el formulario
    try:
        with get_db_cursor(True) as cursor:
            # Datos de la cuenta con estado calculado
            cursor.execute("""
                SELECT 
                    c.*, 
                    cl.Nombre as NombreCliente,
                    cl.Telefono as TelefonoCliente,
                    cl.Direccion as DireccionCliente,
                    cl.RUC_CEDULA,
                    e.Nombre_Empresa,
                    CASE 
                        WHEN c.Saldo_Pendiente = 0 THEN 'Cancelado'
                        WHEN c.Fecha_Vencimiento < CURDATE() THEN 'Vencido'
                        ELSE 'Pendiente'
                    END as Estado_Actual
                FROM Cuentas_Por_Cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash("Cuenta por cobrar no encontrada")
                return redirect(url_for('admin_cuentascobrar'))
            
            # Convertir Decimal a float para el template
            if cuenta['Saldo_Pendiente']:
                cuenta['Saldo_Pendiente'] = float(cuenta['Saldo_Pendiente'])
            if cuenta['Monto_Movimiento']:
                cuenta['Monto_Movimiento'] = float(cuenta['Monto_Movimiento'])
            
            # Métodos de pago disponibles
            cursor.execute("SELECT ID_MetodoPago, Nombre FROM Metodos_Pago")
            metodos_pago = cursor.fetchall()
            
            # Pasar la fecha actual para comparar vencimientos
            from datetime import datetime
            today = datetime.now().date()
            
            return render_template('admin/ventas/cxcobrar/registrar_pago.html',
                                 cuenta=cuenta, 
                                 metodos_pago=metodos_pago,
                                 today=today)
                                 
    except Exception as e:
        flash(f"❌ Error al cargar formulario de pago: {e}")
        return redirect(url_for('admin_cuentascobrar'))

@app.route('/admin/ventas/cxcobrar/detalle/<int:id_movimiento>')
@admin_required
@bitacora_decorator("DETALLE-CUENTA-COBRAR")
def admin_detalle_cuentacobrar(id_movimiento):
    try:
        with get_db_cursor(True) as cursor:
            # DATOS PRINCIPALES CORREGIDOS CON JOINS EXACTOS
            cursor.execute("""
                SELECT 
                    c.ID_Movimiento,
                    c.Fecha,
                    c.ID_Cliente,
                    c.Num_Documento,
                    c.Observacion,
                    c.Fecha_Vencimiento,
                    c.Tipo_Movimiento,
                    c.Monto_Movimiento,
                    c.ID_Empresa,
                    COALESCE(c.Saldo_Pendiente, 0) as Saldo_Pendiente,
                    c.ID_Factura,
                    c.ID_Usuario_Creacion,
                    COALESCE(cl.Nombre, 'Cliente no encontrado') as NombreCliente,
                    COALESCE(cl.RUC_CEDULA, 'N/A') as CedulaCliente,
                    COALESCE(cl.Telefono, 'N/A') as TelefonoCliente,
                    COALESCE(cl.Direccion, 'N/A') as DireccionCliente,
                    COALESCE(e.Nombre_Empresa, 'N/A') as Nombre_Empresa,
                    CASE 
                        WHEN f.ID_Factura IS NOT NULL THEN CONCAT('FAC-', LPAD(f.ID_Factura, 5, '0'))
                        ELSE 'N/A'
                    END as NumeroFactura,
                    f.Fecha as FechaFactura,
                    COALESCE(u.NombreUsuario, 'N/A') as UsuarioCreacion,
                    CASE 
                        WHEN COALESCE(c.Saldo_Pendiente, 0) = 0 THEN 'Cancelado'
                        WHEN c.Fecha_Vencimiento < CURDATE() AND COALESCE(c.Saldo_Pendiente, 0) > 0 THEN 'Vencido'
                        ELSE 'Pendiente'
                    END as Estado,
                    CASE 
                        WHEN c.Fecha_Vencimiento IS NOT NULL 
                             AND c.Fecha_Vencimiento < CURDATE() 
                             AND COALESCE(c.Saldo_Pendiente, 0) > 0 
                        THEN DATEDIFF(CURDATE(), c.Fecha_Vencimiento)
                        ELSE 0
                    END as DiasVencido,
                    # Información adicional útil
                    c.Monto_Movimiento - COALESCE(c.Saldo_Pendiente, 0) as TotalPagadoCalculado
                FROM Cuentas_Por_Cobrar c
                LEFT JOIN clientes cl ON c.ID_Cliente = cl.ID_Cliente
                LEFT JOIN empresa e ON c.ID_Empresa = e.ID_Empresa
                LEFT JOIN Facturacion f ON c.ID_Factura = f.ID_Factura  -- CORREGIDO: Facturacion con F mayúscula
                LEFT JOIN usuarios u ON c.ID_Usuario_Creacion = u.ID_Usuario
                WHERE c.ID_Movimiento = %s
            """, (id_movimiento,))
            
            cuenta = cursor.fetchone()
            
            if not cuenta:
                flash("❌ Error: Cuenta por cobrar no encontrada", "error")
                return redirect(url_for('admin_cuentascobrar'))
            
            # HISTORIAL DE PAGOS CORREGIDO
            cursor.execute("""
                SELECT 
                    p.ID_Pago,
                    p.ID_Movimiento,
                    p.Monto,
                    p.ID_MetodoPago,
                    p.Comentarios,
                    p.Detalles_Metodo,
                    p.ID_Usuario_Creacion,
                    p.Fecha,
                    COALESCE(mp.Nombre, 'Método no disponible') as MetodoPago,
                    COALESCE(u.NombreUsuario, 'Usuario no disponible') as UsuarioRegistro,
                    DATE_FORMAT(p.Fecha, '%%d/%%m/%%Y %%H:%%i') as FechaFormateada,
                    DATE_FORMAT(p.Fecha, '%%Y-%%m-%%d') as FechaCorta
                FROM Pagos_CuentasCobrar p
                LEFT JOIN metodos_pago mp ON p.ID_MetodoPago = mp.ID_MetodoPago  -- CORREGIDO: metodos_pago en minúsculas
                LEFT JOIN usuarios u ON p.ID_Usuario_Creacion = u.ID_Usuario
                WHERE p.ID_Movimiento = %s
                ORDER BY p.Fecha DESC
            """, (id_movimiento,))
            
            pagos = cursor.fetchall()
            
            # CÁLCULOS SEGUROS CON DECIMAL
            from decimal import Decimal
            
            # Convertir a Decimal de forma segura
            monto_movimiento = Decimal(str(cuenta['Monto_Movimiento']))
            saldo_pendiente = Decimal(str(cuenta['Saldo_Pendiente']))
            
            # Calcular total pagado de forma precisa y segura
            total_pagado = sum(Decimal(str(pago['Monto'])) for pago in pagos) if pagos else Decimal('0')
            
            # Validar consistencia de datos
            saldo_teorico = monto_movimiento - total_pagado
            diferencia = abs(saldo_pendiente - saldo_teorico)
            
            # Si hay diferencia significativa, mostrar advertencia
            tiene_inconsistencia = diferencia > Decimal('0.01')
            
            # ESTADÍSTICAS ADICIONALES MEJORADAS
            primer_pago = pagos[-1] if pagos and len(pagos) > 0 else None
            ultimo_pago = pagos[0] if pagos and len(pagos) > 0 else None
            
            # INFORMACIÓN ADICIONAL ÚTIL
            total_abonado = monto_movimiento - saldo_pendiente
            porcentaje_pagado = (total_abonado / monto_movimiento * 100) if monto_movimiento > 0 else 0
            
            # PREPARAR DATOS PARA TEMPLATE
            datos_template = {
                'cuenta': cuenta,
                'pagos': pagos,
                'total_pagado': float(total_pagado),
                'total_abonado': float(total_abonado),
                'porcentaje_pagado': round(float(porcentaje_pagado), 2),
                'tiene_inconsistencia': tiene_inconsistencia,
                'diferencia': float(diferencia),
                'primer_pago': primer_pago,
                'ultimo_pago': ultimo_pago,
                'monto_movimiento_formateado': float(monto_movimiento),
                'saldo_pendiente_formateado': float(saldo_pendiente),
                'saldo_teorico': float(saldo_teorico)
            }
            
            return render_template('admin/ventas/cxcobrar/detalle_cuenta.html', **datos_template)
                                 
    except Exception as e:
        flash(f"❌ Error al cargar detalle de cuenta: {str(e)}", "error")
        return redirect(url_for('admin_cuentascobrar'))

# =============================================
TIPO_COMPRA = 1
TIPO_VENTA = 2
TIPO_PRODUCCION = 3
TIPO_CONSUMO = 4
TIPO_AJUSTE = 5
TIPO_TRASLADO = 6

# 1. LISTADO MEJORADO CON FILTROS
@app.route('/admin/movimientos/listado')
@admin_required
@bitacora_decorator("HISTORIAL-MOVIMIENTOS")
def admin_historial_movimientos():
    """Historial completo de movimientos con filtros"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Filtros
        tipo_filtro = request.args.get('tipo', 'todos')
        fecha_inicio = request.args.get('fecha_inicio', '')
        fecha_fin = request.args.get('fecha_fin', '')
        
        with get_db_cursor(True) as cursor:
            # Construir consulta base CORREGIDA
            query = """
                SELECT mi.*, 
                       cm.Descripcion as Tipo_Movimiento_Descripcion,
                       cm.Letra,
                       bo.Nombre as Bodega_Origen_Nombre,
                       bd.Nombre as Bodega_Destino_Nombre,
                       p.Nombre as Proveedor_Nombre,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Cantidad_Productos,
                       (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor 
                    AND p.ID_Empresa = mi.ID_Empresa  -- IMPORTANTE: filtrar por misma empresa
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.Estado = 1
            """
            
            count_query = """
                SELECT COUNT(*) as total
                FROM movimientos_inventario mi
                WHERE mi.Estado = 1
            """
            
            params = []
            count_params = []
            
            # Aplicar filtros
            if tipo_filtro != 'todos':
                query += " AND mi.ID_TipoMovimiento = %s"
                count_query += " AND mi.ID_TipoMovimiento = %s"
                params.append(tipo_filtro)
                count_params.append(tipo_filtro)
            
            if fecha_inicio:
                query += " AND mi.Fecha >= %s"
                count_query += " AND mi.Fecha >= %s"
                params.append(fecha_inicio)
                count_params.append(fecha_inicio)
            
            if fecha_fin:
                query += " AND mi.Fecha <= %s"
                count_query += " AND mi.Fecha <= %s"
                params.append(fecha_fin)
                count_params.append(fecha_fin)
            
            # Ordenar y paginar
            query += " ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC LIMIT %s OFFSET %s"
            params.extend([per_page, offset])
            
            # Ejecutar consulta de conteo
            cursor.execute(count_query, tuple(count_params))
            total = cursor.fetchone()['total']
            
            # Ejecutar consulta principal
            cursor.execute(query, tuple(params))
            movimientos = cursor.fetchall()
            
            # Obtener tipos de movimiento para filtro
            cursor.execute("SELECT * FROM catalogo_movimientos ORDER BY Descripcion")
            tipos_movimiento = cursor.fetchall()
            
            total_pages = (total + per_page - 1) // per_page
            
            return render_template('admin/movimientos/historial_movimientos.html',
                                 movimientos=movimientos,
                                 tipos_movimiento=tipos_movimiento,
                                 tipo_filtro=tipo_filtro,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 page=page,
                                 total_pages=total_pages,
                                 total=total)
    except Exception as e:
        flash(f"Error al cargar historial: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

# 2. NUEVA ENTRADA (Compra/Producción)
@app.route('/admin/movimientos/entrada/nueva')
@admin_required
def admin_nueva_entrada_form():

    print(f"DEBUG - current_user: {current_user}")
    print(f"DEBUG - current_user.is_authenticated: {current_user.is_authenticated}")
    print(f"DEBUG - current_user.id: {getattr(current_user, 'id', 'NO ID ATTRIBUTE')}")
    print(f"DEBUG - current_user.__dict__: {current_user.__dict__}")

    """Mostrar formulario para nueva entrada (compra/producción)"""
    try:
        with get_db_cursor(True) as cursor:
            # Solo mostrar tipos de entrada (Letra = 'E')
            cursor.execute("""
                SELECT * FROM catalogo_movimientos 
                WHERE Letra = 'E'
                ORDER BY Descripcion
            """)  # Ajuste también puede ser entrada
            
            tipos_movimiento = cursor.fetchall()
            
            # Obtener proveedores
            cursor.execute("""
                SELECT * FROM proveedores 
                WHERE Estado = 'ACTIVO' 
                ORDER BY Nombre
            """)
            proveedores = cursor.fetchall()
            
            # Obtener bodegas
            cursor.execute("""
                SELECT * FROM bodegas 
                WHERE Estado = 1 
                ORDER BY Nombre
            """)
            bodegas = cursor.fetchall()
            
            # Obtener productos activos
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    p.Unidad_Medida, 
                    um.Descripcion as Unidad_Descripcion,
                    p.Precio_Venta, 
                    p.Stock_Minimo,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                WHERE p.Estado = 'activo'
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, 
                         p.Unidad_Medida, p.Precio_Venta, p.Stock_Minimo,
                         um.Descripcion, cp.Descripcion
                ORDER BY p.Descripcion
                LIMIT 100
            """)
            productos = cursor.fetchall()
            
            # Obtener también el stock por bodega para cada producto
            productos_con_stock = []
            for producto in productos:
                producto_dict = dict(producto)
                
                # Consultar stock por bodega
                cursor.execute("""
                    SELECT 
                        b.ID_Bodega,
                        b.Nombre as Bodega,
                        COALESCE(ib.Existencias, 0) as Existencias
                    FROM bodegas b
                    LEFT JOIN inventario_bodega ib ON b.ID_Bodega = ib.ID_Bodega 
                        AND ib.ID_Producto = %s
                    WHERE b.Estado = 1
                    ORDER BY b.Nombre
                """, (producto['ID_Producto'],))
                
                stock_bodegas = cursor.fetchall()
                producto_dict['stock_bodegas'] = stock_bodegas
                
                productos_con_stock.append(producto_dict)

            fecha_hoy = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('admin/movimientos/nueva_entrada.html',
                                 tipos_movimiento=tipos_movimiento,
                                 proveedores=proveedores,
                                 bodegas=bodegas,
                                 productos=productos_con_stock,
                                 fecha_hoy=fecha_hoy)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('admin_historial_movimientos'))

# 3. PROCESAR ENTRADA
@app.route('/admin/movimientos/entrada/procesar', methods=['POST'])
@admin_required
@bitacora_decorator("PROCESAR-ENTRADA")
def admin_procesar_entrada():
    """Procesar nueva entrada (compra/producción/ajuste positivo)"""
    try:
        # Obtener user_id desde current_user (Flask-Login)
        if not current_user.is_authenticated:
            flash("Debe iniciar sesión para realizar esta acción", 'error')
            return redirect(url_for('login'))
        
        user_id = current_user.id
        print(f"DEBUG - User ID from current_user: {user_id}")
        
        # Validar datos básicos
        fecha = request.form.get('fecha')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        if not all([fecha, id_tipo_movimiento, id_bodega]):
            flash("Fecha, tipo de movimiento y bodega son requeridos", 'error')
            return redirect(url_for('admin_nueva_entrada_form'))
        
        # Convertir valores
        try:
            id_tipo_movimiento = int(id_tipo_movimiento)
            id_bodega = int(id_bodega)
        except ValueError:
            flash("ID de tipo de movimiento o bodega no válido", 'error')
            return redirect(url_for('admin_nueva_entrada_form'))
        
        # Validar que sea tipo de entrada
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT Letra FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = %s
            """, (id_tipo_movimiento,))
            
            tipo_mov = cursor.fetchone()
            if not tipo_mov or tipo_mov['Letra'] not in ['E', 'A']:
                flash("Tipo de movimiento no válido para entrada", 'error')
                return redirect(url_for('admin_nueva_entrada_form'))
        
        # Obtener productos
        productos_json = request.form.get('productos')
        if not productos_json:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('admin_nueva_entrada_form'))
        
        try:
            productos = json.loads(productos_json)
        except json.JSONDecodeError:
            flash("Formato de productos no válido", 'error')
            return redirect(url_for('admin_nueva_entrada_form'))
        
        with get_db_cursor() as cursor:
            # Obtener ID de empresa del usuario o usar valor por defecto
            cursor.execute("""
                SELECT ID_Empresa FROM Usuarios WHERE ID_Usuario = %s
            """, (user_id,))
            
            usuario_data = cursor.fetchone()
            id_empresa = usuario_data['ID_Empresa'] if usuario_data else 1
            
            # Insertar movimiento principal
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Proveedor, Tipo_Compra, 
                 ID_Bodega, N_Factura_Externa, Observacion, 
                 ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                id_tipo_movimiento, 
                fecha,
                request.form.get('id_proveedor') or None,
                request.form.get('tipo_compra') or None,
                id_bodega,
                request.form.get('n_factura_externa') or None,
                request.form.get('observacion') or None,
                id_empresa,
                user_id
            ))
            
            id_movimiento = cursor.lastrowid
            
            # Procesar cada producto
            for prod in productos:
                try:
                    # Validar campos requeridos
                    if 'id_producto' not in prod or not prod['id_producto']:
                        continue
                    
                    if 'cantidad' not in prod or not prod['cantidad']:
                        continue
                    
                    # Convertir valores
                    id_producto = int(prod['id_producto'])
                    cantidad = Decimal(str(prod.get('cantidad', 0)))
                    costo_unitario = Decimal(str(prod.get('costo_unitario', 0)))
                    precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                    subtotal = cantidad * costo_unitario
                    
                    # Validar valores positivos
                    if cantidad <= 0:
                        continue
                    
                    # Validar que el producto existe
                    cursor.execute("""
                        SELECT ID_Producto FROM productos 
                        WHERE ID_Producto = %s AND Estado = 'activo'
                    """, (id_producto,))
                    
                    if not cursor.fetchone():
                        continue
                    
                    # Insertar detalle
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                         Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        id_producto, 
                        cantidad,
                        costo_unitario, 
                        precio_unitario, 
                        subtotal,
                        user_id
                    ))
                    
                    # ACTUALIZAR inventario_bodega
                    cursor.execute("""
                        INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        Existencias = Existencias + VALUES(Existencias)
                    """, (id_bodega, id_producto, cantidad))
                    
                except Exception as prod_error:
                    print(f"Error con producto: {prod_error}")
                    continue
            
            flash(f"✅ Entrada registrada exitosamente! ID: {id_movimiento}", 'success')
            return redirect(url_for('admin_detalle_movimiento', id_movimiento=id_movimiento))
            
    except Exception as e:
        print(f"Error completo: {e}")
        flash(f"❌ Error al procesar entrada: {str(e)}", 'error')
        return redirect(url_for('admin_nueva_entrada_form'))

def obtener_existencias_producto(id_producto):
    """Obtener existencias totales de un producto sumando todas las bodegas"""
    with get_db_cursor(True) as cursor:
        cursor.execute("""
            SELECT COALESCE(SUM(Existencias), 0) as Existencias_Totales
            FROM inventario_bodega
            WHERE ID_Producto = %s
        """, (id_producto,))
        
        result = cursor.fetchone()
        return result['Existencias_Totales'] if result else 0

# 4. NUEVA SALIDA (Venta/Consumo)
@app.route('/admin/movimientos/salida/nueva')
@admin_required
def admin_nueva_salida_form():
    """Mostrar formulario para nueva salida (venta/consumo)"""
    try:
        with get_db_cursor(True) as cursor:
            # Solo mostrar tipos de salida (Letra = 'S')
            cursor.execute("""
                SELECT * FROM catalogo_movimientos 
                WHERE Letra = 'S'
                ORDER BY Descripcion
            """)  # Ajuste también puede ser salida
            
            tipos_movimiento = cursor.fetchall()
            
            # Obtener bodegas
            cursor.execute("""
                SELECT * FROM bodegas 
                WHERE Estado = 1 
                ORDER BY Nombre
            """)
            bodegas = cursor.fetchall()
            
            # Obtener clientes (para ventas)
            cursor.execute("""
                SELECT * FROM clientes 
                WHERE Estado = 'ACTIVO'
                ORDER BY Nombre
            """)
            clientes = cursor.fetchall()
            
            # Obtener facturas pendientes - CORREGIDO: formateo de fecha
            cursor.execute("""
                SELECT f.ID_Factura, f.Fecha, c.Nombre as Cliente,
                       (SELECT COUNT(*) FROM detalle_facturacion 
                        WHERE ID_Factura = f.ID_Factura) as Items
                FROM facturacion f
                JOIN clientes c ON f.IDCliente = c.ID_Cliente
                WHERE f.ID_Empresa = %s
                AND f.Fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                ORDER BY f.Fecha DESC
                LIMIT 50
            """, (session.get('id_empresa', 1),))
            
            facturas = cursor.fetchall()
            
            # Formatear fechas para el template
            for factura in facturas:
                if factura['Fecha']:
                    factura['Fecha_formatted'] = factura['Fecha'].strftime('%Y-%m-%d')
                else:
                    factura['Fecha_formatted'] = ''

            fecha_hoy = datetime.now().strftime('%Y-%m-%d')
            
            return render_template('admin/movimientos/nueva_salida.html',
                                 tipos_movimiento=tipos_movimiento,
                                 bodegas=bodegas,
                                 clientes=clientes,
                                 facturas=facturas,
                                 fecha_hoy=fecha_hoy)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('admin_historial_movimientos'))

# 5. PROCESAR SALIDA
@app.route('/admin/movimientos/salida/procesar', methods=['POST'])
@admin_required
@bitacora_decorator("PROCESAR-SALIDA")
def admin_procesar_salida():
    """Procesar nueva salida (venta/consumo/ajuste negativo)"""
    try:
        # Validar autenticación
        if not current_user.is_authenticated:
            flash("Debe iniciar sesión para realizar esta acción", 'error')
            return redirect(url_for('login'))
        
        user_id = current_user.id
        
        # Validar datos básicos
        fecha = request.form.get('fecha')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        if not all([fecha, id_tipo_movimiento, id_bodega]):
            flash("Fecha, tipo de movimiento y bodega son requeridos", 'error')
            return redirect(url_for('admin_nueva_salida_form'))
        
        try:
            id_tipo_movimiento = int(id_tipo_movimiento)
            id_bodega = int(id_bodega)
        except ValueError:
            flash("ID de tipo de movimiento o bodega no válido", 'error')
            return redirect(url_for('admin_nueva_salida_form'))
        
        # Validar que sea tipo de salida
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT Letra FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = %s
            """, (id_tipo_movimiento,))
            
            tipo_mov = cursor.fetchone()
            if not tipo_mov or tipo_mov['Letra'] not in ['S', 'A']:
                flash("Tipo de movimiento no válido para salida", 'error')
                return redirect(url_for('admin_nueva_salida_form'))
        
        # Obtener productos
        productos_json = request.form.get('productos')
        if not productos_json:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('admin_nueva_salida_form'))
        
        try:
            productos = json.loads(productos_json)
        except json.JSONDecodeError:
            flash("Formato de productos no válido", 'error')
            return redirect(url_for('admin_nueva_salida_form'))
        
        with get_db_cursor() as cursor:
            # Obtener ID de empresa del usuario
            cursor.execute("""
                SELECT ID_Empresa FROM Usuarios WHERE ID_Usuario = %s
            """, (user_id,))
            
            usuario_data = cursor.fetchone()
            id_empresa = usuario_data['ID_Empresa'] if usuario_data else 1
            
            # VERIFICAR STOCK antes de proceder
            productos_insuficientes = []
            
            for prod in productos:
                cursor.execute("""
                    SELECT Existencias 
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega, prod['id_producto']))
                
                stock = cursor.fetchone()
                cantidad_necesaria = Decimal(str(prod['cantidad']))
                
                stock_disponible = stock['Existencias'] if stock else Decimal('0')
                
                if stock_disponible < cantidad_necesaria:
                    # Obtener nombre del producto
                    cursor.execute("SELECT Descripcion FROM productos WHERE ID_Producto = %s", 
                                 (prod['id_producto'],))
                    producto_info = cursor.fetchone()
                    producto_nombre = producto_info['Descripcion'] if producto_info else 'Producto desconocido'
                    
                    productos_insuficientes.append({
                        'producto': producto_nombre,
                        'solicitado': float(cantidad_necesaria),
                        'disponible': float(stock_disponible)
                    })
            
            if productos_insuficientes:
                mensaje_error = "Stock insuficiente:<br>"
                for item in productos_insuficientes:
                    mensaje_error += f"- {item['producto']}: Solicitado {item['solicitado']}, Disponible {item['disponible']}<br>"
                flash(mensaje_error, 'error')
                return redirect(url_for('admin_nueva_salida_form'))
            
            # VARIABLE PARA ID DE FACTURA
            id_factura_venta = None
            
            # SI ES VENTA, MANEJAR FACTURACIÓN Y CUENTAS POR COBRAR
            if id_tipo_movimiento == TIPO_VENTA:  # TIPO_VENTA = 2
                id_cliente = request.form.get('id_cliente')
                id_factura_existente = request.form.get('id_factura_venta')
                tipo_pago = request.form.get('tipo_pago')  # CONTADO o CREDITO
                
                if not id_cliente and not id_factura_existente:
                    flash("Para ventas debe seleccionar un cliente o una factura existente", 'error')
                    return redirect(url_for('admin_nueva_salida_form'))
                
                if id_factura_existente:
                    # Usar factura existente
                    id_factura_venta = int(id_factura_existente)
                    
                    # Verificar que la factura pertenece a la empresa
                    cursor.execute("""
                        SELECT ID_Factura FROM facturacion 
                        WHERE ID_Factura = %s AND ID_Empresa = %s
                    """, (id_factura_venta, id_empresa))
                    
                    if not cursor.fetchone():
                        flash("Factura no encontrada o no pertenece a su empresa", 'error')
                        return redirect(url_for('admin_nueva_salida_form'))
                        
                elif id_cliente:
                    # Crear nueva factura
                    cursor.execute("""
                        INSERT INTO facturacion 
                        (Fecha, IDCliente, Credito_Contado, Observacion, 
                         ID_Empresa, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        fecha,
                        id_cliente,
                        1 if tipo_pago == 'CREDITO' else 0,  # 1=Crédito, 0=Contado
                        request.form.get('observacion_factura') or None,
                        id_empresa,
                        user_id
                    ))
                    id_factura_venta = cursor.lastrowid
                    
                    # Calcular total de la venta
                    total_venta = Decimal('0')
                    for prod in productos:
                        cantidad = Decimal(str(prod['cantidad']))
                        precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                        total_item = cantidad * precio_unitario
                        total_venta += total_item
                        
                        # Insertar detalle de facturación
                        cursor.execute("""
                            INSERT INTO detalle_facturacion 
                            (ID_Factura, ID_Producto, Cantidad, Costo, Total)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (
                            id_factura_venta,
                            prod['id_producto'],
                            cantidad,
                            Decimal(str(prod.get('costo_unitario', 0))),
                            total_item
                        ))
                    
                    # Si es CRÉDITO, crear registro en cuentas por cobrar
                    if tipo_pago == 'CREDITO':
                        # Calcular fecha de vencimiento (30 días por defecto)
                        fecha_vencimiento = (datetime.strptime(fecha, '%Y-%m-%d') + 
                                           timedelta(days=30)).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO cuentas_por_cobrar 
                            (Fecha, ID_Cliente, Num_Documento, Observacion,
                             Fecha_Vencimiento, Tipo_Movimiento, Monto_Movimiento,
                             ID_Empresa, Saldo_Pendiente, ID_Factura, ID_Usuario_Creacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            fecha,
                            id_cliente,
                            f"FACT-{id_factura_venta:06d}",  # Formato: FACT-000001
                            f"Venta a crédito - Factura #{id_factura_venta}",
                            fecha_vencimiento,
                            1,  # Tipo movimiento: 1 = Factura (debe)
                            total_venta,
                            id_empresa,
                            total_venta,  # Saldo pendiente inicial = monto total
                            id_factura_venta,
                            user_id
                        ))
                    
                    flash(f"✅ Factura #{id_factura_venta} creada exitosamente", 'success')
                    
                    if tipo_pago == 'CREDITO':
                        flash(f"📝 Cuenta por cobrar registrada - Vence: {fecha_vencimiento}", 'info')
            
            # Insertar movimiento de inventario (SALIDA)
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Factura_Venta,
                 Observacion, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                id_tipo_movimiento, 
                fecha, 
                id_bodega,
                id_factura_venta,
                request.form.get('observacion') or None,
                id_empresa,
                user_id
            ))
            
            id_movimiento = cursor.lastrowid
            
            # Procesar cada producto para el movimiento de inventario
            for prod in productos:
                try:
                    # Validar campos requeridos
                    if 'id_producto' not in prod or not prod['id_producto']:
                        continue
                    
                    if 'cantidad' not in prod or not prod['cantidad']:
                        continue
                    
                    # Convertir valores
                    id_producto = int(prod['id_producto'])
                    cantidad = Decimal(str(prod['cantidad']))
                    precio_unitario = Decimal(str(prod.get('precio_unitario', 0)))
                    
                    # Obtener costo promedio (último costo de entrada)
                    cursor.execute("""
                        SELECT Costo_Unitario 
                        FROM detalle_movimientos_inventario dmi
                        JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                        JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                        WHERE dmi.ID_Producto = %s 
                        AND cm.Letra = 'E'
                        ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                        LIMIT 1
                    """, (id_producto,))
                    
                    costo_result = cursor.fetchone()
                    
                    # Usar costo proporcionado o el último costo encontrado
                    if 'costo_unitario' in prod and prod['costo_unitario']:
                        costo_unitario = Decimal(str(prod['costo_unitario']))
                    elif costo_result:
                        costo_unitario = Decimal(str(costo_result['Costo_Unitario']))
                    else:
                        costo_unitario = Decimal('0')
                    
                    subtotal = cantidad * costo_unitario
                    
                    # Insertar detalle del movimiento de inventario
                    cursor.execute("""
                        INSERT INTO detalle_movimientos_inventario
                        (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                         Precio_Unitario, Subtotal, ID_Usuario_Creacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        id_movimiento, 
                        id_producto, 
                        cantidad,
                        costo_unitario, 
                        precio_unitario, 
                        subtotal,
                        user_id
                    ))
                    
                    # DESCONTAR de inventario_bodega
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                except Exception as prod_error:
                    print(f"Error con producto {prod.get('id_producto', 'desconocido')}: {prod_error}")
                    continue
            
            flash(f"✅ Salida registrada exitosamente! ID Movimiento: {id_movimiento}", 'success')
            
            # Redirigir según tipo
            if id_tipo_movimiento == TIPO_VENTA and id_factura_venta:
                return redirect(url_for('admin_detalle_factura', id_factura=id_factura_venta))
            else:
                return redirect(url_for('admin_detalle_movimiento', id_movimiento=id_movimiento))
            
    except Exception as e:
        flash(f"❌ Error al procesar salida: {str(e)}", 'error')
        return redirect(url_for('admin_nueva_salida_form'))

# API para obtener productos con stock por bodega (para salidas)
@app.route('/api/productos/stock-bodega')
@admin_required
def api_productos_stock_bodega():
    """API para obtener productos con stock disponible en una bodega específica"""
    try:
        bodega_id = request.args.get('bodega')
        
        if not bodega_id:
            return jsonify({'error': 'Se requiere ID de bodega'}), 400
        
        with get_db_cursor(True) as cursor:
            # Obtener productos activos con stock en la bodega específica
            cursor.execute("""
                SELECT 
                    p.ID_Producto, 
                    p.COD_Producto, 
                    p.Descripcion, 
                    p.Unidad_Medida, 
                    um.Descripcion as Unidad_Descripcion,
                    p.Precio_Venta, 
                    p.Stock_Minimo,
                    cp.Descripcion as Categoria_Descripcion,
                    COALESCE(ib.Existencias, 0) as Stock_Bodega,
                    COALESCE(SUM(ib_total.Existencias), 0) as Existencias_Totales
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN inventario_bodega ib_total ON p.ID_Producto = ib_total.ID_Producto
                WHERE p.Estado = 'activo'
                    AND COALESCE(ib.Existencias, 0) > 0
                GROUP BY p.ID_Producto, p.COD_Producto, p.Descripcion, 
                         p.Unidad_Medida, p.Precio_Venta, p.Stock_Minimo,
                         um.Descripcion, cp.Descripcion, ib.Existencias
                ORDER BY p.Descripcion
                LIMIT 100
            """, (bodega_id,))
            
            productos = cursor.fetchall()
            
            # Convertir a lista de diccionarios y formatear números
            productos_list = []
            for producto in productos:
                producto_dict = dict(producto)
                producto_dict['Precio_Venta'] = float(producto_dict['Precio_Venta'] or 0)
                producto_dict['Stock_Bodega'] = float(producto_dict['Stock_Bodega'] or 0)
                producto_dict['Existencias_Totales'] = float(producto_dict['Existencias_Totales'] or 0)
                producto_dict['Stock_Minimo'] = float(producto_dict['Stock_Minimo'] or 0)
                productos_list.append(producto_dict)
            
            return jsonify(productos_list)
            
    except Exception as e:
        print(f"Error en API productos stock bodega: {e}")
        return jsonify({'error': str(e)}), 500

# 6. NUEVA TRANSFERENCIA (Traslado)
@app.route('/admin/movimientos/transferencia/nueva')
@admin_required
def admin_nueva_transferencia_form():
    """Mostrar formulario para transferencia entre bodegas"""
    try:
        with get_db_cursor(True) as cursor:
            # Solo mostrar tipo Traslado
            cursor.execute("""
                SELECT * FROM catalogo_movimientos 
                WHERE ID_TipoMovimiento = %s
            """, (TIPO_TRASLADO,))
            
            tipos_movimiento = cursor.fetchall()
            
            # Obtener bodegas
            cursor.execute("""
                SELECT * FROM bodegas 
                WHERE Estado = 1 
                ORDER BY Nombre
            """)
            bodegas = cursor.fetchall()
            
            return render_template('admin/movimientos/nueva_transferencia.html',
                                 tipos_movimiento=tipos_movimiento,
                                 bodegas=bodegas)
    except Exception as e:
        flash(f"Error al cargar formulario: {str(e)}", 'error')
        return redirect(url_for('admin_historial_movimientos'))

# 7. PROCESAR TRANSFERENCIA
@app.route('/admin/movimientos/transferencia/procesar', methods=['POST'])
@admin_required
@bitacora_decorator("PROCESAR-TRANSFERENCIA")
def admin_procesar_transferencia():
    """Procesar transferencia entre bodegas"""
    try:
        fecha = request.form.get('fecha')
        id_bodega_origen = int(request.form.get('id_bodega_origen'))
        id_bodega_destino = int(request.form.get('id_bodega_destino'))
        ubicacion_entrega = request.form.get('ubicacion_entrega')
        observacion = request.form.get('observacion')
        
        # Validaciones
        if not all([fecha, id_bodega_origen, id_bodega_destino]):
            flash("Fecha y bodegas son requeridas", 'error')
            return redirect(url_for('admin_nueva_transferencia_form'))
        
        if id_bodega_origen == id_bodega_destino:
            flash("La bodega de origen y destino no pueden ser la misma", 'error')
            return redirect(url_for('admin_nueva_transferencia_form'))
        
        productos_json = request.form.get('productos')
        if not productos_json:
            flash("Debe agregar al menos un producto", 'error')
            return redirect(url_for('admin_nueva_transferencia_form'))
        
        productos = json.loads(productos_json)
        
        with get_db_cursor() as cursor:
            # VERIFICAR STOCK en bodega origen
            productos_insuficientes = []
            
            for prod in productos:
                cursor.execute("""
                    SELECT Existencias 
                    FROM inventario_bodega 
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (id_bodega_origen, prod['id_producto']))
                
                stock = cursor.fetchone()
                cantidad = Decimal(str(prod['cantidad']))
                
                stock_disponible = stock['Existencias'] if stock else Decimal('0')
                
                if stock_disponible < cantidad:
                    cursor.execute("SELECT Descripcion FROM productos WHERE ID_Producto = %s", 
                                 (prod['id_producto'],))
                    producto_info = cursor.fetchone()
                    producto_nombre = producto_info['Descripcion'] if producto_info else 'Producto desconocido'
                    
                    productos_insuficientes.append({
                        'producto': producto_nombre,
                        'solicitado': float(cantidad),
                        'disponible': float(stock_disponible)
                    })
            
            if productos_insuficientes:
                mensaje_error = "Stock insuficiente en bodega origen:<br>"
                for item in productos_insuficientes:
                    mensaje_error += f"- {item['producto']}: Solicitado {item['solicitado']}, Disponible {item['disponible']}<br>"
                flash(mensaje_error, 'error')
                return redirect(url_for('admin_nueva_transferencia_form'))
            
            # Insertar movimiento de transferencia
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (ID_TipoMovimiento, Fecha, ID_Bodega, ID_Bodega_Destino,
                 UbicacionEntrega, Observacion, ID_Empresa, ID_Usuario_Creacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                TIPO_TRASLADO, fecha, id_bodega_origen, id_bodega_destino,
                ubicacion_entrega, observacion, session.get('id_empresa', 1), 
                session.get('user_id')
            ))
            
            id_movimiento = cursor.lastrowid
            
            # Procesar productos
            for prod in productos:
                cantidad = Decimal(str(prod['cantidad']))
                
                # Obtener costo promedio
                cursor.execute("""
                    SELECT Costo_Unitario 
                    FROM detalle_movimientos_inventario dmi
                    JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                    JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    WHERE dmi.ID_Producto = %s 
                    AND cm.Letra = 'E'
                    ORDER BY mi.Fecha DESC, dmi.ID_Detalle_Movimiento DESC
                    LIMIT 1
                """, (prod['id_producto'],))
                
                costo_result = cursor.fetchone()
                costo_unitario = Decimal(str(costo_result['Costo_Unitario'] if costo_result else 0))
                subtotal = cantidad * costo_unitario
                
                # Insertar detalle
                cursor.execute("""
                    INSERT INTO detalle_movimientos_inventario
                    (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario,
                     Subtotal, ID_Usuario_Creacion)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_movimiento, prod['id_producto'], cantidad,
                    costo_unitario, subtotal, session.get('user_id')
                ))
                
                # DESCONTAR de bodega origen
                cursor.execute("""
                    UPDATE inventario_bodega 
                    SET Existencias = Existencias - %s
                    WHERE ID_Bodega = %s AND ID_Producto = %s
                """, (cantidad, id_bodega_origen, prod['id_producto']))
                
                # AGREGAR a bodega destino
                cursor.execute("""
                    INSERT INTO inventario_bodega (ID_Bodega, ID_Producto, Existencias)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    Existencias = Existencias + VALUES(Existencias)
                """, (id_bodega_destino, prod['id_producto'], cantidad))
                
                # NOTA: Existencias generales NO cambian (solo se transfiere)
            
            flash(f"✅ Transferencia registrada exitosamente! ID: {id_movimiento}", 'success')
            return redirect(url_for('admin_detalle_movimiento', id_movimiento=id_movimiento))
            
    except Exception as e:
        flash(f"❌ Error al procesar transferencia: {str(e)}", 'error')
        return redirect(url_for('admin_nueva_transferencia_form'))

# 8. DETALLE DE MOVIMIENTO
@app.route('/admin/movimientos/detalle/<int:id_movimiento>')
@admin_required
def admin_detalle_movimiento(id_movimiento):
    """Ver detalle completo de un movimiento"""
    try:
        with get_db_cursor(True) as cursor:
            # Movimiento principal
            cursor.execute("""
                SELECT mi.*, 
                       cm.Descripcion as Tipo_Movimiento_Descripcion,
                       cm.Letra,
                       bo.Nombre as Bodega_Origen_Nombre,
                       bd.Nombre as Bodega_Destino_Nombre,
                       p.Nombre as Proveedor_Nombre,
                       cl.Nombre as Cliente_Nombre,
                       f.Fecha as Factura_Fecha,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       emp.Nombre_Empresa
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN facturacion f ON mi.ID_Factura_Venta = f.ID_Factura
                LEFT JOIN clientes cl ON f.IDCliente = cl.ID_Cliente
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa emp ON mi.ID_Empresa = emp.ID_Empresa
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado", 'error')
                return redirect(url_for('admin_historial_movimientos'))
            
            # Detalle de productos
            cursor.execute("""
                SELECT dmi.*, 
                       p.COD_Producto, p.Descripcion as Producto_Descripcion,
                       um.Descripcion as Unidad_Medida_Descripcion,
                       um.Abreviatura as Unidad_Abreviatura,
                       cp.Descripcion as Categoria_Descripcion,
                       u.NombreUsuario as Usuario_Creacion_Nombre,
                       ib.Existencias as Stock_Actual
                FROM detalle_movimientos_inventario dmi
                JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN categorias_producto cp ON p.ID_Categoria = cp.ID_Categoria
                LEFT JOIN usuarios u ON dmi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (movimiento['ID_Bodega'], id_movimiento))
            
            detalle = cursor.fetchall()
            
            # Calcular totales
            total_cantidad = sum(Decimal(str(d['Cantidad'])) for d in detalle)
            total_costo = sum(Decimal(str(d['Subtotal'] or 0)) for d in detalle)
            
            # Para ventas, calcular total precio
            total_precio = 0
            if movimiento['Letra'] == 'S':
                total_precio = sum(Decimal(str(d['Precio_Unitario'] or 0)) * 
                                 Decimal(str(d['Cantidad'])) for d in detalle)
            
            return render_template('admin/movimientos/detalle_movimiento.html',
                                 movimiento=movimiento,
                                 detalle=detalle,
                                 total_cantidad=total_cantidad,
                                 total_costo=total_costo,
                                 total_precio=total_precio)
            
    except Exception as e:
        flash(f"Error al cargar detalle: {str(e)}", 'error')
        return redirect(url_for('admin_historial_movimientos'))

# 9. REPORTES PRINCIPAL
@app.route('/admin/movimientos/reportes')
@admin_required
def admin_reportes_movimientos():
    """Página principal de reportes"""
    try:
        with get_db_cursor(True) as cursor:
            # Tipos de movimiento para filtro
            cursor.execute("SELECT * FROM catalogo_movimientos ORDER BY Descripcion")
            tipos_movimiento = cursor.fetchall()
            
            # Bodegas para filtro
            cursor.execute("SELECT * FROM bodegas WHERE Estado = 1 ORDER BY Nombre")
            bodegas = cursor.fetchall()
            
            # Estadísticas del mes
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_movimientos,
                    SUM(CASE WHEN cm.Letra = 'E' THEN 1 ELSE 0 END) as entradas,
                    SUM(CASE WHEN cm.Letra = 'S' THEN 1 ELSE 0 END) as salidas,
                    SUM(CASE WHEN cm.ID_TipoMovimiento = 6 THEN 1 ELSE 0 END) as transferencias,
                    (SELECT SUM(dmi.Subtotal) 
                     FROM detalle_movimientos_inventario dmi
                     JOIN movimientos_inventario mi2 ON dmi.ID_Movimiento = mi2.ID_Movimiento
                     JOIN catalogo_movimientos cm2 ON mi2.ID_TipoMovimiento = cm2.ID_TipoMovimiento
                     WHERE mi2.Estado = 1 AND cm2.Letra = 'E'
                     AND MONTH(mi2.Fecha) = MONTH(CURRENT_DATE())
                     AND YEAR(mi2.Fecha) = YEAR(CURRENT_DATE())) as total_compras,
                    (SELECT SUM(dmi.Precio_Unitario * dmi.Cantidad) 
                     FROM detalle_movimientos_inventario dmi
                     JOIN movimientos_inventario mi2 ON dmi.ID_Movimiento = mi2.ID_Movimiento
                     JOIN catalogo_movimientos cm2 ON mi2.ID_TipoMovimiento = cm2.ID_TipoMovimiento
                     WHERE mi2.Estado = 1 AND cm2.Letra = 'S'
                     AND MONTH(mi2.Fecha) = MONTH(CURRENT_DATE())
                     AND YEAR(mi2.Fecha) = YEAR(CURRENT_DATE())) as total_ventas
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.Estado = 1 
                AND MONTH(mi.Fecha) = MONTH(CURRENT_DATE())
                AND YEAR(mi.Fecha) = YEAR(CURRENT_DATE())
            """)
            estadisticas = cursor.fetchone()
            
            # Últimos movimientos
            cursor.execute("""
                SELECT mi.ID_Movimiento, mi.Fecha, cm.Descripcion as Tipo,
                       cm.Letra, bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                       u.NombreUsuario as Usuario,
                       (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Productos,
                       (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                WHERE mi.Estado = 1
                ORDER BY mi.ID_Movimiento DESC
                LIMIT 10
            """)
            ultimos_movimientos = cursor.fetchall()
            
            # Productos con stock bajo - CORREGIDO
            cursor.execute("""
                SELECT p.Descripcion, p.COD_Producto, 
                       COALESCE(SUM(ib.Existencias), 0) as Existencias_Totales,
                       p.Stock_Minimo,
                       um.Descripcion as Unidad_Medida,
                       (SELECT COUNT(*) FROM inventario_bodega 
                        WHERE ID_Producto = p.ID_Producto 
                        AND Existencias > 0) as Bodegas_Con_Stock
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.Estado = 1
                GROUP BY p.ID_Producto, p.Descripcion, p.COD_Producto, 
                         p.Stock_Minimo, um.Descripcion
                HAVING COALESCE(SUM(ib.Existencias), 0) <= p.Stock_Minimo
                ORDER BY (COALESCE(SUM(ib.Existencias), 0) / NULLIF(p.Stock_Minimo, 0)) ASC
                LIMIT 10
            """)
            productos_stock_bajo = cursor.fetchall()
            
            return render_template('admin/movimientos/reportes.html',
                                 tipos_movimiento=tipos_movimiento,
                                 bodegas=bodegas,
                                 estadisticas=estadisticas,
                                 ultimos_movimientos=ultimos_movimientos,
                                 productos_stock_bajo=productos_stock_bajo)
            
    except Exception as e:
        flash(f"Error al cargar reportes: {str(e)}", 'error')
        return redirect(url_for('admin_dashboard'))

# 10. REPORTE FILTRADO
@app.route('/admin/movimientos/reporte/filtrar', methods=['POST'])
@admin_required
def admin_reporte_filtrado():
    """Generar reporte con filtros"""
    try:
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        id_tipo_movimiento = request.form.get('id_tipo_movimiento')
        id_bodega = request.form.get('id_bodega')
        
        # Construir consulta
        query = """
            SELECT mi.ID_Movimiento, mi.Fecha, cm.Descripcion as Tipo_Movimiento,
                   cm.Letra, bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                   p.Nombre as Proveedor, u.NombreUsuario as Usuario,
                   mi.Observacion, mi.Tipo_Compra, mi.N_Factura_Externa,
                   (SELECT COUNT(*) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Cantidad_Productos,
                   (SELECT SUM(Subtotal) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Costo,
                   (SELECT SUM(Precio_Unitario * Cantidad) FROM detalle_movimientos_inventario 
                    WHERE ID_Movimiento = mi.ID_Movimiento) as Total_Precio
            FROM movimientos_inventario mi
            LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
            LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
            LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
            LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
            LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
            WHERE mi.Estado = 1
        """
        
        params = []
        
        if fecha_inicio:
            query += " AND mi.Fecha >= %s"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND mi.Fecha <= %s"
            params.append(fecha_fin)
        if id_tipo_movimiento and id_tipo_movimiento != 'todos':
            query += " AND mi.ID_TipoMovimiento = %s"
            params.append(id_tipo_movimiento)
        if id_bodega and id_bodega != 'todas':
            query += " AND (mi.ID_Bodega = %s OR mi.ID_Bodega_Destino = %s)"
            params.extend([id_bodega, id_bodega])
        
        query += " ORDER BY mi.Fecha DESC, mi.ID_Movimiento DESC"
        
        with get_db_cursor(True) as cursor:
            cursor.execute(query, tuple(params))
            movimientos = cursor.fetchall()
            
            # Calcular totales
            total_movimientos = len(movimientos)
            total_costo = sum(Decimal(str(m['Total_Costo'] or 0)) for m in movimientos)
            total_precio = sum(Decimal(str(m['Total_Precio'] or 0)) for m in movimientos)
            
            return render_template('admin/movimientos/reporte_filtrado.html',
                                 movimientos=movimientos,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 total_movimientos=total_movimientos,
                                 total_costo=total_costo,
                                 total_precio=total_precio)
            
    except Exception as e:
        flash(f"Error al generar reporte: {str(e)}", 'error')
        return redirect(url_for('admin_reportes_movimientos'))

# 11. ANULAR MOVIMIENTO
@app.route('/admin/movimientos/anular/<int:id_movimiento>', methods=['POST'])
@admin_required
@bitacora_decorator("ANULAR-MOVIMIENTO")
def admin_anular_movimiento(id_movimiento):
    """Anular un movimiento y revertir inventario"""
    try:
        motivo = request.form.get('motivo', 'Sin motivo especificado')
        
        with get_db_cursor() as cursor:
            # Obtener información del movimiento
            cursor.execute("""
                SELECT mi.*, cm.Descripcion, cm.Letra
                FROM movimientos_inventario mi
                JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                WHERE mi.ID_Movimiento = %s AND mi.Estado = 1
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado o ya anulado", 'warning')
                return redirect(url_for('admin_historial_movimientos'))
            
            # Obtener detalle del movimiento
            cursor.execute("""
                SELECT * FROM detalle_movimientos_inventario
                WHERE ID_Movimiento = %s
            """, (id_movimiento,))
            
            detalles = cursor.fetchall()
            
            # Revertir inventario según tipo
            letra = movimiento['Letra']
            
            for detalle in detalles:
                cantidad = Decimal(str(detalle['Cantidad']))
                id_producto = detalle['ID_Producto']
                id_bodega = movimiento['ID_Bodega']
                
                if letra == 'E':  # Entrada → Descontar
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    cursor.execute("""
                        UPDATE productos 
                        SET Existencias = Existencias - %s
                        WHERE ID_Producto = %s
                    """, (cantidad, id_producto))
                    
                elif letra == 'S':  # Salida → Agregar
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias + %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    cursor.execute("""
                        UPDATE productos 
                        SET Existencias = Existencias + %s
                        WHERE ID_Producto = %s
                    """, (cantidad, id_producto))
                    
                elif movimiento['ID_TipoMovimiento'] == TIPO_TRASLADO:  # Transferencia
                    id_bodega_destino = movimiento['ID_Bodega_Destino']
                    
                    # Revertir origen (agregar)
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias + %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega, id_producto))
                    
                    # Revertir destino (descontar)
                    cursor.execute("""
                        UPDATE inventario_bodega 
                        SET Existencias = Existencias - %s
                        WHERE ID_Bodega = %s AND ID_Producto = %s
                    """, (cantidad, id_bodega_destino, id_producto))
            
            # Marcar movimiento como anulado
            cursor.execute("""
                UPDATE movimientos_inventario 
                SET Estado = 0, 
                    Fecha_Modificacion = NOW(),
                    ID_Usuario_Modificacion = %s,
                    Observacion = CONCAT(COALESCE(Observacion, ''), 
                    ' | ANULADO: ', %s)
                WHERE ID_Movimiento = %s
            """, (session.get('user_id'), motivo, id_movimiento))
            
            flash(f"✅ Movimiento #{id_movimiento} anulado exitosamente", 'success')
            
    except Exception as e:
        flash(f"❌ Error al anular movimiento: {str(e)}", 'error')
    
    return redirect(url_for('admin_historial_movimientos'))

# 12. API PARA OBTENER STOCK
@app.route('/api/inventario/stock/<int:id_producto>/<int:id_bodega>')
@admin_required
def api_obtener_stock(id_producto, id_bodega):
    """Obtener stock de un producto en una bodega específica"""
    try:
        with get_db_cursor(True) as cursor:
            cursor.execute("""
                SELECT p.ID_Producto, p.Descripcion, p.COD_Producto,
                       ib.Existencias, p.Existencias as Total_General,
                       p.Precio_Venta, p.Stock_Minimo,
                       um.Descripcion as Unidad_Medida
                FROM productos p
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
                    AND ib.ID_Bodega = %s
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE p.ID_Producto = %s AND p.Estado = 1
            """, (id_bodega, id_producto))
            
            producto = cursor.fetchone()
            
            if not producto:
                return jsonify({'error': 'Producto no encontrado'}), 404
            
            return jsonify({
                'success': True,
                'producto': producto
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# 13. API PARA BUSCAR PRODUCTOS
@app.route('/api/productos/buscar')
@admin_required
def api_buscar_productos():
    """Buscar productos por código o descripción"""
    try:
        termino = request.args.get('q', '')
        id_bodega = request.args.get('bodega', '')
        
        if not termino:
            return jsonify([])
        
        with get_db_cursor(True) as cursor:
            query = """
                SELECT p.ID_Producto, p.COD_Producto, p.Descripcion, 
                       p.Unidad_Medida, um.Descripcion as Unidad_Descripcion,
                       p.Precio_Venta, p.Existencias as Stock_General,
                       ib.Existencias as Stock_Bodega,
                       p.Stock_Minimo
                FROM productos p
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                LEFT JOIN inventario_bodega ib ON p.ID_Producto = ib.ID_Producto 
            """
            
            params = []
            
            if id_bodega:
                query += " AND ib.ID_Bodega = %s"
                params.append(id_bodega)
            
            query += """
                WHERE (p.COD_Producto LIKE %s OR p.Descripcion LIKE %s) 
                AND p.Estado = 1
                ORDER BY p.Descripcion
                LIMIT 20
            """
            
            params.extend([f"%{termino}%", f"%{termino}%"])
            
            cursor.execute(query, tuple(params))
            productos = cursor.fetchall()
            
            return jsonify(productos)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

# 14. IMPRIMIR MOVIMIENTO
@app.route('/admin/movimientos/imprimir/<int:id_movimiento>')
@admin_required
def admin_imprimir_movimiento(id_movimiento):
    """Generar PDF para impresión del movimiento"""
    try:
        with get_db_cursor(True) as cursor:
            # Similar a detalle_movimiento pero optimizado para impresión
            cursor.execute("""
                SELECT mi.*, cm.Descripcion as Tipo_Movimiento,
                       bo.Nombre as Bodega_Origen, bd.Nombre as Bodega_Destino,
                       p.Nombre as Proveedor, u.NombreUsuario as Usuario,
                       emp.Nombre_Empresa, emp.RUC, emp.Direccion, emp.Telefono
                FROM movimientos_inventario mi
                LEFT JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                LEFT JOIN bodegas bo ON mi.ID_Bodega = bo.ID_Bodega
                LEFT JOIN bodegas bd ON mi.ID_Bodega_Destino = bd.ID_Bodega
                LEFT JOIN proveedores p ON mi.ID_Proveedor = p.ID_Proveedor
                LEFT JOIN usuarios u ON mi.ID_Usuario_Creacion = u.ID_Usuario
                LEFT JOIN empresa emp ON mi.ID_Empresa = emp.ID_Empresa
                WHERE mi.ID_Movimiento = %s
            """, (id_movimiento,))
            
            movimiento = cursor.fetchone()
            
            if not movimiento:
                flash("Movimiento no encontrado", 'error')
                return redirect(url_for('admin_historial_movimientos'))
            
            # Detalle
            cursor.execute("""
                SELECT dmi.*, p.Descripcion as Producto, p.COD_Producto,
                       um.Abreviatura as Unidad
                FROM detalle_movimientos_inventario dmi
                JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                LEFT JOIN unidades_medida um ON p.Unidad_Medida = um.ID_Unidad
                WHERE dmi.ID_Movimiento = %s
                ORDER BY dmi.ID_Detalle_Movimiento
            """, (id_movimiento,))
            
            detalle = cursor.fetchall()
            
            # Aquí normalmente generarías un PDF
            # Por ahora, redirigimos a una página de impresión
            return render_template('admin/movimientos/imprimir_movimiento.html',
                                 movimiento=movimiento,
                                 detalle=detalle)
            
    except Exception as e:
        flash(f"Error al generar impresión: {str(e)}", 'error')
        return redirect(url_for('admin_detalle_movimiento', id_movimiento=id_movimiento))

#Iniciar Aplicación
if __name__ == '__main__':
    
    os.makedirs('templates/admin', exist_ok=True)
    os.makedirs('templates/vendedor', exist_ok=True)
    os.makedirs('templates/jefe_galera', exist_ok=True)
    
    # Ejecutar diagnóstico al iniciar
    print("🚀 Iniciando aplicación...")
    test_connection()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
