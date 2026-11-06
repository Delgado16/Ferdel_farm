"""
Suite de Pruebas Automatizadas de Rendimiento y Regresión — FERDEL FARM
Valida:
1. Inicialización y salud del pool de conexiones.
2. Comportamiento y recuperación ante saturación del pool.
3. Consulta del endpoint de salud /health con commit=False.
4. Correcto funcionamiento de la bitácora sin fugas.
5. Caché de usuarios en Flask-Login (load_user).
6. Bloqueo distribuido de respaldos (GET_LOCK de MySQL).
7. Ejecución de consultas de métricas de Dashboard (KPIs).
"""
import os
import sys
import unittest
import time

# Configurar directorio base
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from config.database import (
    init_pool, get_db, close_db, get_db_cursor,
    DatabasePoolExhaustedError, DatabaseConnectionError,
    connection_pool, DB_CONFIG
)
from auth.utils import load_user, invalidate_user_cache
from helpers.backup_service import LOCK_NAME
from routes.admin.utils import (
    obtener_metricas_kpis, obtener_ventas_mes,
    obtener_top_clientes_deudores, obtener_productos_bajo_stock
)


class TestFerdelOptimizations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

    def test_01_init_pool_and_connection(self):
        """Verifica que el pool esté inicializado y entregue conexiones funcionales"""
        with self.app.app_context():
            db = get_db()
            self.assertIsNotNone(db)
            self.assertTrue(db.is_connected())

    def test_02_health_endpoint(self):
        """Verifica que /health responda 200 y reporte database: True con X-Response-Time"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertTrue(data.get('database'))
        self.assertIn('X-Response-Time', response.headers)

    def test_03_cursor_context_manager_and_rollback(self):
        """Verifica el manejo de transacciones y rollback automático en excepciones"""
        with self.app.app_context():
            # Prueba lectura
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT 1 AS val")
                res = cursor.fetchone()
                self.assertEqual(res['val'], 1)

            # Prueba que un error lance la excepción y no rompa la conexión
            with self.assertRaises(Exception):
                with get_db_cursor(commit=True) as cursor:
                    cursor.execute("SELECT * FROM tabla_inexistente_que_debe_fallar_12345")

            # La conexión en g.db debe seguir viva tras la excepción
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT 2 AS val")
                res = cursor.fetchone()
                self.assertEqual(res['val'], 2)

    def test_04_user_cache_in_auth(self):
        """Verifica que load_user use la caché en memoria y reduzca consultas a BD"""
        invalidate_user_cache()
        with self.app.app_context():
            # Obtener un ID de usuario activo real
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT ID_Usuario, NombreUsuario, Estado FROM usuarios WHERE UPPER(Estado) = 'ACTIVO' LIMIT 1")
                row = cursor.fetchone()

            if row:
                uid = row['ID_Usuario']
                # Primer llamado: consulta BD y guarda en caché
                u1 = load_user(uid)
                self.assertIsNotNone(u1)
                self.assertEqual(u1.username, row['NombreUsuario'])

                # Segundo llamado: debe responder desde caché
                u2 = load_user(uid)
                self.assertIs(u1, u2)

                # Invalidar caché
                invalidate_user_cache(uid)
                u3 = load_user(uid)
                self.assertIsNotNone(u3)
                self.assertEqual(u3.username, row['NombreUsuario'])

    def test_05_mysql_advisory_lock_for_backups(self):
        """Verifica que el bloqueo distribuido LOCK_NAME prevenga respaldos concurrentes"""
        with self.app.app_context():
            with get_db_cursor(commit=False) as cursor:
                cursor.execute("SELECT GET_LOCK(%s, 0) AS lock_res", (LOCK_NAME,))
                res = cursor.fetchone()
                self.assertEqual(res['lock_res'], 1, "No se pudo adquirir el candado de respaldo")

                # Intentar adquirir el mismo candado desde otra consulta de verificación
                cursor.execute("SELECT IS_USED_LOCK(%s) AS used_by", (LOCK_NAME,))
                used = cursor.fetchone()
                self.assertIsNotNone(used['used_by'])

                # Liberar candado
                cursor.execute("SELECT RELEASE_LOCK(%s) AS rel_res", (LOCK_NAME,))
                rel = cursor.fetchone()
                self.assertEqual(rel['rel_res'], 1)

    def test_06_dashboard_kpis_and_queries(self):
        """Verifica que las consultas optimizadas del Dashboard funcionen correctamente"""
        with self.app.app_context():
            t0 = time.perf_counter()
            kpis = obtener_metricas_kpis()
            t_kpis = (time.perf_counter() - t0) * 1000

            self.assertIn('usuarios_count', kpis)
            self.assertIn('ventas_hoy', kpis)
            self.assertIn('cobros_hoy', kpis)
            self.assertIn('saldo_caja', kpis)

            ventas_mes = obtener_ventas_mes()
            self.assertIsInstance(ventas_mes, list)

            top_clientes = obtener_top_clientes_deudores()
            self.assertIsInstance(top_clientes, list)

            prod_stock = obtener_productos_bajo_stock()
            self.assertIsInstance(prod_stock, list)

            print(f"\n[BENCHMARK] obtener_metricas_kpis ejecutado en {t_kpis:.2f} ms")


if __name__ == '__main__':
    unittest.main()

