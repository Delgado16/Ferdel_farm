import sys

def replace_in_file():
    with open('routes/admin/ventas/facturacion.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix admin_anular_venta
    content = content.replace("SET ID_TipoMovimiento = 10,  -- Tipo ANULACIÓN", "SET ID_TipoMovimiento = 11,  -- Tipo ANULACIÓN")
    
    # Fix admin_anular_factura limit issue and ID 10 issue
    old_code = '''                    # ============ LOCAL: MODIFICAR MOVIMIENTO ORIGINAL ============
                    # Buscar el movimiento original
                    cursor.execute("""
                        SELECT ID_Movimiento, ID_Bodega, Estado, ID_TipoMovimiento
                        FROM movimientos_inventario 
                        WHERE ID_Factura_Venta = %s AND ID_Empresa = %s 
                        AND (Estado = 'Activa' OR Estado = 'ACTIVA')
                        ORDER BY ID_Movimiento DESC
                        LIMIT 1
                    """, (id_factura, empresa_id))
                    movimiento_original = cursor.fetchone()
                    
                    if not movimiento_original:
                        raise Exception("No se encontró el movimiento de inventario original para la factura #{}".format(id_factura))
                    
                    id_movimiento_original = movimiento_original['ID_Movimiento']
                    id_bodega = movimiento_original['ID_Bodega']
                    
                    # MODIFICAR el movimiento original - cambiar tipo a ANULACIÓN (10) y estado a 'Anulada'
                    observacion_anulacion = 'ANULADA - Factura #{} - Motivo: {}'.format(id_factura, motivo)
                    
                    cursor.execute("""
                        UPDATE movimientos_inventario 
                        SET ID_TipoMovimiento = 10,
                            Estado = 'Anulada',
                            Observacion = %s,
                            Fecha_Modificacion = NOW(),
                            ID_Usuario_Modificacion = %s
                        WHERE ID_Movimiento = %s
                    """, (observacion_anulacion, user_id, id_movimiento_original))
                    
                    # ELIMINAR detalles anteriores del movimiento
                    cursor.execute("""
                        DELETE FROM detalle_movimientos_inventario 
                        WHERE ID_Movimiento = %s
                    """, (id_movimiento_original,))
                    
                    # INSERTAR nuevos detalles en el MISMO movimiento (como devolución)
                    for detalle in detalles:
                        id_producto = detalle['ID_Producto']
                        cantidad = float(detalle['Cantidad'])
                        costo = float(detalle['Costo']) if detalle['Costo'] else 0
                        costo_unitario = costo / cantidad if cantidad > 0 else 0
                        total = float(detalle['Total']) if detalle['Total'] else 0
                        
                        cursor.execute("""
                            INSERT INTO detalle_movimientos_inventario 
                            (ID_Movimiento, ID_Producto, Cantidad, Costo_Unitario, 
                             Precio_Unitario, Subtotal, ID_Usuario_Creacion, Fecha_Creacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """, (id_movimiento_original, id_producto, cantidad, 
                              costo_unitario, costo_unitario, total, user_id))
                        
                        # Devolver al inventario de bodega
                        cursor.execute("""
                            SELECT Existencias FROM inventario_bodega 
                            WHERE ID_Bodega = %s AND ID_Producto = %s
                        """, (id_bodega, id_producto))
                        inv_bodega = cursor.fetchone()
                        
                        if inv_bodega:
                            cursor.execute("""
                                UPDATE inventario_bodega 
                                SET Existencias = Existencias + %s
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (cantidad, id_bodega, id_producto))
                        else:
                            cursor.execute("""
                                INSERT INTO inventario_bodega 
                                (ID_Bodega, ID_Producto, Existencias)
                                VALUES (%s, %s, %s)
                            """, (id_bodega, id_producto, cantidad))'''
                            
    new_code = '''                    # ============ LOCAL: MODIFICAR MOVIMIENTO ORIGINAL ============
                    # Buscar el movimiento original
                    cursor.execute("""
                        SELECT ID_Movimiento, ID_Bodega, Estado, ID_TipoMovimiento
                        FROM movimientos_inventario 
                        WHERE ID_Factura_Venta = %s AND ID_Empresa = %s 
                        AND (Estado = 'Activa' OR Estado = 'ACTIVA')
                    """, (id_factura, empresa_id))
                    movimientos_originales = cursor.fetchall()
                    
                    if not movimientos_originales:
                        raise Exception("No se encontró el movimiento de inventario original para la factura #{}".format(id_factura))
                    
                    observacion_anulacion = 'ANULADA - Factura #{} - Motivo: {}'.format(id_factura, motivo)
                    
                    for movimiento_original in movimientos_originales:
                        id_mov = movimiento_original['ID_Movimiento']
                        id_bodega = movimiento_original['ID_Bodega']
                        
                        # MODIFICAR el movimiento original - cambiar tipo a ANULACIÓN (11) y estado a 'Anulada'
                        cursor.execute("""
                            UPDATE movimientos_inventario 
                            SET ID_TipoMovimiento = 11,
                                Estado = 'Anulada',
                                Observacion = CONCAT(IFNULL(Observacion, ''), ' | ', %s),
                                Fecha_Modificacion = NOW(),
                                ID_Usuario_Modificacion = %s
                            WHERE ID_Movimiento = %s
                        """, (observacion_anulacion, user_id, id_mov))
                        
                        # Obtener los detalles de este movimiento específico para devolver al inventario de su bodega
                        cursor.execute("""
                            SELECT ID_Producto, Cantidad 
                            FROM detalle_movimientos_inventario 
                            WHERE ID_Movimiento = %s
                        """, (id_mov,))
                        detalles_mov = cursor.fetchall()
                        
                        for d_mov in detalles_mov:
                            id_producto = d_mov['ID_Producto']
                            cantidad = float(d_mov['Cantidad'])
                            
                            # Devolver al inventario de la bodega específica
                            cursor.execute("""
                                UPDATE inventario_bodega 
                                SET Existencias = Existencias + %s
                                WHERE ID_Bodega = %s AND ID_Producto = %s
                            """, (cantidad, id_bodega, id_producto))'''

    content = content.replace(old_code, new_code)
    
    with open('routes/admin/ventas/facturacion.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print('Replaced!')

if __name__ == '__main__':
    replace_in_file()
