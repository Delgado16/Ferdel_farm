"""
Blueprint de rutas principales (home, health, diagnostics)
"""
from flask import Blueprint, abort, redirect, url_for, jsonify, render_template, send_from_directory, current_app
from flask_login import login_required, current_user
from datetime import datetime
from config.settings import RENDER_ENV, RAILWAY_ENV
from config.database import get_db_cursor, diagnose_db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    """Ruta raíz - redirige al dashboard si está autenticado"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Ruta de dashboard que redirige según el rol"""
    if current_user.rol == 'Administrador':
        return redirect(url_for('admin.admin_dashboard'))
    elif current_user.rol == 'Vendedor':
        return redirect(url_for('vendedor.vendedor_dashboard'))
    elif current_user.rol == 'Bodega':
        return redirect(url_for('bodega.bodega_dashboard'))
    else:
        abort(403)


@main_bp.route('/health')
def health_check():
    """Endpoint para monitoreo en Render"""
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'environment': 'render' if RENDER_ENV else ('railway' if RAILWAY_ENV else 'development'),
        'database': False
    }
    
    # Probar base de datos
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1")
            status['database'] = True
    except Exception as e:
        status['database'] = False
        status['error'] = str(e)
        status['status'] = 'unhealthy'
    
    return jsonify(status)


@main_bp.route('/debug-db')
def debug_db():
    """Diagnóstico rápido de BD"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT DATABASE() as db, VERSION() as version, NOW() as current_time")
            result = cursor.fetchone()
            return jsonify({
                'connected': True,
                'database': result['db'],
                'mysql_version': result['version'],
                'server_time': result['current_time'].isoformat() if result['current_time'] else None,
                'render_env': RENDER_ENV,
                'railway_env': RAILWAY_ENV,
            })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'render_env': RENDER_ENV,
            'railway_env': RAILWAY_ENV
        }), 500


@main_bp.route('/diagnostico', methods=["GET"])
def diagnostico():
    """Página de diagnóstico para verificar el estado de la BD"""
    result = diagnose_db()
    return f"""
    <h1>Diagnóstico de Base de Datos</h1>
    <p>Resultado: {'✅ Éxito' if result else '❌ Fallo'}</p>
    <p>Ver logs detallados en la consola del servidor.</p>
    <p><a href="/auth/login">Ir al login</a> | <a href="/auth/fix-admin">Corregir admin</a> | <a href="/auth/check-users">Ver usuarios</a></p>
    """


@main_bp.route('/sw.js')
def serve_sw():
    return send_from_directory(current_app.static_folder, 'sw.js')


@main_bp.route('/manifest.json')
def serve_manifest():
    return send_from_directory(current_app.static_folder, 'manifest.json')


@main_bp.route('/test-403')
def test_403():
    abort(403)


@main_bp.app_errorhandler(403)
def forbidden_error(error):
    """Manejador de error global para 403 Prohibido"""
    from flask import request
    
    # Si la petición acepta JSON (como peticiones AJAX o API), retornamos JSON
    accept = request.headers.get('Accept', '')
    if request.path.startswith('/api/') or \
       request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
       ('application/json' in accept and 'text/html' not in accept):
        return jsonify({
            'status': 'error',
            'error': 'Prohibido',
            'message': 'No tienes permiso para acceder al recurso solicitado. Está protegida contra lectura o no es legible para el servidor.'
        }), 403
        
    return render_template('errors/403.html'), 403


