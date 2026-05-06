"""
Blueprint de autenticación (login, logout, reset)
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from config.database import get_db_cursor
from auth import User
from helpers.bitacora import registrar_login_exitoso, registrar_login_fallido, registrar_logout

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Ruta de login"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    session.clear()
    
    if request.method == 'POST':
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        print(f"\n🔐 Intento de login - Usuario: '{username}'")
        
        if not username:
            flash("El nombre de usuario es requerido", "danger")
            registrar_login_fallido(username, "Usuario vacio")
            return render_template('login.html')
        
        if not password:
            flash("La contraseña es requerida", "danger")
            registrar_login_fallido(username, "Contraseña vacia")
            return render_template('login.html')
        
        if len(password) < 4:
            flash("La contraseña debe tener al menos 4 caracteres", "danger")
            return render_template('login.html')
        
        try:
            with get_db_cursor() as cursor:
                # Consulta case-insensitive para estado
                cursor.execute("""
                    SELECT u.ID_Usuario, u.NombreUsuario, u.Contraseña, r.Nombre_Rol 
                    FROM usuarios u 
                    JOIN roles r ON u.ID_Rol = r.ID_Rol 
                    WHERE u.NombreUsuario = %s AND UPPER(u.Estado) = 'ACTIVO' AND r.Estado = 'Activo'
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
                            print(f"✅ Usuario {username} ha iniciado sesión - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('main.dashboard'))
                        else:
                            print("❌ Contraseña incorrecta (hash)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                    else:
                        # Contraseña en texto plano (temporal)
                        if user_data['Contraseña'] == password:
                            user = User(user_data['ID_Usuario'], user_data['NombreUsuario'], user_data['Nombre_Rol'])
                            login_user(user)
                            registrar_login_exitoso(username, user_data['ID_Usuario'])
                            print(f"✅ Usuario {username} ha iniciado sesión (texto plano) - Rol: {user_data['Nombre_Rol']}")
                            flash(f"¡Bienvenido {user.username}!", "success")
                            return redirect(url_for('main.dashboard'))
                        else:
                            print("❌ Contraseña incorrecta (texto plano)")
                            registrar_login_fallido(username, "contraseña incorrecta")
                            flash("Credenciales incorrectas. Por favor verifique sus datos.", "danger")
                else:
                    print("❌ Usuario no encontrado o inactivo")
                    registrar_login_fallido(username, "usuario no encontrado o inactivo")
                    flash("Credenciales incorrectas o usuario inactivo.", "danger")
                
        except Exception as e:
            print(f"❌ Error en login: {e}")
            registrar_login_fallido(username, f"Error del sistema: {e}")
            flash("Error interno del sistema. Intente más tarde.", "danger")
        
        return render_template('login.html')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Ruta de logout"""
    registrar_logout(current_user.id)
    logout_user()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/reset-admin')
def reset_admin():
    """Reset completo del usuario admin (RUTA TEMPORAL)"""
    try:
        with get_db_cursor() as cursor:
            # Resetear a texto plano temporalmente
            cursor.execute("""
                UPDATE usuarios 
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
        <p><a href="/auth/login">Ir al login</a></p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@auth_bp.route('/fix-admin')
def fix_admin():
    """Corregir el usuario admin (RUTA TEMPORAL - ELIMINAR DESPUÉS)"""
    try:
        with get_db_cursor() as cursor:
            # 1. Corregir estado (case-insensitive)
            cursor.execute("UPDATE usuarios SET Estado = 'Activo' WHERE ID_Usuario = 2")
            
            # 2. Crear hash válido para la contraseña
            hashed_password = generate_password_hash('Admin123$')
            cursor.execute("UPDATE usuarios SET Contraseña = %s WHERE ID_Usuario = 2", (hashed_password,))
            
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
        <p><a href="/auth/login">Ir al login</a></p>
        <p style='color: red; font-weight: bold;'>⚠️ RECUERDA ELIMINAR ESTA RUTA /auth/fix-admin DESPUÉS DE USAR</p>
        """
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"

@auth_bp.route('/check-users')
def check_users():
    """Ver todos los usuarios (RUTA TEMPORAL - ELIMINAR DESPUÉS)"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado, Contraseña FROM usuarios")
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
            
            return result + "<p><a href='/auth/login'>Ir al login</a></p>"
    except Exception as e:
        return f"<h1>❌ Error:</h1><p>{e}</p>"
