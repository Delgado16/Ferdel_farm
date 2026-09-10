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
    story.append(Paragraph("1. Resumen Ejecutivo de Operaciones del Día (Enfoque en Efectivo Real)", subtitulo_style))
    resumen_datos = [
        ["Ventas en Efectivo (Contado)", format_money(context.get('ventas_contado', 0)), f"Efectivo de contado (Oficina: {format_money(context.get('ventas_normal', 0))} / Ruta: {format_money(context.get('ventas_ruta', 0))}) | Facturado Total: {format_money(context.get('ventas_total', 0))} (Crédito: {format_money(context.get('ventas_credito', 0))})"],
        ["Cobranza en Efectivo (Abonos)", format_money(context.get('cobros_efectivo', 0)), f"Efectivo recaudado en mano | Bancos/Transf: {format_money(context.get('cobros_bancos', 0))} (Total Cobrado: {format_money(context.get('cobros_total', 0))})"],
        ["Cierre de Caja (Efectivo Neto)", format_money(context.get('caja_saldo_neto', 0)), f"Apertura: {format_money(context.get('caja_apertura', 0))} | Entradas Efec: {format_money(context.get('caja_total_entradas', 0))} | Salidas Efec: {format_money(context.get('caja_total_salidas', 0))}"],
        ["Cartera Global (CxC)", format_money(context.get('cxc_saldo_total', 0)), f"Nuevos Créditos Hoy: {format_money(context.get('cxc_nuevos_creditos_hoy', 0))} | Abonos Recuperados: {format_money(context.get('cxc_abonos_recuperados_hoy', 0))}"],
        ["Compras a Proveedores", format_money(context.get('compras_total', 0)), f"Contado: {format_money(context.get('compras_contado', 0))} | Crédito: {format_money(context.get('compras_credito', 0))}"],
        ["Gastos Operativos", format_money(context.get('gastos_total', 0)), f"Oficina: {format_money(context.get('gastos_oficina_total', 0))} | Rutas: {format_money(context.get('gastos_ruta_total', 0))}"],
        ["Inventario Bodega", f"{context.get('inventario_total_productos', 0)} Items", f"Items con Stock Crítico: {len(context.get('bajo_stock', []))}"]
    ]
    story.append(crear_tabla(["Módulo / Concepto", "Monto / Valor", "Desglose Operativo"], resumen_datos, [135, 110, 305]))
    story.append(Spacer(1, 8))

    # 2. CONCILIACIÓN Y FLUJO DE EFECTIVO EN CAJA
    story.append(Paragraph(f"2. Arqueo y Conciliación de Efectivo (Saldo Esperado: {format_money(context.get('caja_saldo_neto', 0))})", subtitulo_style))
    conciliacion_datos = [
        ["Apertura de Caja", "INICIAL", format_money(context.get('caja_apertura', 0))],
        ["(+) Ventas de Contado (Efectivo Oficina + Rutas)", "VENTAS-CONT", format_money(context.get('ventas_contado', 0))],
        ["(+) Abonos de Clientes Cobrados en Efectivo", "ABONOS-EFECT", format_money(context.get('cobros_efectivo', 0))],
        ["(-) Gastos Operativos Totales (Oficina y Rutas)", "GASTOS-OP", f"- {format_money(context.get('gastos_total', 0))}"],
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
        story.append(Paragraph("6. Liquidación y Rendimiento de Vendedores en Ruta", subtitulo_style))
        vend_rows = []
        for vend in context.get('vendedores', []):
            g_ruta = vend.get('gastos_ruta', 0)
            g_ruta_str = f"-{format_money(g_ruta)}" if g_ruta > 0 else "C$0.00"
            vend_rows.append([
                vend.get('vendedor', ''),
                str(vend.get('facturas', 0)),
                format_money(vend.get('ventas_contado', 0)),
                format_money(vend.get('abonos_efectivo', 0)),
                g_ruta_str,
                format_money(vend.get('efectivo_neto', 0))
            ])
        story.append(crear_tabla(["Vendedor", "Facturas", "Vtas Contado", "Abonos Efec.", "Gastos Ruta", "Efec. Neto Liquidar"], vend_rows, [120, 55, 90, 90, 85, 100], header_bg='#0f172a'))
        story.append(Spacer(1, 8))

    # 7. EGRESOS: COMPRAS Y GASTOS OPERATIVOS
    story.append(Paragraph("7. Egresos del Día (Compras a Proveedores y Gastos)", subtitulo_style))
    egresos_rows = []
    for c in context.get('compras', []):
        egresos_rows.append([
            "COMPRA PROV.",
            c.get('proveedor', '')[:25],
            f"Fact: {c.get('factura', 'N/A')} ({c.get('tipo_compra', 'CONTADO')})",
            format_money(c.get('total', 0))
        ])
    for g in context.get('gastos', []):
        orig_tag = "[OFICINA]" if 'Oficina' in g.get('origen', '') else "[RUTA]"
        desc_det = g.get('concepto') or g.get('subcategoria', '')
        egresos_rows.append([
            f"{orig_tag} {g.get('tipo_gasto', '')[:14]}",
            g.get('proveedor', 'N/A')[:22],
            f"{desc_det[:25]}",
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


def exportar_pdf_competencia_vendedores(context, nombre_archivo):
    """Exportar el Reporte de Competencia y Rendimiento de Vendedores en PDF profesional apaisado con Logo y diseño ejecutivo"""
    import os
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=26,
        leftMargin=26,
        topMargin=24,
        bottomMargin=24
    )

    story = []
    styles = getSampleStyleSheet()

    # Estilos de encabezado y títulos
    titulo_style = ParagraphStyle(
        'TituloCompetencia',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=2
    )

    subtitulo_style = ParagraphStyle(
        'SubCompetencia',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#059669'),
        spaceAfter=3
    )

    meta_style = ParagraphStyle(
        'MetaCompetencia',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#475569')
    )

    section_style = ParagraphStyle(
        'SecCompetencia',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=6,
        spaceAfter=3
    )

    # Estilos para ENCABEZADOS DE TABLAS (Texto blanco nítido)
    th_style = ParagraphStyle('THLeft', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white)
    th_center = ParagraphStyle('THCenter', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=1)
    th_right = ParagraphStyle('THRight', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=2)

    # Estilos para el cuerpo de las tablas
    body_style = ParagraphStyle('TBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#1e293b'))
    body_bold = ParagraphStyle('TBodyBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor('#0f172a'))
    body_center = ParagraphStyle('TBodyCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor('#1e293b'))
    body_center_bold = ParagraphStyle('TBodyCenterBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor('#0f172a'))
    body_right = ParagraphStyle('TBodyRight', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, alignment=2, textColor=colors.HexColor('#1e293b'))
    body_right_bold = ParagraphStyle('TBodyRightBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, alignment=2, textColor=colors.HexColor('#0f172a'))

    def format_money(val):
        try:
            return f"C${float(val):,.2f}"
        except (ValueError, TypeError):
            return "C$0.00"

    def format_num(val):
        try:
            return f"{float(val):,.2f}" if float(val) % 1 != 0 else f"{int(val):,}"
        except (ValueError, TypeError):
            return "0"

    # Logo de la empresa
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base_dir, 'static', 'ferdel.png')

    f_inicio = context.get('fecha_inicio_formatted', context.get('fecha_inicio', ''))
    f_fin = context.get('fecha_fin_formatted', context.get('fecha_fin', ''))
    orden_txt = {
        'ventas': 'Mayor Venta Total',
        'efectivo': 'Mayor Efectivo Traído (Ventas Contado + Abonos)',
        'abonos': 'Mayor Cobro de Cartera (Abonos)',
        'unidades': 'Más Unidades Vendidas',
        'facturas': 'Más Facturas Realizadas'
    }.get(context.get('ordenar_por', 'ventas'), 'Mayor Venta')

    # Encabezado con Logo y Título
    info_text = [
        Paragraph("<b>FERDEL - REPORTE DE COMPETENCIA Y RENDIMIENTO DE VENDEDORES</b>", titulo_style),
        Paragraph("AUDITORÍA DE FACTURACIÓN, EFECTIVIDAD DE COBRANZA Y LIQUIDEZ POR RUTA", subtitulo_style),
        Paragraph(
            f"<b>Período:</b> {f_inicio} al {f_fin} &nbsp;|&nbsp; <b>Criterio:</b> {orden_txt} &nbsp;|&nbsp; <b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %I:%M %p')}",
            meta_style
        )
    ]

    header_table_data = []
    if os.path.exists(logo_path):
        try:
            img_logo = RLImage(logo_path, width=46, height=46)
            header_table_data = [[img_logo, info_text]]
            col_widths_hdr = [52, 688]
        except Exception:
            header_table_data = [[info_text]]
            col_widths_hdr = [740]
    else:
        header_table_data = [[info_text]]
        col_widths_hdr = [740]

    t_header = Table(header_table_data, colWidths=col_widths_hdr)
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 4))

    # 1. RESUMEN DE INDICADORES GLOBALES (KPIs con encabezados blancos)
    kpi_headers = [
        Paragraph("VENTAS TOTALES", th_center),
        Paragraph("EFECTIVO TRAÍDO", th_center),
        Paragraph("VTAS. CONTADO", th_center),
        Paragraph("VTAS. CRÉDITO", th_center),
        Paragraph("ABONOS COBRADOS", th_center),
        Paragraph("UNIDADES", th_center),
        Paragraph("FACTURAS", th_center)
    ]
    kpi_values = [
        Paragraph(f"<b>{format_money(context.get('total_ventas_global', 0))}</b>", body_center_bold),
        Paragraph(f"<b><font color='#059669'>{format_money(context.get('total_efectivo_global', 0))}</font></b>", body_center_bold),
        Paragraph(f"{format_money(context.get('total_contado_global', 0))}", body_center),
        Paragraph(f"{format_money(context.get('total_credito_global', 0))}", body_center),
        Paragraph(f"<b><font color='#2563eb'>{format_money(context.get('total_abonos_global', 0))}</font></b>", body_center),
        Paragraph(f"{format_num(context.get('total_unidades_global', 0))}", body_center),
        Paragraph(f"{format_num(context.get('total_facturas_global', 0))}", body_center)
    ]

    t_kpis = Table([kpi_headers, kpi_values], colWidths=[110, 110, 100, 100, 110, 106, 104])
    t_kpis.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f8fafc')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_kpis)
    story.append(Spacer(1, 4))

    # 2. CUADRO DE HONOR / PODIO TOP 3 (Encabezados blancos nítidos y filas claras temáticas)
    podio = context.get('podio', [])
    if podio:
        podio_rows = []
        medallas = ['1º LUGAR (ORO)', '2º LUGAR (PLATA)', '3º LUGAR (BRONCE)']
        for idx, p in enumerate(podio[:3]):
            med_txt = medallas[idx] if idx < len(medallas) else f"#{idx+1}"
            podio_rows.append([
                Paragraph(f"<b>{med_txt}</b>", body_center_bold),
                Paragraph(f"<b>{p.get('vendedor', '')}</b>", body_bold),
                Paragraph(f"{p.get('rutas', 'Sin ruta')}", body_style),
                Paragraph(f"<b>{format_money(p.get('total_ventas', 0))}</b>", body_right_bold),
                Paragraph(f"<b><font color='#059669'>{format_money(p.get('efectivo_total', 0))}</font></b>", body_right_bold),
                Paragraph(f"{format_money(p.get('total_abonos', 0))}", body_right),
                Paragraph(f"{format_num(p.get('unidades_vendidas', 0))} uds / {p.get('total_facturas', 0)} fact", body_center),
                Paragraph(f"<b>{p.get('porcentaje_participacion', 0)}%</b>", body_center_bold)
            ])
        
        podio_headers = [
            Paragraph("Puesto", th_center),
            Paragraph("Vendedor", th_style),
            Paragraph("Rutas", th_style),
            Paragraph("Total Ventas", th_right),
            Paragraph("Efectivo Traído", th_right),
            Paragraph("Abonos Cobrados", th_right),
            Paragraph("Volumen / Facturas", th_center),
            Paragraph("% Mercado", th_center)
        ]

        t_podio = Table([podio_headers] + podio_rows, colWidths=[80, 115, 95, 88, 92, 86, 114, 70])
        t_podio.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fef9c3')), # Oro suave y claro
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f1f5f9')), # Plata clara
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ffedd5')), # Bronce claro
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(Paragraph("🏆 Podio de Honor y Líderes", section_style))
        story.append(t_podio)
        story.append(Spacer(1, 4))

    # 3. TABLA GENERAL DE COMPETENCIA (LEADERBOARD COMPLETO)
    story.append(Paragraph("📊 Tabla General de Rendimiento y Liquidación", section_style))

    headers_tabla = [
        Paragraph("Pos", th_center),
        Paragraph("Vendedor", th_style),
        Paragraph("Rutas", th_style),
        Paragraph("Vtas. Contado", th_right),
        Paragraph("Vtas. Crédito", th_right),
        Paragraph("Total Ventas", th_right),
        Paragraph("Abonos Cartera", th_right),
        Paragraph("Efectivo Traído", th_right),
        Paragraph("Fact / Clts", th_center),
        Paragraph("Unidades", th_center),
        Paragraph("% Part.", th_center)
    ]

    tabla_filas = [headers_tabla]
    competidores = context.get('competidores', [])

    for c in competidores:
        pos_str = f"#{c.get('ranking', '')}"
        tabla_filas.append([
            Paragraph(pos_str, body_center_bold),
            Paragraph(f"<b>{c.get('vendedor', '')}</b>", body_style),
            Paragraph(f"{c.get('rutas', 'N/A')[:20]}", body_style),
            Paragraph(format_money(c.get('ventas_contado', 0)), body_right),
            Paragraph(format_money(c.get('ventas_credito', 0)), body_right),
            Paragraph(f"<b>{format_money(c.get('total_ventas', 0))}</b>", body_right_bold),
            Paragraph(format_money(c.get('total_abonos', 0)), body_right),
            Paragraph(f"<b><font color='#059669'>{format_money(c.get('efectivo_total', 0))}</font></b>", body_right_bold),
            Paragraph(f"{c.get('total_facturas', 0)} / {c.get('clientes_atendidos', 0)}", body_center),
            Paragraph(format_num(c.get('unidades_vendidas', 0)), body_center),
            Paragraph(f"{c.get('porcentaje_participacion', 0)}%", body_center_bold)
        ])

    # Fila de Totales Globales
    fila_totales = [
        Paragraph("<b>TOTAL</b>", body_center_bold),
        Paragraph(f"<b>{len(competidores)} Vendedores</b>", body_bold),
        Paragraph("<b>-</b>", body_center),
        Paragraph(f"<b>{format_money(context.get('total_contado_global', 0))}</b>", body_right_bold),
        Paragraph(f"<b>{format_money(context.get('total_credito_global', 0))}</b>", body_right_bold),
        Paragraph(f"<b>{format_money(context.get('total_ventas_global', 0))}</b>", body_right_bold),
        Paragraph(f"<b>{format_money(context.get('total_abonos_global', 0))}</b>", body_right_bold),
        Paragraph(f"<b><font color='#059669'>{format_money(context.get('total_efectivo_global', 0))}</font></b>", body_right_bold),
        Paragraph(f"<b>{context.get('total_facturas_global', 0)}</b>", body_center_bold),
        Paragraph(f"<b>{format_num(context.get('total_unidades_global', 0))}</b>", body_center_bold),
        Paragraph("<b>100.0%</b>", body_center_bold)
    ]
    tabla_filas.append(fila_totales)

    col_widths = [32, 105, 75, 64, 64, 74, 70, 78, 54, 56, 68]
    t_main = Table(tabla_filas, colWidths=col_widths)
    t_main.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
    ]))
    story.append(t_main)

    story.append(Spacer(1, 5))
    nota_style = ParagraphStyle(
        'NotaPDF',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#64748b')
    )
    story.append(Paragraph(
        "* <b>Efectivo Traído</b> = Ventas de Contado + Abonos de Cartera cobrados en Efectivo. "
        "Documento confidencial para uso administrativo y directivo de FERDEL.",
        nota_style
    ))

    doc.build(story)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    response.headers['Content-type'] = 'application/pdf'
    return response



