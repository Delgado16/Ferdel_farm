import sys
import os
from flask import Flask
from config.database import get_db_cursor
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)

def check_db():
    try:
        with app.app_context():
            with get_db_cursor(commit=False) as cursor:
                # Check column type
                cursor.execute("SHOW COLUMNS FROM detalle_movimientos_inventario WHERE Field = 'Cantidad'")
                print(cursor.fetchone())
                
                cursor.execute("SHOW COLUMNS FROM inventario_bodega WHERE Field = 'Existencias'")
                print(cursor.fetchone())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
