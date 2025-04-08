from functools import wraps
from flask import request, jsonify, current_app
from jose import jwt
import requests

# Cache JWKS
_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if not _jwks_cache:
        url = current_app.config['COGNITO_KEYS_URL']
        _jwks_cache = requests.get(url).json()
    return _jwks_cache

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get Bearer token from Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            config = current_app.config
            jwks = get_jwks()
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header['kid']

            key = next((k for k in jwks['keys'] if k['kid'] == kid), None)
            if key is None:
                raise Exception("Public key not found")

            decoded = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=config['CLIENT_ID'],
                issuer=f"https://cognito-idp.{config['COGNITO_REGION']}.amazonaws.com/{config['USER_POOL_ID']}"
            )

            request.user = decoded  # You can now access request.user in routes

        except Exception as e:
            print(f"Token validation failed: {e}")
            return jsonify({'message': 'Invalid or expired token'}), 401

        return f(*args, **kwargs)
    return decorated
