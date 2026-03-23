const CACHE_NAME = 'vendedor-cache-v2';

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
});

// Estrategia de caché para las peticiones
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const request = event.request;

  // 🔧 Estrategia 1: Imágenes (Cache First con respaldo de red)
  if (url.pathname.match(/\.(jpg|jpeg|png|gif|webp|svg|bmp|ico)$/i)) {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          // Si está en caché, lo devolvemos
          if (cachedResponse) {
            console.log('[Service Worker] Imagen desde caché:', url.pathname);
            return cachedResponse;
          }
          
          // Si no está en caché, vamos a la red
          console.log('[Service Worker] Imagen desde red:', url.pathname);
          return fetch(request)
            .then(networkResponse => {
              // Verificar que sea una respuesta válida
              if (!networkResponse || networkResponse.status !== 200) {
                return networkResponse;
              }
              
              // Clonar y guardar en caché para futuras solicitudes
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(request, responseToCache);
                })
                .catch(error => {
                  console.error('[Service Worker] Error guardando imagen en caché:', error);
                });
              
              return networkResponse;
            })
            .catch(error => {
              console.error('[Service Worker] Error fetching imagen:', error);
              // Opcional: devolver una imagen por defecto si falla todo
              // return caches.match('/static/img/placeholder.png');
            });
        })
    );
  }
  
  // 🔧 Estrategia 2: API y datos dinámicos (Network First)
  else if (url.pathname.includes('/api/') || url.pathname.includes('/ajax/')) {
    event.respondWith(
      fetch(request)
        .then(networkResponse => {
          // Si la petición es exitosa, actualizamos caché
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
          // Si falla la red, buscamos en caché
          console.log('[Service Worker] API desde caché (offline):', url.pathname);
          return caches.match(request);
        })
    );
  }
  
  // 🔧 Estrategia 3: HTML y recursos principales (Cache First con revalidación)
  else if (url.pathname.startsWith('/vendedor/') || 
           url.pathname.match(/\.(html|css|js)$/i) ||
           url.pathname === '/' ||
           url.pathname === '/index.html') {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          // Si está en caché, devolvemos y actualizamos en segundo plano
          if (cachedResponse) {
            // Revalidación en segundo plano
            fetch(request)
              .then(networkResponse => {
                if (networkResponse && networkResponse.status === 200) {
                  const responseToCache = networkResponse.clone();
                  caches.open(CACHE_NAME)
                    .then(cache => {
                      cache.put(request, responseToCache);
                    });
                }
              })
              .catch(error => {
                console.error('[Service Worker] Error revalidando recurso:', error);
              });
            
            return cachedResponse;
          }
          
          // Si no está en caché, vamos a la red
          return fetch(request)
            .then(networkResponse => {
              if (!networkResponse || networkResponse.status !== 200) {
                return networkResponse;
              }
              
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(request, responseToCache);
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
          // Guardar en caché si es exitoso
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
          console.log('[Service Worker] Recurso desde caché (offline):', url.pathname);
          return caches.match(request);
        })
    );
  }
});

// Opcional: Mensajes desde la página principal
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  // Permitir forzar limpieza de caché desde la app
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.delete(CACHE_NAME).then(() => {
        console.log('[Service Worker] Caché eliminado manualmente');
        event.ports[0].postMessage({ success: true });
      })
    );
  }
});