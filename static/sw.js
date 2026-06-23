const CACHE_NAME = 'vendedor-cache-v3';

// SOLO las rutas que existen en tu app
const urlsToCache = [
  '/vendedor/dashboard',
  '/vendedor/mis-rutas',
  '/vendedor/inventario',
  '/vendedor/ventas',
  '/vendedor/venta/crear',
  '/vendedor/clientes',
  '/vendedor/gastos',
  '/vendedor/caja/mis_movimientos',
  '/vendedor/movimientos/historial',
  '/vendedor/movimientos/entrada-bodega',
  '/vendedor/movimientos/devolucion-bodega',
  '/vendedor/movimientos/merma',
  '/static/icon/icon-192.png',
  '/static/ferdel.png'
];

// Instalación: precachea los recursos estáticos
self.addEventListener('install', event => {
  console.log('[Service Worker] Instalando...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Cacheando recursos estáticos');
        return cache.addAll(urlsToCache);
      })
      .catch(error => {
        console.error('[Service Worker] Error en instalación:', error);
        // Intentar cachear individualmente para identificar el error
        urlsToCache.forEach(url => {
          fetch(url).catch(e => console.error(`Error cacheando ${url}:`, e));
        });
      })
  );
  // Activar inmediatamente
  self.skipWaiting();
});

// Activación: limpia cachés antiguos
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activando...');
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            console.log('[Service Worker] Eliminando caché antiguo:', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  // Tomar control de las páginas abiertas inmediatamente
  event.waitUntil(clients.claim());
  console.log('[Service Worker] Activado y controlando clientes');
});

// Estrategia de caché para las peticiones
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const request = event.request;

  // Solo interceptar peticiones GET (las peticiones POST/PUT/DELETE deben pasar directo a la red)
  if (request.method !== 'GET') {
    return;
  }

  // 🔧 Estrategia 1: Imágenes (Cache First con respaldo de red)
  if (url.pathname.match(/\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)$/i)) {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          if (cachedResponse) {
            console.log('[Service Worker] ✅ Imagen desde caché:', url.pathname);
            return cachedResponse;
          }
          
          console.log('[Service Worker] 🌐 Imagen desde red:', url.pathname);
          return fetch(request)
            .then(networkResponse => {
              if (!networkResponse || networkResponse.status !== 200) {
                return networkResponse;
              }
              
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(request, responseToCache);
                  console.log('[Service Worker] 💾 Imagen guardada en caché:', url.pathname);
                })
                .catch(error => {
                  console.error('[Service Worker] Error guardando imagen en caché:', error);
                });
              
              return networkResponse;
            })
            .catch(error => {
              console.error('[Service Worker] ❌ Error fetching imagen:', url.pathname, error);
              if (url.pathname.includes('ferdel.png')) {
                console.log('[Service Worker] 🖼️ Usando fallback para logo');
                return new Response(
                  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 120">
                    <rect width="400" height="120" fill="#2c5e2e"/>
                    <rect x="10" y="10" width="380" height="100" fill="#3c8c3c" rx="5"/>
                    <text x="200" y="55" font-family="Arial" font-size="28" fill="white" text-anchor="middle" font-weight="bold">FERDEL</text>
                    <text x="200" y="85" font-family="Arial" font-size="14" fill="#f0f0f0" text-anchor="middle">Granja Avícola</text>
                    <text x="200" y="102" font-family="Arial" font-size="11" fill="#ffd966" text-anchor="middle">Sistema de Ventas</text>
                  </svg>`,
                  {
                    headers: { 'Content-Type': 'image/svg+xml' }
                  }
                );
              }
              return new Response(
                `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
                  <rect width="100" height="100" fill="#cccccc"/>
                  <text x="50" y="55" font-family="Arial" font-size="14" fill="#666" text-anchor="middle">📷</text>
                </svg>`,
                {
                  headers: { 'Content-Type': 'image/svg+xml' }
                }
              );
            });
        })
    );
  }
  
  // 🔧 Estrategia 2: API y datos dinámicos (Network First)
  else if (url.pathname.includes('/api/') || 
           url.pathname.includes('/ajax/') ||
           url.pathname.startsWith('/vendedor/') ||
           url.pathname.startsWith('/admin/') ||
           url.pathname.startsWith('/bodega/')) {
    event.respondWith(
      fetch(request)
        .then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(request, responseToCache);
              })
              .catch(error => {
                console.error('[Service Worker] Error guardando API en caché:', error);
              });
          }
          return networkResponse;
        })
        .catch(() => {
          console.log('[Service Worker] 📦 API desde caché (offline):', url.pathname);
          return caches.match(request);
        })
    );
  }
  
  // 🔧 Estrategia 3: HTML y recursos principales (Cache First con revalidación)
  else if (url.pathname.match(/\.(html|css|js)$/i) ||
           url.pathname === '/' ||
           url.pathname === '/index.html') {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          if (cachedResponse) {
            // Revalidación en segundo plano
            fetch(request)
              .then(networkResponse => {
                if (networkResponse && networkResponse.status === 200) {
                  const responseToCache = networkResponse.clone();
                  caches.open(CACHE_NAME)
                    .then(cache => {
                      cache.put(request, responseToCache);
                      console.log('[Service Worker] 🔄 Revalidado:', url.pathname);
                    });
                }
              })
              .catch(error => {
                console.error('[Service Worker] Error revalidando recurso:', error);
              });
            
            return cachedResponse;
          }
          
          return fetch(request)
            .then(networkResponse => {
              if (!networkResponse || networkResponse.status !== 200) {
                return networkResponse;
              }
              
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(request, responseToCache);
                  console.log('[Service Worker] 💾 Cacheado:', url.pathname);
                });
              
              return networkResponse;
            });
        })
    );
  }
  
  // 🔧 Estrategia 4: Otros recursos (Network First con fallback a caché)
  else {
    event.respondWith(
      fetch(request)
        .then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(request, responseToCache);
              })
              .catch(error => {
                console.error('[Service Worker] Error guardando recurso en caché:', error);
              });
          }
          return networkResponse;
        })
        .catch(() => {
          console.log('[Service Worker] 📦 Recurso desde caché (offline):', url.pathname);
          return caches.match(request);
        })
    );
  }
});

// Mensajes desde la página principal
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
    console.log('[Service Worker] Skip waiting ejecutado');
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.delete(CACHE_NAME).then(() => {
        console.log('[Service Worker] 🗑️ Caché eliminado manualmente');
        if (event.ports && event.ports[0]) {
          event.ports[0].postMessage({ success: true });
        }
      })
    );
  }
  
  if (event.data && event.data.type === 'CHECK_IMAGE_CACHE' && event.data.url) {
    event.waitUntil(
      caches.match(event.data.url).then(response => {
        if (event.ports && event.ports[0]) {
          event.ports[0].postMessage({ 
            cached: !!response,
            url: event.data.url 
          });
        }
      })
    );
  }
});

self.addEventListener('updatefound', () => {
  console.log('[Service Worker] Nueva versión encontrada');
});