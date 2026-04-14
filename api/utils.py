import os
import re
from django.conf import settings


def strip_base_url(path):
    """
    Removes the absolute part of a URL (protocol, host, port) 
    to return just the relative media path for storage.
    Example: http://127.0.0.1:8001/media/stories/x.jpg -> stories/x.jpg
    """
    if not path:
        return None

    path_str = str(path)
    # Remove protocol and domain
    # This will match http://localhost:8000/media/something or /media/something
    match = re.search(r'(?:https?://[^/]+)?(/.*)', path_str)
    if match:
        relative_path = match.group(1)
        # Strip the MEDIA_URL part if it exists at the start
        media_url = settings.MEDIA_URL.strip('/')
        # Ensure we have a leading slash if not present
        if not relative_path.startswith('/'):
            relative_path = '/' + relative_path

        # Standard clean way to get the path inside media
        if relative_path.startswith(f'/{media_url}/'):
            return relative_path[len(f'/{media_url}/'):]
        elif relative_path.startswith(f'{media_url}/'):
            return relative_path[len(f'{media_url}/'):]

    return path_str


def get_absolute_media_url(path, request=None):
    """
    Safely constructs an absolute URL for a media file.
    - Robustly handles cases where path is already absolute (possibly with wrong host/IP).
    - If path is relative → prepends MEDIA_URL and builds absolute URI using request.
    """
    if not path:
        return None

    path_str = str(path)
    is_production = os.environ.get('ENV') == 'production'

    # 🔗 Handle already absolute URLs
    if path_str.startswith('http://') or path_str.startswith('https://'):
        # If it's a doubled up URL (e.g. domain.com/https://external.com)
        # We strip the local part and return the external part.
        match = re.search(r'https?://[^/]+/(https?://.*)', path_str)
        if match:
            return match.group(1)

        # If we have a request, check if it's a known internal domain that needs rerouting
        if request:
            # Check if it's a known local/internal domain
            is_internal_domain = any(h in path_str for h in ['localhost', '127.0.0.1', '10.0.2.2', '192.168.', 'loveable.sbs', '72.62.195.63'])
            
            if is_internal_domain:
                match = re.search(r'https?://[^/]+(/.*)', path_str)
                if match:
                    relative_url = match.group(1)
                    media_url = settings.MEDIA_URL.rstrip('/')
                    if relative_url.startswith(media_url + '/'):
                        absolute_url = request.build_absolute_uri(relative_url)
                        if (is_production or request.is_secure()) and absolute_url.startswith('http://'):
                            return absolute_url.replace('http://', 'https://', 1)
                        return absolute_url

        # For genuine external URLs (like JioSaavn or Spotify), just return as is
        # but upgrade to https in production if needed
        if is_production and path_str.startswith('http://') and not any(
                h in path_str for h in ['localhost', '127.0.0.1', '10.0.2.2']):
            return path_str.replace('http://', 'https://', 1)
        return path_str

    # Standardize relative path
    clean_path = path_str.lstrip('/')
    media_url = settings.MEDIA_URL.rstrip('/')
    media_url_clean = media_url.lstrip('/')

    if not clean_path.startswith(media_url_clean):
        relative_url = f"/{media_url_clean}/{clean_path}"
    else:
        relative_url = f"/{clean_path}"

    if request:
        absolute_url = request.build_absolute_uri(relative_url)
        if (is_production or request.is_secure()) and absolute_url.startswith('http://'):
            return absolute_url.replace('http://', 'https://', 1)
        return absolute_url

    # FALLBACK: If no request is provided, we try to use the SERVER_URL from environment
    # or just return the relative URL if we can't determine the host.
    server_url = os.environ.get('SERVER_URL', '').rstrip('/')
    if server_url:
        # SERVER_URL usually ends in /api/, so we might need to get the root
        base_match = re.match(r'(https?://[^/]+)', server_url)
        if base_match:
            base_url = base_match.group(1)
            return f"{base_url}{relative_url}"

    return relative_url
