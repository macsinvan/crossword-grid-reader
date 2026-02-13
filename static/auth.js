/**
 * Auth Module — Supabase Google OAuth
 *
 * Manages authentication state and provides the auth token
 * for admin API calls. Supabase JS client handles token
 * storage in localStorage automatically.
 */

const AuthModule = (function() {
    let supabaseClient = null;
    let currentUser = null;   // {email, role} or null

    function init() {
        const url = window.__SUPABASE_URL;
        const key = window.__SUPABASE_ANON_KEY;

        if (!url || !key || !window.supabase) {
            // Auth not configured — show no login button, admin features stay hidden
            return;
        }

        supabaseClient = window.supabase.createClient(url, key);

        // Listen for auth state changes (login, logout, token refresh)
        supabaseClient.auth.onAuthStateChange(async (event, session) => {
            if (session) {
                await fetchUserRole(session.access_token);
            } else {
                currentUser = null;
                updateUI();
            }
        });

        // Check initial session state
        supabaseClient.auth.getSession().then(({ data: { session } }) => {
            if (session) {
                fetchUserRole(session.access_token);
            } else {
                // Show login button for unauthenticated users
                const loginBtn = document.getElementById('auth-login-btn');
                if (loginBtn) loginBtn.style.display = '';
                updateUI();
            }
        });

        // Bind UI events
        const loginBtn = document.getElementById('auth-login-btn');
        const logoutBtn = document.getElementById('auth-logout-btn');
        if (loginBtn) loginBtn.addEventListener('click', signIn);
        if (logoutBtn) logoutBtn.addEventListener('click', signOut);
    }

    async function fetchUserRole(accessToken) {
        try {
            const resp = await fetch('/auth/me', {
                headers: { 'Authorization': 'Bearer ' + accessToken }
            });
            const data = await resp.json();
            currentUser = data.user;  // {email, role} or null
        } catch (err) {
            console.error('Failed to fetch user role:', err);
            currentUser = null;
        }
        updateUI();
    }

    async function signIn() {
        if (!supabaseClient) return;
        const { error } = await supabaseClient.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: window.location.origin
            }
        });
        if (error) console.error('Sign in error:', error);
    }

    async function signOut() {
        if (!supabaseClient) return;
        const { error } = await supabaseClient.auth.signOut();
        if (error) console.error('Sign out error:', error);
        currentUser = null;
        updateUI();
    }

    function updateUI() {
        const loginBtn = document.getElementById('auth-login-btn');
        const userInfo = document.getElementById('auth-user-info');
        const emailEl = document.getElementById('auth-user-email');
        const importTab = document.querySelector('[data-tab="import"]');
        const deleteButtons = document.querySelectorAll('.delete-btn');

        if (currentUser) {
            // Signed in — show user info, hide login button
            if (loginBtn) loginBtn.style.display = 'none';
            if (userInfo) userInfo.style.display = 'flex';
            if (emailEl) emailEl.textContent = currentUser.email;

            // Show admin UI only for admins
            const isAdmin = currentUser.role === 'admin';
            if (importTab) importTab.style.display = isAdmin ? '' : 'none';
            deleteButtons.forEach(btn => btn.style.display = isAdmin ? '' : 'none');
        } else {
            // Not signed in — show login button, hide admin UI
            if (loginBtn && supabaseClient) loginBtn.style.display = '';
            if (userInfo) userInfo.style.display = 'none';
            if (importTab) importTab.style.display = 'none';
            deleteButtons.forEach(btn => btn.style.display = 'none');
        }
    }

    /** Get the current access token for API calls, or null. */
    async function getAccessToken() {
        if (!supabaseClient) return null;
        const { data: { session } } = await supabaseClient.auth.getSession();
        return session?.access_token || null;
    }

    /** Check if the current user is an admin. */
    function isAdmin() {
        return currentUser?.role === 'admin';
    }

    return { init, getAccessToken, isAdmin, updateUI };
})();

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    AuthModule.init();
});
