from datetime import datetime, timedelta

def get_period_date_range_test(periodo_arg='', fecha_inicio_arg='', fecha_fin_arg='', default_period='mes'):
    today = datetime.now()
    
    periodo = (periodo_arg or '').strip()
    f_ini = (fecha_inicio_arg or '').strip()
    f_fin = (fecha_fin_arg or '').strip()
    
    # Si viene explícitamente desde formulario personalizado con fechas
    if f_ini and f_fin and (not periodo or periodo == 'personalizado'):
        return f_ini, f_fin, 'personalizado'
        
    if not periodo:
        if f_ini and f_fin:
            return f_ini, f_fin, 'personalizado'
        periodo = default_period
        
    if periodo in ['dia', 'hoy']:
        fecha_inicio = today.strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
        periodo = 'dia'
    elif periodo == 'ayer':
        ayer = today - timedelta(days=1)
        fecha_inicio = ayer.strftime('%Y-%m-%d')
        fecha_fin = ayer.strftime('%Y-%m-%d')
        periodo = 'ayer'
    elif periodo == 'semana':
        fecha_inicio = (today - timedelta(days=6)).strftime('%Y-%m-%d')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo == 'mes':
        fecha_inicio = today.strftime('%Y-%m-01')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo in ['mes_anterior', 'mes_pasado']:
        primer_dia_mes_actual = today.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_mes_actual - timedelta(days=1)
        primer_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1)
        fecha_inicio = primer_dia_mes_anterior.strftime('%Y-%m-%d')
        fecha_fin = ultimo_dia_mes_anterior.strftime('%Y-%m-%d')
        periodo = 'mes_anterior'
    elif periodo == 'ano':
        fecha_inicio = today.strftime('%Y-01-01')
        fecha_fin = today.strftime('%Y-%m-%d')
    elif periodo == 'todo':
        fecha_inicio = '2020-01-01'
        fecha_fin = today.strftime('%Y-%m-%d')
    else:
        fecha_inicio = f_ini or today.strftime('%Y-%m-01')
        fecha_fin = f_fin or today.strftime('%Y-%m-%d')
        periodo = 'personalizado'
        
    return fecha_inicio, fecha_fin, periodo

print("Hoy:", get_period_date_range_test('dia'))
print("Ayer:", get_period_date_range_test('ayer'))
print("Semana:", get_period_date_range_test('semana'))
print("Mes:", get_period_date_range_test('mes'))
print("Mes anterior:", get_period_date_range_test('mes_anterior'))
print("Año:", get_period_date_range_test('ano'))
print("Personalizado:", get_period_date_range_test('personalizado', '2026-08-01', '2026-08-15'))
print("Form submit con fechas:", get_period_date_range_test('', '2026-08-01', '2026-08-15'))
