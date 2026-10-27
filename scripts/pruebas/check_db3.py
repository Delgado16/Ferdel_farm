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
                cursor.execute("SELECT u.Descripcion, COUNT(p.ID_Producto) FROM productos p LEFT JOIN unidades_medida u ON p.Unidad_Medida = u.ID_Unidad GROUP BY u.Descripcion")
                print("--- UNIDADES DE MEDIDA ---")
                for u in cursor.fetchall():
                    print(u)
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
