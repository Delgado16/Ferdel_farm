import sys
import os
from flask import Flask
from config.database import get_db_cursor
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)

def parse_cantidad_cajillas(cantidad_val):
    try:
        if not cantidad_val:
            return Decimal('0.00')
        d = Decimal(str(cantidad_val).strip())
        if d % 1 != 0:
            cajillas = int(d)
            unidades = int(round((d - cajillas) * 100))
            return Decimal(cajillas) + Decimal(unidades) / Decimal(30)
        return d
    except Exception:
        return Decimal('0.00')

def corregir_datos():
    try:
        with app.app_context():
            with get_db_cursor(commit=True) as cursor:
                # 1. Obtener todos los detalles de movimientos de productos tipo Caja (Unidad_Medida = 1)
                # que tengan decimales (fracciones incorrectas)
                cursor.execute("""
                    SELECT 
                        dmi.ID_Detalle_Movimiento, dmi.ID_Movimiento, dmi.ID_Producto, 
                        dmi.Cantidad, dmi.Costo_Unitario, dmi.Precio_Unitario, dmi.Subtotal,
                        mi.ID_Bodega, mi.ID_Bodega_Destino, cm.Letra, cm.Adicion
                    FROM detalle_movimientos_inventario dmi
                    JOIN movimientos_inventario mi ON dmi.ID_Movimiento = mi.ID_Movimiento
                    JOIN catalogo_movimientos cm ON mi.ID_TipoMovimiento = cm.ID_TipoMovimiento
                    JOIN productos p ON dmi.ID_Producto = p.ID_Producto
                    WHERE p.Unidad_Medida = 1 AND dmi.Cantidad != ROUND(dmi.Cantidad, 0)
                """)
                
                movimientos = cursor.fetchall()
                print(f"Se encontraron {len(movimientos)} movimientos a corregir.")
                
                for m in movimientos:
                    old_cantidad = Decimal(str(m['Cantidad']))
                    new_cantidad = parse_cantidad_cajillas(old_cantidad)
                    
                    if old_cantidad == new_cantidad:
                        continue
                        
                    print(f"Corrigiendo Movimiento {m['ID_Movimiento']} (Prod {m['ID_Producto']}): {old_cantidad} -> {new_cantidad:.2f}")
                    
                    # El subtotal depende del tipo de precio guardado. Normalmente es Cantidad * Costo o Precio
                    if m['Subtotal'] and old_cantidad > 0:
                        # Si era 12.16 * 190 = 2310.40, ahora será 12.533 * 190 = 2381.33
                        # Para mantener la misma relación que antes:
                        if m['Precio_Unitario'] and m['Precio_Unitario'] > 0 and (old_cantidad * m['Precio_Unitario'] == m['Subtotal']):
                            new_subtotal = new_cantidad * m['Precio_Unitario']
                        elif m['Costo_Unitario'] and m['Costo_Unitario'] > 0:
                            new_subtotal = new_cantidad * m['Costo_Unitario']
                        else:
                            # Proporcional
                            new_subtotal = m['Subtotal'] * (new_cantidad / old_cantidad)
                    else:
                        new_subtotal = Decimal('0.00')
                        
                    # Actualizar Detalle
                    cursor.execute("""
                        UPDATE detalle_movimientos_inventario 
                        SET Cantidad = %s, Subtotal = %s
                        WHERE ID_Detalle_Movimiento = %s
                    """, (new_cantidad, new_subtotal, m['ID_Detalle_Movimiento']))
                    
                    # Actualizar Inventario Bodega (Diferencia)
                    diff = new_cantidad - old_cantidad
                    
                    if m['Letra'] == 'E': # Entrada
                        cursor.execute("""
                            UPDATE inventario_bodega SET Existencias = Existencias + %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (diff, m['ID_Bodega'], m['ID_Producto']))
                    elif m['Letra'] == 'S': # Salida
                        cursor.execute("""
                            UPDATE inventario_bodega SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (diff, m['ID_Bodega'], m['ID_Producto']))
                    elif m['Letra'] == 'T': # Transferencia
                        # Restar del origen, sumar al destino
                        cursor.execute("""
                            UPDATE inventario_bodega SET Existencias = Existencias - %s
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (diff, m['ID_Bodega'], m['ID_Producto']))
                        if m['ID_Bodega_Destino']:
                            cursor.execute("""
                                UPDATE inventario_bodega SET Existencias = Existencias + %s
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (diff, m['ID_Bodega_Destino'], m['ID_Producto']))
                            
                print("¡Corrección de datos finalizada!")

    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    corregir_datos()
