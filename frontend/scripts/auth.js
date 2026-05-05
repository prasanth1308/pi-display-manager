/**
 * Authentication Module
 * Handles user authentication and session management in the frontend
 */

const Auth = {
  currentUser: null,

  /**
   * Check if user is authenticated
   */
  async checkAuth() {
    try {
      const response = await fetch("/api/auth/status");
      const data = await response.json();

      if (data.authenticated) {
        this.currentUser = data.user;
        this.updateUserInfo();
        return true;
      } else {
        // Redirect to login if not authenticated
        window.location.href = "/login.html";
        return false;
      }
    } catch (error) {
      console.error("Auth check failed:", error);
      window.location.href = "/login.html";
      return false;
    }
  },

  /**
   * Update user info display
   */
  updateUserInfo() {
    const userInfoElement = document.getElementById("user-info");
    if (userInfoElement && this.currentUser) {
      userInfoElement.textContent = `👤 ${this.currentUser.username}`;
    }
  },

  /**
   * Logout user
   */
  async logout() {
    try {
      const response = await fetch("/api/auth/logout");
      const data = await response.json();

      if (data.status === "success") {
        window.location.href = "/login.html";
      }
    } catch (error) {
      console.error("Logout failed:", error);
      // Force redirect anyway
      window.location.href = "/login.html";
    }
  },

  /**
   * Initialize authentication
   */
  init() {
    // Setup logout button
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        if (confirm("Are you sure you want to logout?")) {
          this.logout();
        }
      });
    }
  },
};

// Check authentication when page loads
(async () => {
  const isAuthenticated = await Auth.checkAuth();
  if (isAuthenticated) {
    Auth.init();
  }
})();
