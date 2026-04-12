import requests
import base64
from django.conf import settings
from django.core.cache import cache

class SpotifyClient:
    def __init__(self):
        self.client_id = getattr(settings, 'SPOTIFY_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'SPOTIFY_CLIENT_SECRET', '')
        self.token_url = "https://accounts.spotify.com/api/token"
        self.base_url = "https://api.spotify.com/v1"

    def get_access_token(self):
        token = cache.get('spotify_access_token')
        if token:
            return token

        if not self.client_id or not self.client_secret:
            return None

        auth_header = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode('ascii')
        ).decode('ascii')

        response = requests.post(
            self.token_url,
            data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {auth_header}'}
        )

        if response.status_code == 200:
            data = response.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)
            cache.set('spotify_access_token', access_token, expires_in - 60)
            return access_token
        
        return None

    def search_tracks(self, query, limit=20):
        token = self.get_access_token()
        if not token:
            return []

        response = requests.get(
            f"{self.base_url}/search",
            params={'q': query, 'type': 'track', 'limit': limit},
            headers={'Authorization': f'Bearer {token}'}
        )

        if response.status_code == 200:
            tracks = []
            data = response.json()
            for item in data.get('tracks', {}).get('items', []):
                # We need title, artist, coverURL, previewURL, and duration
                tracks.append({
                    'id': item['id'],
                    'title': item['name'],
                    'artist': item['artists'][0]['name'] if item['artists'] else 'Unknown',
                    'cover_image_url': item['album']['images'][0]['url'] if item['album']['images'] else '',
                    'file_url': item.get('preview_url'), # 30s preview
                    'duration_ms': item['duration_ms'],
                    'external_id': item['id'],
                    'source': 'spotify'
                })
            return tracks
        
        return []
