import csv
import io
import json
from datetime import datetime
from flask import Response, make_response

def exportar_csv(datos, nombre_archivo):
    """Exportar datos a CSV"""
    if not datos:
        return "No hay datos para exportar", 400
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Escribir encabezados
    writer.writerow(datos[0].keys())
    
    # Escribir datos
    for row in datos:
        writer.writerow(row.values())
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

def exportar_json(datos, nombre_archivo):
    """Exportar datos a JSON"""
    return Response(
        json.dumps(datos, default=str, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'}
    )
