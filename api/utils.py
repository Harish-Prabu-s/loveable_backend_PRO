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
        # If we have a request, we REROUTE the absolute URL to the current requested host
        # ONLY if it appears to be a local media file (starts with MEDIA_URL)
        if request:
            match = re.search(r'https?://[^/]+(/.*)', path_str)
            if match:
                relative_url = match.group(1)
                
                # 🛑 CRITICAL FIX: If the "relative" part is actually another absolute URL (doubled-up URL)
                # This happens if a past bug prefixed an external URL with our domain.
                # Example: https://loveable.sbs/https://aac.saavncdn.com/...
                inner_match = re.search(r'(https?://.*)', relative_url)
                if inner_match:
                    return inner_match.group(1)

                media_url = settings.MEDIA_URL.rstrip('/')
                
                # Check if it's a known local/internal domain
                is_internal_domain = any(h in path_str for h in ['localhost', '127.0.0.1', '10.0.2.2', '192.168.', 'loveable.sbs'])
                
                # We only reroute if it's an internal domain AND it's in the media folder
                if is_internal_domain and relative_url.startswith(media_url + '/'):
                    absolute_url = request.build_absolute_uri(relative_url)
                    if (is_production or request.is_secure()) and absolute_url.startswith('http://'):
                        return absolute_url.replace('http://', 'https://', 1)
                    return absolute_url

        # For genuine external URLs (like JioSaavn or Spotify), just return as is
        if is_production and path_str.startswith('http://') and not any(
                h in path_str for h in ['localhost', '127.0.0.1', '10.0.2.2']):
            return path_str.replace('http://', 'https://', 1)
        return path_str

    # Standardize relative path
    clean_path = path_str.lstrip('/')

    # Prefix with MEDIA_URL if not already present
    media_url = settings.MEDIA_URL.rstrip('/')
    media_url_clean = media_url.lstrip('/')

    if not clean_path.startswith(media_url_clean):
        # Use simple join to avoid double slashes
        relative_url = f"/{media_url_clean}/{clean_path}"
    else:
        relative_url = f"/{clean_path}"

    if request:
        absolute_url = request.build_absolute_uri(relative_url)
        # Ensure the generated absolute URI matches the secure state
        if (is_production or request.is_secure()) and absolute_url.startswith('http://'):
            return absolute_url.replace('http://', 'https://', 1)
        return absolute_url

    return relative_url
