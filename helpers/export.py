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

def exportar_excel(datos, nombre_archivo):
    """Exportar datos a Excel (.xlsx) de manera estructurada"""
    if not datos:
        return "No hay datos para exportar", 400
        
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte"
    
    # Encabezados
    headers = list(datos[0].keys())
    ws.append(headers)
    
    # Estilo de cabeceras
    header_fill = PatternFill(start_color="2C5E2E", end_color="2C5E2E", fill_type="solid") # primary-color de Ferdel
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    center_align = Alignment(horizontal="center", vertical="center")
    
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
    
    # Filas de datos
    for row_data in datos:
        row_values = [str(val) if val is not None else "" for val in row_data.values()]
        ws.append(row_values)
        
    # Auto-ajustar el ancho de las columnas
    for col in ws.columns:
        max_len = 0
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)
        
    # Guardar en memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response

def exportar_pdf(datos, nombre_archivo):
    """Exportar datos a PDF de manera estructurada y limpia"""
    if not datos:
        return "No hay datos para exportar", 400
        
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    
    # Usar landscape (apaisado) si hay muchas columnas (> 6) para que quepa bien
    headers = list(datos[0].keys())
    use_landscape = len(headers) > 6
    pagesize = landscape(letter) if use_landscape else letter
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=pagesize,
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Título del reporte
    titulo_style = ParagraphStyle(
        'TituloReporte',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#2c5e2e'),
        spaceAfter=15
    )
    
    fecha_style = ParagraphStyle(
        'FechaReporte',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=20
    )
    
    # Formatear el nombre del archivo para el título
    titulo_limpio = nombre_archivo.replace('_', ' ').replace('-', ' ').title()
    story.append(Paragraph(f"Reporte de {titulo_limpio}", titulo_style))
    story.append(Paragraph(f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fecha_style))
    
    # Preparar tabla
    table_data = [headers]
    
    body_style = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10
    )
    
    for row in datos:
        row_cells = []
        for val in row.values():
            val_str = str(val) if val is not None else ""
            row_cells.append(Paragraph(val_str, body_style))
        table_data.append(row_cells)
    
    # Ajustar ancho de las columnas proporcionalmente
    col_width = (doc.width) / len(headers)
    t = Table(table_data, colWidths=[col_width] * len(headers))
    
    # Estilo de tabla
    t_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5e2e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
    ])
    t.setStyle(t_style)
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    response.headers['Content-type'] = 'application/pdf'
    return response

