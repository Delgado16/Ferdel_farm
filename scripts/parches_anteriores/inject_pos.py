import sys

html_content = open('templates/admin/ventas/crear_venta.html', 'r', encoding='utf-8').read()

parts = html_content.split('<div class="card border-0 shadow-sm">', 1)

pos_grid_html = """
<div class="row">
    <!-- Panel Izquierdo: Catálogo POS -->
    <div class="col-lg-7 col-md-12 mb-4">
        <div class="card border-0 shadow-sm h-100" style="background: #f8f9fa;">
            <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center p-3">
                <h5 class="mb-0"><i class="bi bi-grid-3x3-gap me-2"></i>Punto de Venta</h5>
                <div class="w-50 position-relative">
                    <i class="bi bi-search position-absolute top-50 start-0 translate-middle-y ms-2 text-muted"></i>
                    <input type="text" id="pos-search" class="form-control form-control-sm ps-4" placeholder="Buscar producto..." oninput="renderPosProducts()">
                </div>
            </div>
            <div class="card-body">
                <!-- Categorías -->
                <div class="d-flex overflow-auto mb-3 pb-2" id="pos-categories" style="gap: 10px; white-space: nowrap;">
                    <button type="button" class="btn btn-primary pos-cat-btn" data-cat="todas" onclick="filtrarPosCat('todas', this)">Todas</button>
                    {% for cat in categorias %}
                    <button type="button" class="btn btn-outline-primary pos-cat-btn" data-cat="{{ cat.ID_Categoria }}" onclick="filtrarPosCat('{{ cat.ID_Categoria }}', this)">{{ cat.Descripcion }}</button>
                    {% endfor %}
                </div>
                
                <!-- Grid de productos -->
                <div class="row g-2" id="pos-product-grid" style="max-height: 65vh; overflow-y: auto;">
                    <!-- Renderizado por JS -->
                </div>
            </div>
        </div>
    </div>

    <!-- Panel Derecho: Formulario -->
    <div class="col-lg-5 col-md-12">
        <div class="card border-0 shadow-sm" style="border-top: 5px solid var(--primary-color) !important;">
"""

new_content = parts[0] + pos_grid_html + parts[1]
new_content = new_content.replace('</div>\n\n<script>', '</div></div></div>\n\n<script>')

