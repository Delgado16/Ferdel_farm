// static/sw.js - Service Worker con soporte offline completo
const CACHE_NAME = 'vendedor-offline-v1';
const API_CACHE = 'api-cache-v1';

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll([
                '/vendedor/dashboard',
                '/vendedor/ventas',
                '/vendedor/venta/crear',
                '/vendedor/inventario',
                '/vendedor/clientes',
                '/static/js/db.js',
                '/static/js/sync.js'
            ]);
        })
    );
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);
    
    // Estrategia para APIs
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(apiStrategy(event.request));
        return;
    }
    
    // Estrategia para páginas
    if (url.pathname.startsWith('/vendedor/')) {
        event.respondWith(pageStrategy(event.request));
        return;
    }
    
    // Para archivos estáticos
    event.respondWith(
        caches.match(event.request)
            .then(response => response || fetch(event.request))
    );
});

async function apiStrategy(request) {
    try {
        // Intentar red primero
        const response = await fetch(request);
        
        // Si es GET y exitoso, cachear
        if (request.method === 'GET' && response.ok) {
            const cache = await caches.open(API_CACHE);
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        // Si falla la red, buscar en cache
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        
        // Si es POST, retornar error amigable
        if (request.method === 'POST') {
            return new Response(JSON.stringify({
                success: false,
                message: 'Sin conexión. La operación se guardará cuando tengas internet.',
                offline: true
            }), {
                status: 503,
                headers: { 'Content-Type': 'application/json' }
            });
        }
        
        return new Response(JSON.stringify({
            success: false,
            message: 'Sin conexión',
            offline: true
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

async function pageStrategy(request) {
    // Intentar cache primero
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }
    
    try {
        const response = await fetch(request);
        
        // Cachear la página para futuras visitas offline
        if (response.ok && response.headers.get('content-type')?.includes('text/html')) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        
        return response;
    } catch (error) {
        // Si no hay cache y no hay red, mostrar página simple
        return new Response(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Sin conexión</title>
                <style>
                    body { font-family: Arial; text-align: center; padding: 2rem; }
                    .card { background: #f8f9fa; border-radius: 8px; padding: 2rem; max-width: 400px; margin: 0 auto; }
                    h1 { color: #dc3545; }
                    button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>📡 Sin conexión</h1>
                    <p>Esta página no está disponible offline.</p>
                    <button onclick="window.location.href='/vendedor/dashboard'">Ir al Dashboard</button>
                </div>
            </body>
            </html>
        `, {
            status: 503,
            headers: { 'Content-Type': 'text/html' }
        });
    }
}