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

    def search_spotify(self, query, types=['track', 'artist', 'album'], limit=20):
        token = self.get_access_token()
        if not token:
            print("ERROR: No token obtained.")
            return {"tracks": [], "artists": [], "albums": []}

        url = f"{self.base_url}/search"
        params = {
            'q': query, 
            'type': ','.join(types), 
            'limit': limit,
        }
        headers = {'Authorization': f'Bearer {token}'}
        
        print(f"DEBUG: Hitting {url} with params {params}")
        response = requests.get(url, params=params, headers=headers)
        
        print(f"DEBUG: Status Code: {response.status_code}")
        if response.status_code != 200:
            print(f"DEBUG: Response Body: {response.text}")
            return {"tracks": [], "artists": [], "albums": []}

        data = response.json()
        print(f"DEBUG: Response received. Track items: {len(data.get('tracks', {}).get('items', []))}")
        
        results = {
            "tracks": [],
            "artists": [],
            "albums": []
        }

        # Parse Tracks
        for item in data.get('tracks', {}).get('items', []):
            results["tracks"].append(self._map_track(item))

        # Parse Artists
        for item in data.get('artists', {}).get('items', []):
            results["artists"].append({
                'id': item['id'],
                'name': item['name'],
                'genres': item.get('genres', []),
                'image_url': item['images'][0]['url'] if item.get('images') else None,
                'followers': item.get('followers', {}).get('total', 0),
                'type': 'artist'
            })

        # Parse Albums
        for item in data.get('albums', {}).get('items', []):
            results["albums"].append({
                'id': item['id'],
                'name': item['name'],
                'artist': item['artists'][0]['name'] if item.get('artists') else 'Unknown',
                'image_url': item['images'][0]['url'] if item.get('images') else None,
                'release_date': item.get('release_date'),
                'total_tracks': item.get('total_tracks', 0),
                'type': 'album'
            })

        return results

    def get_artist_top_tracks(self, artist_id, market='US'):
        token = self.get_access_token()
        if not token: return []
        
        response = requests.get(
            f"{self.base_url}/artists/{artist_id}/top-tracks",
            params={'market': market},
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if response.status_code == 200:
            return [self._map_track(item) for item in response.json().get('tracks', [])]
        return []

    def get_album_tracks(self, album_id):
        token = self.get_access_token()
        if not token: return []
        
        # Get album metadata to get the cover image for the tracks
        album_res = requests.get(
            f"{self.base_url}/albums/{album_id}",
            headers={'Authorization': f'Bearer {token}'}
        )
        album_data = album_res.json() if album_res.status_code == 200 else {}
        cover_image = album_data.get('images', [{}])[0].get('url', '')

        response = requests.get(
            f"{self.base_url}/albums/{album_id}/tracks",
            headers={'Authorization': f'Bearer {token}'}
        )
        
        if response.status_code == 200:
            tracks = []
            for item in response.json().get('items', []):
                # Standardize with cover image from album
                track = self._map_track(item)
                if not track['cover_image_url']:
                    track['cover_image_url'] = cover_image
                tracks.append(track)
            return tracks
        return []

    def _map_track(self, item):
        return {
            'id': item['id'],
            'title': item['name'],
            'artist': item['artists'][0]['name'] if item.get('artists') else 'Unknown',
            'cover_image_url': item['album']['images'][0]['url'] if item.get('album') and item['album'].get('images') else '',
            'file_url': item.get('preview_url'),
            'duration_ms': item['duration_ms'],
            'external_id': item['id'],
            'source': 'spotify'
        }
