import re

with open('templates/admin/ventas/crear_venta.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove POS Grid HTML
html_pattern = re.compile(r'<div class="row">\s*<!-- Panel Izquierdo: Catálogo POS -->.*?<!-- Panel Derecho: Formulario -->\s*<div class="col-lg-5 col-md-12">\s*<div class="card border-0 shadow-sm" style="border-top: 5px solid var\(--primary-color\) !important;">', re.DOTALL)
content = html_pattern.sub('<div class="card border-0 shadow-sm">', content)

# 2. Fix the closing div tags. 
content = content.replace('</div></div></div>\n\n<script>', '</div>\n\n<script>')

# 3. Remove POS Javascript
js_pattern = re.compile(r'// ============================================\s*// LÓGICA DE PUNTO DE VENTA \(POS\) MEJORADA.*?setTimeout\(renderPosProducts, 1500\);\s*', re.DOTALL)
content = js_pattern.sub('', content)

with open('templates/admin/ventas/crear_venta.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Reverted to original successfully.")
