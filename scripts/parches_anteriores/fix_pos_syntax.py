import re

with open('templates/admin/ventas/crear_venta.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove anything that looks like POS logic
# We'll use regex to remove from "// ====" to "setTimeout(renderPosProducts, 1500);"
pattern = re.compile(r'// ============================================\s*// LÓGICA DE PUNTO DE VENTA.*?setTimeout\(renderPosProducts, 1500\);', re.DOTALL)
content = pattern.sub('', content)

# Clean up sweetalert again just in case
pattern_sa = re.compile(r'<script src="https://cdn\.jsdelivr\.net/npm/sweetalert2@11">.*?</script>', re.DOTALL)
content = pattern_sa.sub('<script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>', content)

# Remove the window._posInjected stuff if it got left behind
pattern_inj = re.compile(r'if\(window\._posInjected\).*?}\s*setTimeout\(renderPosProducts, 1500\);', re.DOTALL)
content = pattern_inj.sub('', content)

pos_js = """
    // ============================================
    // LÓGICA DE PUNTO DE VENTA (POS) MEJORADA
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
                const precioMostrar = parseFloat(p.Precio_Mercado || p.precio_mercado || 0);
                const stock = parseFloat(p.Existencias || 0);
                const stockClass = stock <= 0 ? 'text-danger' : (stock <= 5 ? 'text-warning' : 'text-success');
                const bodegaNombre = p.BodegaNombre || 'Principal';
                
                html += `
                <div class="col-xl-4 col-lg-6 col-md-6 col-sm-6">
                    <div class="card h-100 product-pos-card shadow-sm border-0" style="cursor:pointer; transition: all 0.2s; background: #fff; border-radius: 10px; overflow: hidden;" onclick="agregarDesdePos('${p.ID_Producto || p.id}', '${p.ID_Bodega || 1}')" onmouseover="this.style.transform='translateY(-3px)'; this.style.boxShadow='0 6px 12px rgba(0,0,0,0.1) !important';" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.05) !important';">
                        <div class="card-body p-3 d-flex flex-column">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge bg-secondary" style="font-size: 0.7rem;">${p.COD_Producto || 'S/C'}</span>
                                <span class="${stockClass} fw-bold" style="font-size: 0.75rem;"><i class="bi bi-box"></i> ${stock}</span>
                            </div>
                            <h6 class="card-title mb-2 text-dark" style="font-size: 0.9rem; flex-grow: 1; line-height: 1.3; font-weight: 600;">${p.Descripcion}</h6>
                            <div class="d-flex justify-content-between align-items-end mt-1 pt-2 border-top">
                                <span class="fw-bold text-primary fs-6">C$ ${precioMostrar.toFixed(2)}</span>
                                <small class="text-muted" style="font-size: 0.7rem;"><i class="bi bi-shop"></i> ${bodegaNombre}</small>
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
        const targetValue = `${prodId}_${bodegaId}`;
        const selects = document.querySelectorAll('.producto-select');
        
        let existingRow = null;
        for (let sel of selects) {
            if (sel.value === targetValue) {
                existingRow = sel.closest('.product-card');
                break;
            }
        }
        
        if (existingRow) {
            const qtyInput = existingRow.querySelector('.cantidad');
            if (qtyInput) {
                qtyInput.value = parseFloat(qtyInput.value || 0) + 1;
                qtyInput.dispatchEvent(new Event('input'));
                qtyInput.dispatchEvent(new Event('change'));
                
                existingRow.style.transition = 'background-color 0.3s';
                existingRow.style.backgroundColor = '#fff3cd'; 
                setTimeout(() => { existingRow.style.backgroundColor = '#fff'; }, 600);
            }
            return;
        }

        let emptySelect = null;
        for (let sel of selects) {
            if (!sel.value) {
                emptySelect = sel;
                break;
            }
        }
        
        if (!emptySelect) {
            const btnAgregar = document.querySelector('button[onclick="agregarProducto()"]') || document.querySelector('.btn-outline-primary i.bi-plus')?.parentElement;
            if (btnAgregar) {
                btnAgregar.click();
            } else {
                if(typeof agregarProducto === 'function') agregarProducto();
            }
            
            setTimeout(() => {
                const newSelects = document.querySelectorAll('.producto-select');
                emptySelect = newSelects[newSelects.length - 1];
                if(emptySelect) {
                    fillEmptySelect(emptySelect, targetValue);
                }
            }, 100);
            return;
        }
        
        fillEmptySelect(emptySelect, targetValue);
    }

    function fillEmptySelect(emptySelect, targetValue) {
        emptySelect.value = targetValue;
        emptySelect.dispatchEvent(new Event('change'));
        
        const row = emptySelect.closest('.product-card');
        if (row) {
            setTimeout(() => {
                const qty = row.querySelector('.cantidad');
                if (qty && (!qty.value || qty.value == "0")) {
                    qty.value = 1;
                    qty.dispatchEvent(new Event('input'));
                    qty.dispatchEvent(new Event('change'));
                }
                row.style.transition = 'background-color 0.3s';
                row.style.backgroundColor = '#d4edda';
                setTimeout(() => { row.style.backgroundColor = '#fff'; }, 600);
            }, 200);
        }
    }

    if(window._posInjected) {
        console.log("POS already injected");
    } else {
        window._posInjected = true;
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
    }

    setTimeout(renderPosProducts, 1500);
"""

# Find the end of the script tag right before {% endblock %}
# Or better, just do it before the LAST </script> tag.
parts = content.rsplit('</script>', 1)
if len(parts) == 2:
    new_content = parts[0] + pos_js + '\n</script>' + parts[1]
else:
    new_content = content + '\n<script>\n' + pos_js + '\n</script>'

with open('templates/admin/ventas/crear_venta.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Fixed syntax error completely.")
