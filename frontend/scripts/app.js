/**
 * Pi Display Manager - Main Application Entry Point
 * Initializes the application
 */

// Application initialization
document.addEventListener("DOMContentLoaded", () => {
  // Initialize event listeners
  EventListeners.init();

  // Load initial data
  StatusManager.refresh();
  PlaylistManager.load();
  IdleManager.load();

  // Start auto-refresh
  StatusManager.startAutoRefresh();
});

// Add fadeOut animation for toasts
const style = document.createElement("style");
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100%); }
    }
`;
document.head.appendChild(style);
