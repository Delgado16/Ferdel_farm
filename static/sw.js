// static/sw.js - Service Worker
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
  'static/icon/icon-192.png',
  'static/ferdel.png'

];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response; // Si está en cache, lo devuelve
        }
        return fetch(event.request); // Si no, va a internet
      })
  );
});