pos_js = """
    // ============================================
    // LÓGICA DE PUNTO DE VENTA (POS)
    // ============================================
    let posCategoriaActual = 'todas';

    function filtrarPosCat(catId, btn) {
        posCategoriaActual = catId;
        document.querySelectorAll('.pos-cat-btn').forEach(b => {
            b.classList.remove('btn-primary');
            b.classList.add('btn-outline-primary');
        });
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        renderPosProducts();
    }

    function renderPosProducts() {
        const grid = document.getElementById('pos-product-grid');
        if (!grid) return;
        
        const searchVal = document.getElementById('pos-search').value.toLowerCase();
        
        let productosAMostrar = typeof productosFiltradosPorCliente !== 'undefined' && productosFiltradosPorCliente.length > 0 ? productosFiltradosPorCliente : (typeof productosBase !== 'undefined' ? productosBase : []);
        
        const bodegasSeleccionadas = Array.from(document.querySelectorAll('.filtro-bodega-cb:checked')).map(cb => cb.value);
        if (bodegasSeleccionadas.length > 0) {
            productosAMostrar = productosAMostrar.filter(p => bodegasSeleccionadas.includes(String(p.ID_Bodega || '1')));
        } else {
            productosAMostrar = [];
        }

        if (posCategoriaActual !== 'todas') {
            productosAMostrar = productosAMostrar.filter(p => (p.ID_Categoria || p.id_categoria) == posCategoriaActual);
        }

        if (searchVal) {
            productosAMostrar = productosAMostrar.filter(p => 
                (p.Descripcion || '').toLowerCase().includes(searchVal) || 
                (p.COD_Producto || '').toLowerCase().includes(searchVal)
            );
        }

        let html = '';
        if (productosAMostrar.length === 0) {
            html = '<div class="col-12 text-center py-5 text-muted"><i class="bi bi-box-seam fs-1 d-block mb-2"></i>No hay productos disponibles</div>';
        } else {
            productosAMostrar.forEach(p => {
                const precio = typeof obtenerPrecioPorPerfil === 'function' ? obtenerPrecioPorPerfil(p, perfilClienteActual) : 0;
                const stock = parseFloat(p.Existencias || 0);
                const stockClass = stock <= 0 ? 'text-danger' : (stock <= 5 ? 'text-warning' : 'text-success');
                const bodegaNombre = p.BodegaNombre || 'Principal';
                
                html += `
                <div class="col-xl-4 col-lg-6 col-md-4 col-sm-6">
                    <div class="card h-100 product-pos-card shadow-sm" style="cursor:pointer; border: 1px solid #e9ecef; transition: transform 0.1s;" onclick="agregarDesdePos('${p.ID_Producto || p.id}', '${p.ID_Bodega || 1}')" onmouseover="this.style.transform='scale(1.02)'; this.style.borderColor='var(--primary-color)';" onmouseout="this.style.transform='scale(1)'; this.style.borderColor='#e9ecef';">
                        <div class="card-body p-2 d-flex flex-column">
                            <span class="badge bg-secondary mb-1" style="font-size: 0.65rem; align-self: flex-start;">${p.COD_Producto || 'S/C'}</span>
                            <h6 class="card-title mb-1" style="font-size: 0.85rem; flex-grow: 1; line-height: 1.2;">${p.Descripcion}</h6>
                            <div class="d-flex justify-content-between align-items-end mt-2">
                                <span class="fw-bold text-primary">C$ ${precio.toFixed(2)}</span>
                                <div class="text-end">
                                    <small class="${stockClass} d-block" style="font-size: 0.7rem; font-weight: bold;">Stock: ${stock}</small>
                                    <small class="text-muted d-block" style="font-size: 0.65rem;">${bodegaNombre}</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                `;
            });
        }
        grid.innerHTML = html;
    }

    function agregarDesdePos(prodId, bodegaId) {
        let emptySelect = null;
        const selects = document.querySelectorAll('.producto-select');
        for (let sel of selects) {
            if (!sel.value) {
                emptySelect = sel;
                break;
            }
        }
        
        if (!emptySelect) {
            const btn = document.querySelector('button[onclick="agregarProducto()"]') || document.querySelector('.btn-outline-primary i.bi-plus')?.parentElement;
            if (btn) btn.click();
            const newSelects = document.querySelectorAll('.producto-select');
            emptySelect = newSelects[newSelects.length - 1];
        }
        
        if (emptySelect) {
            emptySelect.value = `${prodId}_${bodegaId}`;
            emptySelect.dispatchEvent(new Event('change'));
            
            const row = emptySelect.closest('.product-card');
            if (row) {
                setTimeout(() => {
                    const qty = row.querySelector('.cantidad');
                    if (qty) {
                        qty.value = (parseFloat(qty.value || 0) + 1);
                        qty.dispatchEvent(new Event('input'));
                        qty.dispatchEvent(new Event('change'));
                    }
                    row.style.backgroundColor = '#d4edda';
                    setTimeout(() => { row.style.backgroundColor = '#fff'; }, 500);
                }, 200);
            }
        }
    }

    const originalActualizarTodosLosSelects = window.actualizarTodosLosSelectsProductosConPerfil;
    window.actualizarTodosLosSelectsProductosConPerfil = function() {
        if (originalActualizarTodosLosSelects) originalActualizarTodosLosSelects();
        renderPosProducts();
    };

    const originalAplicarFiltro = window.aplicarFiltroCategoria;
    window.aplicarFiltroCategoria = function() {
        if (originalAplicarFiltro) originalAplicarFiltro();
        renderPosProducts();
    };
    
    document.querySelectorAll('.filtro-bodega-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            renderPosProducts();
        });
    });

    setTimeout(renderPosProducts, 1500);
"""
new_content = new_content.replace('</script>', pos_js + '\n</script>')

with open('templates/admin/ventas/crear_venta.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("POS layout injected successfully.")
