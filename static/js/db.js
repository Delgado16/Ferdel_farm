// static/js/db.js - Base de datos offline
const DB_NAME = 'VendedorOfflineDB';
const DB_VERSION = 1;

class OfflineDB {
    constructor() {
        this.db = null;
    }

    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve(this);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Store para inventario
                if (!db.objectStoreNames.contains('inventario')) {
                    const inventarioStore = db.createObjectStore('inventario', { keyPath: 'ID_Producto' });
                    inventarioStore.createIndex('asignacion', 'ID_Asignacion');
                }

                // Store para ventas pendientes de sincronizar
                if (!db.objectStoreNames.contains('ventas_pendientes')) {
                    const ventasStore = db.createObjectStore('ventas_pendientes', { 
                        keyPath: 'id_temp', 
                        autoIncrement: true 
                    });
                    ventasStore.createIndex('fecha', 'fecha');
                    ventasStore.createIndex('sincronizado', 'sincronizado');
                }

                // Store para clientes
                if (!db.objectStoreNames.contains('clientes')) {
                    const clientesStore = db.createObjectStore('clientes', { keyPath: 'ID_Cliente' });
                    clientesStore.createIndex('ruta', 'ID_Ruta');
                    clientesStore.createIndex('nombre', 'Nombre');
                }

                // Store para movimientos de caja pendientes
                if (!db.objectStoreNames.contains('movimientos_pendientes')) {
                    const movimientosStore = db.createObjectStore('movimientos_pendientes', { 
                        keyPath: 'id_temp', 
                        autoIncrement: true 
                    });
                    movimientosStore.createIndex('tipo', 'tipo');
                    movimientosStore.createIndex('sincronizado', 'sincronizado');
                }
            };
        });
    }

    async guardarInventario(asignacionId, productos) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['inventario'], 'readwrite');
            const store = transaction.objectStore('inventario');
            
            productos.forEach(producto => {
                producto.ID_Asignacion = asignacionId;
                store.put(producto);
            });

            transaction.oncomplete = () => resolve();
            transaction.onerror = () => reject(transaction.error);
        });
    }

    async obtenerInventario(asignacionId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['inventario'], 'readonly');
            const store = transaction.objectStore('inventario');
            const index = store.index('asignacion');
            const request = index.getAll(asignacionId);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async guardarVentaOffline(ventaData) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['ventas_pendientes'], 'readwrite');
            const store = transaction.objectStore('ventas_pendientes');
            
            const ventaOffline = {
                ...ventaData,
                fecha: new Date().toISOString(),
                sincronizado: false,
                intentos_sincronizacion: 0
            };

            const request = store.add(ventaOffline);
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async obtenerVentasPendientes() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['ventas_pendientes'], 'readonly');
            const store = transaction.objectStore('ventas_pendientes');
            const index = store.index('sincronizado');
            const request = index.getAll(false);

            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async marcarVentaSincronizada(idTemp) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['ventas_pendientes'], 'readwrite');
            const store = transaction.objectStore('ventas_pendientes');
            const request = store.get(idTemp);

            request.onsuccess = () => {
                const venta = request.result;
                venta.sincronizado = true;
                store.put(venta);
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    }

    async limpiarVentasSincronizadas() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(['ventas_pendientes'], 'readwrite');
            const store = transaction.objectStore('ventas_pendientes');
            const index = store.index('sincronizado');
            const request = index.getAll(true);

            request.onsuccess = () => {
                const ventas = request.result;
                ventas.forEach(venta => {
                    store.delete(venta.id_temp);
                });
                resolve();
            };
            request.onerror = () => reject(request.error);
        });
    }
}

// Instancia global
const offlineDB = new OfflineDB();