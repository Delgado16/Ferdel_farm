"""
Configuración de Gunicorn para producción (Railway / Render / Linux)
Optimizado para bajo consumo de RAM, concurrencia gthread y gestión limpia de procesos.
"""
import os
import multiprocessing

# Dirección y puerto de enlace
port = os.environ.get('PORT', '5000')
bind = f"0.0.0.0:{port}"

# Concurrencia de Workers y Threads
# Recomendado en Railway: 2 workers con 4 threads cada uno (8 solicitudes concurrentes)
workers = int(os.environ.get('GUNICORN_WORKERS', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
worker_class = 'gthread'

# Timeouts y Keep-Alive
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Prevención de fugas de memoria: reinicio cíclico controlado de workers
max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '50'))

# En Linux / Railway, usar memoria compartida para latidos de workers
if os.path.exists('/dev/shm'):
    worker_tmp_dir = '/dev/shm'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()

# No pre-cargar app para asegurar que cada worker tenga su propio pool independiente
preload_app = False


def on_starting(server):
    server.log.info("🚀 Iniciando Gunicorn para FERDEL FARM...")
    server.log.info(f"   Workers: {workers} | Threads: {threads} | Worker Class: {worker_class}")
    server.log.info(f"   Bind: {bind} | Timeout: {timeout}s | Max Requests: {max_requests}")


def worker_exit(server, worker):
    """Cierra conexiones al salir el worker"""
    try:
        from config.database import connection_pool
        # El recolector de basura de Python y cierre de proceso liberan las conexiones
        server.log.info(f"Worker {worker.pid} cerrando limpiamente sus recursos.")
    except Exception:
        pass

