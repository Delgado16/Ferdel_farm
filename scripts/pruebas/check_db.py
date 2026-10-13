import sys
import os
from flask import Flask
from config.database import get_db_cursor
from decimal import Decimal

# Add current dir to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

def check_db():
    try:
        with app.app_context():
            with get_db_cursor(commit=False) as cursor:
                # Check products
                cursor.execute("SELECT ID_Producto, COD_Producto, Descripcion, Unidad_Medida, Precio_Mercado FROM productos LIMIT 5")
                print("--- PRODUCTOS ---")
                for p in cursor.fetchall():
                    print(p)
                    
                # Check some movements with decimal quantities
                cursor.execute("""
                    SELECT 
                        dmi.ID_Movimiento, dmi.ID_Producto, p.Descripcion,
                        dmi.Cantidad, dmi.Costo_Unitario, dmi.Precio_Unitario, dmi.Subtotal
                    FROM detalle_movimientos_inventario dmi
                    JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE dmi.Cantidad != ROUND(dmi.Cantidad, 0)
                    LIMIT 5
                """)
                print("\n--- MOVIMIENTOS CON DECIMALES ---")
                for m in cursor.fetchall():
                    print(m)
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
