// Biz Bridge - Homepage JavaScript (Essential Only)

class BizBridge {
    constructor() {
        this.currentUser = null;
        this.init();
    }

    init() {
        this.checkAuthStatus();
        this.setupLogoutHandlers();
    }

    // Check if user is logged in
    async checkAuthStatus() {
        try {
            const token = localStorage.getItem('authToken');
            if (!token) {
                this.showGuestUI();
                return;
            }

            // Call your backend API to verify token
            const response = await fetch('/api/auth/verify', {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.currentUser = data.user;
                this.showAuthenticatedUI(data.user);
            } else {
                this.showGuestUI();
                localStorage.removeItem('authToken');
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            this.showGuestUI();
        }
    }

    // Show logged in user interface
    showAuthenticatedUI(user) {
        // Hide guest buttons
        document.getElementById('guest-buttons')?.classList.add('hidden');
        document.getElementById('mobile-guest-buttons')?.classList.add('hidden');

        // Show user menu
        document.getElementById('user-menu')?.classList.remove('hidden');
        document.getElementById('mobile-user-menu')?.classList.remove('hidden');

        // Update user name
        const userName = user.name || user.email || 'User';
        document.getElementById('user-name').textContent = userName;
        document.getElementById('mobile-user-name').textContent = userName;
    }

    // Show guest user interface
    showGuestUI() {
        // Show guest buttons
        document.getElementById('guest-buttons')?.classList.remove('hidden');
        document.getElementById('mobile-guest-buttons')?.classList.remove('hidden');

        // Hide user menu
        document.getElementById('user-menu')?.classList.add('hidden');
        document.getElementById('mobile-user-menu')?.classList.add('hidden');
    }

    // Setup logout button handlers
    setupLogoutHandlers() {
        document.getElementById('logout-btn')?.addEventListener('click', () => this.logout());
        document.getElementById('mobile-logout-btn')?.addEventListener('click', () => this.logout());
    }

    // Handle user logout
    async logout() {
        try {
            const token = localStorage.getItem('authToken');
            if (token) {
                // Call backend logout API
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
            }

            // Clear local storage
            localStorage.removeItem('authToken');
            localStorage.removeItem('userData');
            
            // Update UI
            this.currentUser = null;
            this.showGuestUI();
            
            // Show success message
            this.showNotification('Logged out successfully', 'success');
            
            // Redirect to home after short delay
            setTimeout(() => {
                window.location.href = 'home.html';
            }, 1500);
        } catch (error) {
            console.error('Logout failed:', error);
            this.showNotification('Logout failed', 'error');
            // Still clear local data and redirect
            localStorage.clear();
            setTimeout(() => {
                window.location.href = 'home.html';
            }, 2000);
        }
    }

    // Simple notification system
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';
        
        notification.className = `fixed top-4 right-4 z-50 p-4 rounded-lg text-white ${bgColor} shadow-lg`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Mobile menu toggle (simple)
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    const menuIcon = document.getElementById('menu-icon');
    const closeIcon = document.getElementById('close-icon');
    
    menu.classList.toggle('open');
    menuIcon.classList.toggle('hidden');
    closeIcon.classList.toggle('hidden');
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new BizBridge();
    
    // Setup mobile menu button
    document.getElementById('mobile-menu-button')?.addEventListener('click', toggleMobileMenu);
});