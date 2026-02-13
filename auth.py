"""
Auth utilities for Flask routes.

Verifies Supabase JWTs using the JWT secret (HS256).
Checks admin role from the profiles table using a service role client
(bypasses RLS).
"""

import functools
import os

import jwt
from flask import request, jsonify, g  # noqa: F401


# JWT secret from Supabase dashboard (Settings > API > JWT Secret)
_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# Service role client for profiles lookup (bypasses RLS)
_service_client = None

def _get_service_client():
    """Lazy-init a Supabase client using the service role key."""
    global _service_client
    if _service_client is None:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return None
        _service_client = create_client(url, key)
    return _service_client


def get_current_user():
    """
    Extract and verify the JWT from Authorization header.
    Returns dict with {id, email, role} or None if no valid token.
    Caches result in flask.g for the duration of the request.
    """
    if hasattr(g, "_current_user"):
        return g._current_user

    g._current_user = None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]

    if not _JWT_SECRET:
        # No JWT secret configured — cannot verify tokens
        return None

    try:
        payload = jwt.decode(
            token,
            _JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    user_id = payload.get("sub")
    email = payload.get("email", "")

    if not user_id:
        return None

    # Look up role from profiles table (service role bypasses RLS)
    client = _get_service_client()
    if not client:
        g._current_user = {"id": user_id, "email": email, "role": "user"}
        return g._current_user

    result = client.table("profiles").select("role").eq("id", user_id).execute()

    if not result.data:
        role = "user"  # No profile row yet (trigger race condition edge case)
    else:
        role = result.data[0].get("role", "user")

    g._current_user = {"id": user_id, "email": email, "role": role}
    return g._current_user


def require_admin(f):
    """
    Decorator: require a valid JWT with admin role.
    Returns 401 if no valid token, 403 if not admin.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "Authentication required"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated
