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
        
        # 1. Check if it's an S3 URL for our bucket first
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if bucket_name and f"/{bucket_name}/" in relative_path:
            path_without_query = relative_path.split('?')[0]
            idx = path_without_query.find(f"/{bucket_name}/")
            if idx != -1:
                return path_without_query[idx + len(f"/{bucket_name}/"):]

        # 2. Strip the MEDIA_URL part if it exists at the start
        media_url = getattr(settings, 'MEDIA_URL', '').strip('/')
        if media_url:
            if not relative_path.startswith('/'):
                relative_path = '/' + relative_path

            if relative_path.startswith(f'/{media_url}/'):
                return relative_path[len(f'/{media_url}/'):]
            elif relative_path.startswith(f'{media_url}/'):
                return relative_path[len(f'{media_url}/'):]
                
        # 3. If MEDIA_URL is just '/', strip the leading slash but discard query params
        path_without_query = relative_path.split('?')[0]
        return path_without_query.lstrip('/')

    return path_str

def _is_s3_storage():
    """Check if the default storage backend is S3."""
    try:
        storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
        return 's3' in storage_backend.lower() or 'boto' in storage_backend.lower()
    except Exception:
        return False


def get_absolute_media_url(path, request=None):
    """
    Safely constructs an absolute URL for a media file.
    - When S3 storage is active: calls .url on the field to get the presigned S3 URL directly.
    - When local storage: builds absolute URI using the request or SERVER_URL.
    - Handles already-absolute external URLs (Spotify, JioSaavn, etc.) transparently.
    """
    if not path:
        return None

    # ── S3 storage: let django-storages generate the correct presigned URL ──
    if _is_s3_storage():
        # If it's a FileField/ImageField object, call .url to get the S3 presigned URL
        if hasattr(path, 'url'):
            try:
                url = path.url
                if url:
                    return url
            except Exception:
                pass

        path_str = str(path)

        # Already an absolute S3/external URL — return as-is
        if path_str.startswith('http://') or path_str.startswith('https://'):
            return path_str

        # It's a relative path stored in the DB — generate S3 URL via default_storage
        if path_str:
            try:
                from django.core.files.storage import default_storage
                return default_storage.url(path_str.lstrip('/'))
            except Exception:
                pass

        return path_str

    # ── Local storage fallback (original logic) ──────────────────────────────
    path_str = str(path)
    is_production = os.environ.get('ENV') == 'production'

    # Handle FileField/ImageField objects
    if hasattr(path, 'url'):
        try:
            path_str = path.url
        except Exception:
            pass

    # Handle already absolute URLs
    if path_str.startswith('http://') or path_str.startswith('https://'):
        match = re.search(r'https?://[^/]+/(https?://.*)', path_str)
        if match:
            return match.group(1)

        if request:
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

        if is_production and path_str.startswith('http://') and not any(
                h in path_str for h in ['localhost', '127.0.0.1', '10.0.2.2']):
            return path_str.replace('http://', 'https://', 1)
        return path_str

    # Relative path
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

    server_url = os.environ.get('SERVER_URL', '').rstrip('/')
    if server_url:
        base_match = re.match(r'(https?://[^/]+)', server_url)
        if base_match:
            base_url = base_match.group(1)
            return f"{base_url}{relative_url}"

    return relative_url
