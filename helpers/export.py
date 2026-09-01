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
    """Exportar el Finiquito y Reporte Diario detallado a PDF usando ReportLab"""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15, textColor=colors.HexColor('#2c5e2e'), spaceAfter=4)
    subtitulo_style = ParagraphStyle('Sub', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1e293b'), spaceAfter=6, spaceBefore=12)
    meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#475569'), spaceAfter=12)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9)
    body_bold = ParagraphStyle('BodyBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9)
    body_right = ParagraphStyle('BodyRight', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, alignment=2)
    body_right_bold = ParagraphStyle('BodyRightBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, alignment=2)
    
    def format_money(val):
        try:
            return f"C${float(val):,.2f}"
        except (ValueError, TypeError):
            return "C$0.00"

    story.append(Paragraph("FERDEL - FINIQUITO Y REPORTE DIARIO CONSOLIDADO", titulo_style))
    story.append(Paragraph(f"Fecha de Operación: {context.get('fecha_formatted', '')}  |  Generado: {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", meta_style))
    story.append(Spacer(1, 4))
    
    def crear_tabla(headers, data_rows, col_widths=None, header_bg='#2c5e2e'):
        if not data_rows:
            return Paragraph("No hay registros en esta sección.", body_style)
        
        table_data = []
        header_cells = [Paragraph(f"<b>{h}</b>", ParagraphStyle('H', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, textColor=colors.whitesmoke, alignment=1 if 'Monto' in h or 'Total' in h or 'Saldo' in h else 0)) for h in headers]
        table_data.append(header_cells)
        
        for row in data_rows:
            row_cells = []
            for idx, val in enumerate(row):
                if isinstance(val, Paragraph):
                    row_cells.append(val)
                else:
                    val_str = str(val if val is not None else '')
                    if val_str.startswith('C$') or any(k in headers[idx] for k in ['Monto', 'Total', 'Saldo', 'Crédito', 'Abono', 'Inicial', 'Final']):
                        row_cells.append(Paragraph(val_str, body_right_bold if 'TOTAL' in str(row[0]) else body_right))
                    else:
                        row_cells.append(Paragraph(val_str, body_style))
            table_data.append(row_cells)
            
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(header_bg)),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 4),
            ('TOPPADDING', (0,0), (-1,0), 4),
            ('BOTTOMPADDING', (0,1), (-1,-1), 3),
            ('TOPPADDING', (0,1), (-1,-1), 3),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        return t

    # 1. RESUMEN EJECUTIVO (MÓDULOS PRINCIPALES)
    story.append(Paragraph("1. Resumen Ejecutivo de Operaciones del Día", subtitulo_style))
    resumen_datos = [
        ["Ventas Totales", format_money(context.get('ventas_total', 0)), f"Contado: {format_money(context.get('ventas_contado', 0))} | Crédito: {format_money(context.get('ventas_credito', 0))} (Oficina: {format_money(context.get('ventas_normal', 0))} / Ruta: {format_money(context.get('ventas_ruta', 0))})"],
        ["Cobranza y Abonos", format_money(context.get('cobros_total', 0)), f"Efectivo: {format_money(context.get('cobros_efectivo', 0))} | Bancos/Transferencias: {format_money(context.get('cobros_bancos', 0))}"],
        ["Cierre de Caja (Efectivo)", format_money(context.get('caja_saldo_neto', 0)), f"Apertura: {format_money(context.get('caja_apertura', 0))} | Entradas: {format_money(context.get('caja_total_entradas', 0))} | Salidas: {format_money(context.get('caja_total_salidas', 0))}"],
        ["Cartera Global (CxC)", format_money(context.get('cxc_saldo_total', 0)), f"Nuevos Créditos Hoy: {format_money(context.get('cxc_nuevos_creditos_hoy', 0))} | Abonos Recuperados: {format_money(context.get('cxc_abonos_recuperados_hoy', 0))}"],
        ["Compras a Proveedores", format_money(context.get('compras_total', 0)), f"Contado: {format_money(context.get('compras_contado', 0))} | Crédito: {format_money(context.get('compras_credito', 0))}"],
        ["Gastos Operativos", format_money(context.get('gastos_total', 0)), f"Total de gastos operativos directos del día"],
        ["Inventario Bodega", f"{context.get('inventario_total_productos', 0)} Items", f"Items con Stock Crítico: {len(context.get('bajo_stock', []))}"]
    ]
    story.append(crear_tabla(["Módulo / Concepto", "Monto / Valor", "Desglose Operativo"], resumen_datos, [130, 110, 310]))
    story.append(Spacer(1, 8))

    # 2. CONCILIACIÓN Y FLUJO DE EFECTIVO EN CAJA
    story.append(Paragraph(f"2. Arqueo y Conciliación de Efectivo (Saldo Esperado: {format_money(context.get('caja_saldo_neto', 0))})", subtitulo_style))
    conciliacion_datos = [
        ["Apertura de Caja", "INICIAL", format_money(context.get('caja_apertura', 0))],
        ["(+) Ventas de Contado (Efectivo Oficina + Rutas)", "VENTAS-CONT", format_money(context.get('ventas_contado', 0))],
        ["(+) Abonos de Clientes Cobrados en Efectivo", "ABONOS-EFECT", format_money(context.get('cobros_efectivo', 0))],
        ["(-) Gastos Operativos Pagados en Efectivo", "GASTOS-OP", f"- {format_money(context.get('gastos_total', 0))}"],
        ["(-) Compras a Proveedores de Contado", "COMPRAS-CONT", f"- {format_money(context.get('compras_contado', 0))}"]
    ]
    story.append(crear_tabla(["Concepto de Flujo", "Referencia", "Monto"], conciliacion_datos, [260, 140, 150], header_bg='#059669'))
    story.append(Spacer(1, 8))

    # 3. CARTERA DE CLIENTES: SALDOS Y VARIACIÓN DEL DÍA
    story.append(Paragraph(f"3. Cartera de Clientes: Saldos y Variación del Día ({len(context.get('clientes_cartera', []))} clientes)", subtitulo_style))
    clientes_datos = []
    for c in context.get('clientes_cartera', [])[:30]:  # Top 30 clientes con movimiento o saldo
        cred_txt = format_money(c.get('credito_hoy', 0)) if c.get('credito_hoy', 0) > 0 else "-"
        abono_txt = format_money(c.get('abono_hoy', 0)) if c.get('abono_hoy', 0) > 0 else "-"
        clientes_datos.append([
            c.get('nombre', '')[:25],
            format_money(c.get('saldo_inicial', 0)),
            cred_txt,
            abono_txt,
            format_money(c.get('saldo_actual', 0)),
            c.get('tipo_variacion', 'SIN CAMBIO'),
            c.get('estado_deuda', '')
        ])
    story.append(crear_tabla(["Cliente", "Saldo Inicial", "(+) Crédito", "(-) Abono", "Saldo Final", "Variación", "Estado"], clientes_datos, [140, 70, 65, 65, 70, 70, 70], header_bg='#1e293b'))
    story.append(Spacer(1, 8))

    # 4. FACTURACIÓN Y VENTAS DEL DÍA
    story.append(Paragraph(f"4. Detalle de Facturas Emitidas Hoy ({len(context.get('ventas_detalle', []))} facturas)", subtitulo_style))
    ventas_rows = []
    for v in context.get('ventas_detalle', []):
        ventas_rows.append([
            v.get('id_factura', ''),
            v.get('origen', ''),
            v.get('cliente', '')[:22],
            v.get('vendedor', '')[:16],
            v.get('tipo_venta', ''),
            format_money(v.get('total', 0))
        ])
    story.append(crear_tabla(["Factura", "Origen", "Cliente", "Vendedor", "Condición", "Total"], ventas_rows, [70, 95, 145, 95, 65, 80], header_bg='#4338ca'))
    story.append(Spacer(1, 8))

    # 5. RECAUDACIÓN Y ABONOS DETALLADOS
    story.append(Paragraph(f"5. Cobros y Abonos Recibidos ({len(context.get('cobros_list', []))} recibos)", subtitulo_style))
    cobros_rows = []
    for ab in context.get('cobros_list', []):
        cobros_rows.append([
            ab.get('cliente', '')[:25],
            ab.get('cobrador', '')[:18],
            ab.get('factura', '')[:16],
            ab.get('metodo', ''),
            format_money(ab.get('monto', 0))
        ])
    story.append(crear_tabla(["Cliente", "Cobrador / Vendedor", "Factura Aplicada", "Método de Pago", "Monto"], cobros_rows, [160, 110, 100, 90, 90], header_bg='#d97706'))
    story.append(Spacer(1, 8))

    # 6. RENDIMIENTO DE VENDEDORES EN RUTA
    if context.get('vendedores'):
        story.append(Paragraph("6. Rendimiento por Vendedor / Rutas", subtitulo_style))
        vend_rows = []
        for vend in context.get('vendedores', []):
            vend_rows.append([
                vend.get('vendedor', ''),
                str(vend.get('facturas', 0)),
                format_money(vend.get('ventas_contado', 0)),
                format_money(vend.get('ventas_credito', 0)),
                format_money(vend.get('total_vendido', 0))
            ])
        story.append(crear_tabla(["Vendedor", "Facturas", "Ventas Contado", "Ventas Crédito", "Total Vendido"], vend_rows, [150, 80, 110, 110, 100], header_bg='#0f172a'))
        story.append(Spacer(1, 8))

    # 7. EGRESOS: COMPRAS Y GASTOS OPERATIVOS
    story.append(Paragraph("7. Egresos del Día (Compras a Proveedores y Gastos)", subtitulo_style))
    egresos_rows = []
    for c in context.get('compras', []):
        egresos_rows.append([
            "COMPRA PROVEEDOR",
            c.get('proveedor', '')[:25],
            f"Fact: {c.get('factura', 'N/A')} ({c.get('tipo_compra', 'CONTADO')})",
            format_money(c.get('total', 0))
        ])
    for g in context.get('gastos', []):
        egresos_rows.append([
            f"GASTO: {g.get('tipo_gasto', '')[:18]}",
            g.get('proveedor', 'N/A')[:25],
            f"Ref: {g.get('factura', 'N/A')} - {g.get('subcategoria', '')[:15]}",
            format_money(g.get('monto', 0))
        ])
    story.append(crear_tabla(["Tipo de Egreso", "Proveedor / Beneficiario", "Referencia / Detalle", "Monto"], egresos_rows, [140, 150, 160, 100], header_bg='#dc2626'))
    story.append(Spacer(1, 8))

    # 8. TOP PRODUCTOS VENDIDOS E INVENTARIO
    story.append(Paragraph("8. Top Productos Vendidos Hoy", subtitulo_style))
    prod_datos = []
    for p in context.get('productos_vendidos', [])[:15]:
        prod_datos.append([
            p.get('codigo', ''),
            p.get('producto', '')[:35],
            str(p.get('cantidad', 0)),
            format_money(p.get('total', 0))
        ])
    story.append(crear_tabla(["Código", "Producto", "Cantidad Vendida", "Total"], prod_datos, [80, 260, 110, 100], header_bg='#2c5e2e'))

    doc.build(story)
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    response.headers['Content-type'] = 'application/pdf'
    return response

