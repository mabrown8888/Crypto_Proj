// JWT token management utilities

const TOKEN_KEY = 'token';
const USERNAME_KEY = 'username';

export const authUtils = {
  // Store token in localStorage
  setToken: (token) => {
    localStorage.setItem(TOKEN_KEY, token);
  },

  // Get token from localStorage
  getToken: () => {
    return localStorage.getItem(TOKEN_KEY);
  },

  // Remove token from localStorage
  removeToken: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
  },

  // Store username
  setUsername: (username) => {
    localStorage.setItem(USERNAME_KEY, username);
  },

  // Get username
  getUsername: () => {
    return localStorage.getItem(USERNAME_KEY);
  },

  // Check if user is authenticated
  isAuthenticated: () => {
    const token = authUtils.getToken();
    if (!token) return false;
    
    try {
      // Check if token is expired (simple check)
      const payload = JSON.parse(atob(token.split('.')[1]));
      const currentTime = Date.now() / 1000;
      return payload.exp > currentTime;
    } catch (error) {
      return false;
    }
  },

  // Get authorization header for API calls
  getAuthHeader: () => {
    const token = authUtils.getToken();
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  },

  // Logout user
  logout: () => {
    authUtils.removeToken();
    window.location.reload(); // Refresh to show login form
  },

  // Refresh token
  refreshToken: async () => {
    try {
      const response = await fetch('http://localhost:5001/api/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authUtils.getAuthHeader()
        }
      });

      const data = await response.json();
      
      if (data.success) {
        authUtils.setToken(data.token);
        return true;
      } else {
        authUtils.logout();
        return false;
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
      authUtils.logout();
      return false;
    }
  },

  // Make authenticated API call
  authenticatedFetch: async (url, options = {}) => {
    const authHeaders = authUtils.getAuthHeader();
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
        ...options.headers
      }
    });

    // If unauthorized, try to refresh token once
    if (response.status === 401) {
      const refreshed = await authUtils.refreshToken();
      if (refreshed) {
        // Retry the original request with new token
        const newAuthHeaders = authUtils.getAuthHeader();
        return fetch(url, {
          ...options,
          headers: {
            'Content-Type': 'application/json',
            ...newAuthHeaders,
            ...options.headers
          }
        });
      }
    }

    return response;
  }
};

// Token expiration check and auto-refresh
export const setupTokenRefresh = () => {
  const checkTokenExpiration = () => {
    if (authUtils.isAuthenticated()) {
      const token = authUtils.getToken();
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const currentTime = Date.now() / 1000;
        const timeUntilExpiry = payload.exp - currentTime;
        
        // Refresh token if it expires in less than 5 minutes
        if (timeUntilExpiry < 300) {
          authUtils.refreshToken();
        }
      } catch (error) {
        console.error('Error checking token expiration:', error);
      }
    }
  };

  // Check token expiration every 5 minutes
  setInterval(checkTokenExpiration, 5 * 60 * 1000);
  
  // Check immediately on setup
  checkTokenExpiration();
};