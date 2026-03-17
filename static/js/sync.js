// static/js/sync.js - Manejador de sincronización
class SyncManager {
    constructor(db) {
        this.db = db;
        this.sincronizando = false;
    }

    async sincronizarTodo() {
        if (this.sincronizando) {
            console.log('Ya hay una sincronización en curso');
            return;
        }

        this.sincronizando = true;
        this.mostrarEstado('Sincronizando...');

        try {
            // 1. Sincronizar ventas pendientes
            await this.sincronizarVentas();
            
            // 2. Sincronizar movimientos de caja
            await this.sincronizarMovimientos();
            
            // 3. Actualizar inventario desde servidor
            await this.actualizarInventario();
            
            this.mostrarEstado('Sincronización completa', 'success');
        } catch (error) {
            console.error('Error en sincronización:', error);
            this.mostrarEstado('Error en sincronización', 'error');
        } finally {
            this.sincronizando = false;
        }
    }

    async sincronizarVentas() {
        const ventasPendientes = await this.db.obtenerVentasPendientes();
        
        if (ventasPendientes.length === 0) {
            return;
        }

        const response = await fetch('/api/vendedor/venta/offline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ventas: ventasPendientes })
        });

        const result = await response.json();

        if (result.success) {
            for (const res of result.resultados) {
                if (res.success) {
                    await this.db.marcarVentaSincronizada(res.id_temp);
                }
            }
            await this.db.limpiarVentasSincronizadas();
        }
    }

    async actualizarInventario() {
        const response = await fetch('/api/vendedor/inventario/completo');
        const data = await response.json();

        if (data.success) {
            await this.db.guardarInventario(data.ID_Asignacion, data.inventario);
            localStorage.setItem('ultima_sincronizacion', data.timestamp);
        }
    }

    async sincronizarMovimientos() {
        // Similar a ventas pero para movimientos de caja
        // Implementar según necesidades
    }

    mostrarEstado(mensaje, tipo = 'info') {
        const evento = new CustomEvent('sync-status', {
            detail: { mensaje, tipo }
        });
        document.body.dispatchEvent(evento);
    }
}