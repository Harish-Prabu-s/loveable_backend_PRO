import requests
import html
from abc import ABC, abstractmethod
from api.modules.audio.saavn_service import SaavnClient

class BaseMusicProvider(ABC):
    @abstractmethod
    def search_tracks(self, query, limit=20):
        pass

    @abstractmethod
    def get_track_details(self, track_id):
        pass

    @abstractmethod
    def get_trending_tracks(self):
        pass

class JioSaavnMusicProvider(BaseMusicProvider):
    def __init__(self):
        self.client = SaavnClient()

    def search_tracks(self, query, limit=20):
        tracks = self.client.search(query, limit=limit)
        return [self._normalize(t) for t in tracks]

    def get_track_details(self, track_id):
        # JioSaavn API usually requires a call for search result details if not provided
        # But for now, we'll assume we fetch via ID if needed.
        # Note: SaavnClient.search currently returns enough info for normalization.
        params = {
            '__call': 'song.getDetails',
            'pids': track_id,
            '_format': 'json',
            'api_version': '4',
            'ctx': 'web6dot0'
        }
        try:
            response = requests.get(self.client.base_url, params=params, headers=self.client.headers)
            if response.status_code == 200:
                data = response.json()
                songs = data.get('songs', []) or data.get(track_id, [])
                if isinstance(songs, list) and len(songs) > 0:
                    return self._normalize(self.client._map_track(songs[0]))
        except Exception:
            pass
        return None

    def get_trending_tracks(self):
        tracks = self.client.get_top_trending()
        return [self._normalize(t) for t in tracks]

    def _normalize(self, saavn_track):
        """
        Maps Saavn internal format to our Normalized Music Schema.
        """
        return {
            'provider_name': 'jiosaavn',
            'provider_track_id': str(saavn_track.get('id')),
            'title': saavn_track.get('title'),
            'artist_name': saavn_track.get('artist'),
            'album_name': saavn_track.get('album', 'Unknown'),
            'duration_seconds': saavn_track.get('duration_ms', 0) // 1000,
            'cover_image_url': saavn_track.get('cover_image_url'),
            'preview_url': saavn_track.get('file_url'),
            'language': saavn_track.get('language', 'Unknown'),
            'genre': saavn_track.get('genre', 'Pop'),
            'raw_provider_payload_json': saavn_track
        }

class MusicProviderFactory:
    _providers = {
        'jiosaavn': JioSaavnMusicProvider()
    }

    @classmethod
    def get_provider(cls, name='jiosaavn'):
        return cls._providers.get(name)
