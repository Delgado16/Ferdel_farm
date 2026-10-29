# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

def convertir_hora_db(hora_db):
    """Convierte hora de la base de datos (timedelta, time, o string) a string HH:MM"""
    if not hora_db:
        return None
    
    try:
        # Si es timedelta (MySQL devuelve TIME como timedelta)
        if hasattr(hora_db, 'seconds'):
            total_seconds = hora_db.seconds
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        
        # Si es datetime.time
        elif hasattr(hora_db, 'hour'):
            return f"{hora_db.hour:02d}:{hora_db.minute:02d}"
        
        # Si es datetime.datetime
        elif hasattr(hora_db, 'strftime'):
            return hora_db.strftime('%H:%M')
        
        # Si ya es string
        elif isinstance(hora_db, str):
            # Limpiar string si tiene segundos
            if ':' in hora_db:
                parts = hora_db.split(':')
                return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
            return hora_db
        
        # Otro tipo
        else:
            return str(hora_db)
            
    except Exception as e:
        print(f"Error convirtiendo hora: {hora_db}, tipo: {type(hora_db)}, error: {e}")
        return None


def procesar_asignacion(asignacion_raw):
    """Procesa una asignación para convertir fechas y horas a strings"""
    if not asignacion_raw:
        return None
    
    if isinstance(asignacion_raw, dict):
        asignacion = asignacion_raw
    else:
        asignacion = dict(asignacion_raw)
    
    # Convertir horas
    asignacion['Hora_Inicio_str'] = convertir_hora_db(asignacion.get('Hora_Inicio'))
    asignacion['Hora_Fin_str'] = convertir_hora_db(asignacion.get('Hora_Fin'))
    
    # Convertir fechas a strings para el template
    if asignacion.get('Fecha_Asignacion'):
        if hasattr(asignacion['Fecha_Asignacion'], 'strftime'):
            asignacion['Fecha_Asignacion_str'] = asignacion['Fecha_Asignacion'].strftime('%d/%m/%Y')
        else:
            asignacion['Fecha_Asignacion_str'] = str(asignacion['Fecha_Asignacion'])
    
    if asignacion.get('Fecha_Finalizacion'):
        if hasattr(asignacion['Fecha_Finalizacion'], 'strftime'):
            asignacion['Fecha_Finalizacion_str'] = asignacion['Fecha_Finalizacion'].strftime('%d/%m/%Y')
        else:
            asignacion['Fecha_Finalizacion_str'] = str(asignacion['Fecha_Finalizacion'])
    
    return asignacion


def procesar_lista_asignaciones(asignaciones_raw):
    """Procesa una lista de asignaciones"""
    return [procesar_asignacion(a) for a in asignaciones_raw if a]


class TipoMovimientoRuta:
    """Constantes estandarizadas para ID_TipoMovimiento en rutas e inventario"""
    COMPRA = 1
    VENTA = 2
    PRODUCCION = 3
    CONSUMO = 4
    AJUSTE_SALIDA = 5
    TRASLADO_INTERNO = 6
    MERMA = 7
    AJUSTE_ENTRADA = 8
    DEVOLUCION_RUTA = 11
    TRASLADO_SALIDA = 12
    TRASLADO_ENTRADA = 13
    SALIDA_ENTREGA = 14
    ENTRADA_CARGA = 15


_cache_tipos_movimiento = {}


def obtener_id_tipo_movimiento(cursor, clave_busqueda, default_id):
    """
    Resuelve dinámicamente el ID_TipoMovimiento desde catalogo_movimientos
    usando caché en memoria, o retorna default_id si no hay coincidencia exacta.
    """
    clave_upper = (clave_busqueda or '').strip().upper()
    if clave_upper in _cache_tipos_movimiento:
        return _cache_tipos_movimiento[clave_upper]

    try:
        cursor.execute("SELECT ID_TipoMovimiento, Descripcion, Letra FROM catalogo_movimientos")
        filas = cursor.fetchall() or []
        for f in filas:
            desc = (f.get('Descripcion') or '').upper()
            if clave_upper and clave_upper in desc:
                _cache_tipos_movimiento[clave_upper] = int(f['ID_TipoMovimiento'])
                return _cache_tipos_movimiento[clave_upper]
    except Exception:
        pass

    return default_id


def obtener_asignacion_activa(cursor, id_usuario):
    """
    Obtiene la asignación activa vigente del vendedor junto con los datos
    de su ruta, vehículo y empresa. Todo el flujo del vendedor se rige por esta asignación.
    """
    cursor.execute("""
        SELECT av.ID_Asignacion, av.ID_Usuario, av.ID_Ruta, r.Nombre_Ruta,
               av.Fecha_Asignacion, av.Fecha_Finalizacion, av.Estado,
               av.Hora_Inicio, av.Hora_Fin, av.ID_Vehiculo,
               COALESCE(av.ID_Empresa, r.ID_Empresa, 1) AS ID_Empresa,
               v.Placa, v.Marca, v.Modelo, v.Tipo_Combustible,
               u.NombreUsuario AS Nombre_Vendedor
        FROM asignacion_vendedores av
        LEFT JOIN rutas r ON av.ID_Ruta = r.ID_Ruta
        LEFT JOIN vehiculos v ON av.ID_Vehiculo = v.ID_Vehiculo
        LEFT JOIN usuarios u ON av.ID_Usuario = u.ID_Usuario
        WHERE av.ID_Usuario = %s
          AND av.Estado = 'Activa'
        ORDER BY av.Fecha_Asignacion DESC, av.ID_Asignacion DESC
        LIMIT 1
    """, (id_usuario,))
    row = cursor.fetchone()
    return procesar_asignacion(row) if row else None


def calcular_saldo_caja_ruta(cursor, id_asignacion):
    """
    Calcula de forma estandarizada el saldo de efectivo actual en la caja de la ruta
    para una asignación dada (Apertura + Ventas Contado + Abonos - Gastos).
    """
    if not id_asignacion:
        return 0.0

    cursor.execute("""
        SELECT COALESCE(SUM(CASE
            WHEN Tipo = 'GASTO' THEN -Monto
            WHEN Tipo = 'CIERRE' THEN 0
            WHEN Tipo IN ('APERTURA', 'ABONO') THEN Monto
            WHEN Tipo = 'VENTA' AND (Tipo_Pago = 'CONTADO' OR Tipo_Pago IS NULL) THEN Monto
            ELSE 0
        END), 0) AS Saldo_Actual
        FROM movimientos_caja_ruta
        WHERE ID_Asignacion = %s
          AND Estado = 'ACTIVO'
    """, (id_asignacion,))
    res = cursor.fetchone()
    return float(res['Saldo_Actual'] or 0.0) if res else 0.0



