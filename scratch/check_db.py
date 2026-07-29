import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from config.database import get_db_cursor

app = Flask(__name__)
app.config.from_pyfile('config/settings.py', silent=True) # or configure manually

# Let's run a test query
with app.app_context():
    with get_db_cursor() as cursor:
        # Active assignments
        cursor.execute("SELECT * FROM asignacion_vendedores WHERE Estado = 'Activa'")
        active = cursor.fetchall()
        print("ACTIVE ASSIGNMENTS:")
        for r in active:
            print(dict(r))
            
        # Let's query recent movements_caja_ruta
        cursor.execute("SELECT * FROM movimientos_caja_ruta ORDER BY ID_Movimiento DESC LIMIT 10")
        recent_caja = cursor.fetchall()
        print("\nRECENT CAJA MOVEMENTS:")
        for r in recent_caja:
            print(dict(r))
