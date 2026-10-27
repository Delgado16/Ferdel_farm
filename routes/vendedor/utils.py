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


