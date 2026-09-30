import re

with open('templates/admin/ventas/ventas_salidas.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the "Anular venta" button
btn_pattern = re.compile(r'{%\s*if venta.Estado_Formateado == \'ACTIVA\'\s*%}\s*<button type="button" class="btn btn-outline-danger btn-action"\s*data-bs-toggle="modal" data-bs-target="#anularVentaModal"\s*data-id="{{ venta.ID_Factura }}" title="Anular venta">\s*<i class="fas fa-ban"></i>\s*</button>\s*{%\s*endif\s*%}', re.DOTALL)
content = btn_pattern.sub('', content)

# 2. Remove the modal
modal_pattern = re.compile(r'<!-- ========================================================\s*MODAL DE ANULACIÓN DE VENTA\s*======================================================== -->\s*<div class="modal fade" id="anularVentaModal".*?</div>\s*</div>\s*</div>\s*</div>', re.DOTALL)
content = modal_pattern.sub('', content)

# 3. Remove CSS for Modal (optional but good for cleanliness)
css_pattern = re.compile(r'/\* ========================================================\s*MODAL DE ANULACIÓN\s*======================================================== \*/.*?\.modal-footer \{.*?\}', re.DOTALL)
content = css_pattern.sub('', content)

# 4. Remove the JS for the modal
js_vars_pattern = re.compile(r'let ventaIdActual = null;\s*let datosVentaActual = null;')
content = js_vars_pattern.sub('', content)

js_url_pattern = re.compile(r'function construirUrlAnulacion\(ventaId\) \{[^\}]+\}')
content = js_url_pattern.sub('', content)

js_logic_pattern = re.compile(r'// ============================================\s*// MANEJO DEL MODAL DE ANULACIÓN\s*// ============================================.*?// ============================================\s*// INICIALIZACIÓN PRINCIPAL', re.DOTALL)
content = js_logic_pattern.sub('// ============================================\n    // INICIALIZACIÓN PRINCIPAL', content)

js_listeners_pattern = re.compile(r'// Listeners Modal de Anulación.*?enviarFormularioAnulacion\(\);\s*\}\);', re.DOTALL)
content = js_listeners_pattern.sub('', content)

with open('templates/admin/ventas/ventas_salidas.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Modal and button removed successfully.")