def exportar_pdf_diario(context, nombre_archivo):
    """Exportar el Reporte Diario detallado a PDF usando ReportLab"""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#2c5e2e'), spaceAfter=10)
    subtitulo_style = ParagraphStyle('Sub', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor('#1e293b'), spaceAfter=10, spaceBefore=15)
    fecha_style = ParagraphStyle('Fecha', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=20)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica', fontSize=8)
    
    story.append(Paragraph(f"Reporte Diario Consolidado", titulo_style))
    story.append(Paragraph(f"Fecha del reporte: {context.get('fecha_formatted', '')}", fecha_style))
    
    def crear_tabla(datos, headers, col_widths=None):
        if not datos:
            return Paragraph("No hay registros.", body_style)
        
        table_data = [headers]
        for row in datos:
            row_cells = [Paragraph(str(val), body_style) for val in row]
            table_data.append(row_cells)
            
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5e2e')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        return t

    def format_money(val):
        return f"C${float(val):,.2f}"

    # 1. Módulos Principales (Resumen)
    story.append(Paragraph("Módulos Principales del Negocio", subtitulo_style))
    resumen_datos = [
        ["Ventas Totales", format_money(context.get('ventas_total', 0)), f"Contado: {format_money(context.get('ventas_contado', 0))} | Crédito: {format_money(context.get('ventas_credito', 0))}"],
        ["Compras Totales", format_money(context.get('compras_total', 0)), f"Contado: {format_money(context.get('compras_contado', 0))} | Crédito: {format_money(context.get('compras_credito', 0))}"],
        ["Cuentas x Cobrar", format_money(context.get('cxc_saldo_total', 0)), f"Cobrado Hoy: {format_money(context.get('cobros_total', 0))}"],
        ["Cuentas x Pagar", format_money(context.get('cxp_saldo_total', 0)), "Saldo Global Pendiente"],
        ["Inventario", str(context.get('inventario_total_productos', 0)), f"Bajo Stock: {len(context.get('bajo_stock', []))}"]
    ]
    story.append(crear_tabla(resumen_datos, ["Módulo", "Valor/Saldo", "Detalle"], [120, 100, 300]))
    
    # Agregar gráficos de pastel
    def crear_grafico_pastel(data, labels, title):
        d = Drawing(200, 120)
        pc = Pie()
        pc.x = 50
        pc.y = 10
        pc.width = 80
        pc.height = 80
        
        # Filtramos datos cero para que el gráfico no falle
        valid_data = []
        valid_labels = []
        for val, lab in zip(data, labels):
            if val > 0:
                valid_data.append(val)
                valid_labels.append(lab)
                
        if not valid_data:
            pc.data = [1]
            pc.labels = ["Sin datos"]
            pc.slices[0].fillColor = colors.lightgrey
        else:
            pc.data = valid_data
            pc.labels = valid_labels
            pc.slices.strokeWidth = 0.5
            pc.slices[0].fillColor = colors.HexColor('#2c5e2e')  # Verde Ferdel
            if len(pc.slices) > 1:
                pc.slices[1].fillColor = colors.HexColor('#f59e0b')  # Amarillo/Naranja
                
        d.add(pc)
        
        title_p = Paragraph(title, ParagraphStyle('CT', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1))
        
        # Usamos una tablita simple para poner el título arriba del dibujo
        t = Table([[title_p], [d]], colWidths=[200])
        t.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        return t

    # Insertamos los dos gráficos lado a lado en una tabla layout
    v_data = [float(context.get('ventas_contado', 0)), float(context.get('ventas_credito', 0))]
    c_data = [float(context.get('compras_contado', 0)), float(context.get('compras_credito', 0))]
    
    chart_ventas = crear_grafico_pastel(v_data, ['Contado', 'Crédito'], "Distribución de Ventas")
    chart_compras = crear_grafico_pastel(c_data, ['Contado', 'Crédito'], "Distribución de Compras")
    
    story.append(Spacer(1, 10))
    charts_table = Table([[chart_ventas, chart_compras]], colWidths=[260, 260])
    charts_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    story.append(charts_table)
    story.append(Spacer(1, 15))
    
    # 2. Caja Chica
    story.append(Paragraph(f"Caja Chica (Saldo Neto: {format_money(context.get('caja_saldo_neto', 0))})", subtitulo_style))
    caja_datos = [[m.get('tipo', ''), m.get('descripcion', ''), m.get('referencia', ''), format_money(m.get('monto', 0))] for m in context.get('caja_movimientos', [])]
    story.append(crear_tabla(caja_datos, ["Tipo", "Descripción", "Referencia", "Monto"], [60, 260, 100, 100]))
    
    # 3. Gastos
    story.append(Paragraph(f"Gastos Operativos (Total: {format_money(context.get('gastos_total', 0))})", subtitulo_style))
    gastos_datos = [[g.get('tipo_gasto', ''), g.get('proveedor', ''), g.get('factura', ''), format_money(g.get('monto', 0))] for g in context.get('gastos', [])]
    story.append(crear_tabla(gastos_datos, ["Tipo", "Proveedor/Destino", "Ref", "Monto"], [120, 200, 100, 100]))
    
    # 4. Compras
    story.append(Paragraph(f"Compras a Proveedores (Total: {format_money(context.get('compras_total', 0))})", subtitulo_style))
    compras_datos = [[c.get('factura', ''), c.get('proveedor', ''), c.get('tipo_compra', ''), format_money(c.get('total', 0))] for c in context.get('compras', [])]
    story.append(crear_tabla(compras_datos, ["Factura", "Proveedor", "Condición", "Total"], [80, 240, 100, 100]))
    
    # 5. Productos Vendidos
    story.append(Paragraph("Top Productos Vendidos Hoy", subtitulo_style))
    prod_datos = [[p.get('codigo', ''), p.get('producto', ''), str(p.get('cantidad', 0)), format_money(p.get('total', 0))] for p in context.get('productos_vendidos', [])]
    story.append(crear_tabla(prod_datos, ["Código", "Producto", "Cantidad", "Total"], [80, 240, 100, 100]))

    doc.build(story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    response.headers['Content-type'] = 'application/pdf'
    return response
