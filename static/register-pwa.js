// static/js/register-pwa.js

class PWAManager {
  constructor() {
    this.swRegistration = null;
  }

  async register() {
    if (!('serviceWorker' in navigator)) {
      console.log('[PWA] Service Worker no soportado');
      return;
    }

    try {
      // Registrar SW en la raíz para que cubra TODAS las rutas
      this.swRegistration = await navigator.serviceWorker.register('/static/sw.js', {
        scope: '/'  // Importante: scope raíz para todas las rutas
      });
      
      console.log('[PWA] Service Worker registrado correctamente');
      console.log('[PWA] Scope:', this.swRegistration.scope);
      
      this.handleUpdates();
      
    } catch (error) {
      console.error('[PWA] Error registrando SW:', error);
    }
  }

  handleUpdates() {
    if (!this.swRegistration) return;
    
    this.swRegistration.addEventListener('updatefound', () => {
      const newWorker = this.swRegistration.installing;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          this.showUpdateNotification();
        }
      });
    });
  }

  showUpdateNotification() {
    const toast = document.createElement('div');
    toast.className = 'pwa-update-toast';
    toast.innerHTML = `
      <div class="alert alert-info alert-dismissible fade show">
        <strong>🔄 Nueva versión disponible</strong>
        <button class="btn btn-sm btn-primary ms-2" onclick="location.reload()">
          Actualizar
        </button>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 10000);
  }
}

// Inicializar cuando el DOM esté listo
const pwaManager = new PWAManager();
document.addEventListener('DOMContentLoaded', () => {
  pwaManager.register();
});