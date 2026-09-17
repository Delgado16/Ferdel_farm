import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from config.database import get_db_cursor
import json

app = create_app()
with app.app_context():
    with get_db_cursor() as cursor:
        print("=== TABLAS Y REGISTROS ===")
        cursor.execute("SELECT COUNT(*) as c FROM gastos_generales")
        print("gastos_generales count:", cursor.fetchone()['c'])
        
        cursor.execute("SELECT COUNT(*) as c FROM movimientos_inventario")
        print("movimientos_inventario count:", cursor.fetchone()['c'])
        
        cursor.execute("SELECT COUNT(*) as c FROM movimientos_caja_ruta")
        print("movimientos_caja_ruta count:", cursor.fetchone()['c'])
        
        cursor.execute("SELECT * FROM tipos_gasto")
        print("tipos_gasto:", cursor.fetchall())
        
        cursor.execute("SELECT * FROM subcategorias_gasto")
        print("subcategorias_gasto:", cursor.fetchall())
