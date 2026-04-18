import requests
import base64
import html
from Crypto.Cipher import DES

class SaavnClient:
    def __init__(self):
        self.base_url = "https://www.jiosaavn.com/api.php"
        self.des_key = b'38346591'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'application/json, text/plain, */*'
        }

    def search(self, query, limit=20):
        """
        Searches for tracks using the internal search.getResults call.
        """
        params = {
            '__call': 'search.getResults',
            '_format': 'json',
            '_marker': '0',
            'api_version': '4',
            'ctx': 'web6dot0',
            'q': query,
            'n': limit
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                return [self._map_track(item) for item in results]
        except Exception as e:
            print(f"[Saavn] Search failed: {e}")
            
        return []

    def get_top_trending(self):
        """
        Fetches trending songs (equivalent to Spotify Top Hits).
        """
        params = {
            '__call': 'content.getTrending',
            '_format': 'json',
            '_marker': '0',
            'api_version': '4',
            'ctx': 'web6dot0',
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                # Trending data is often in a list directly or under results
                items = data if isinstance(data, list) else data.get('results', [])
                return [self._map_track(item) for item in items if item.get('type') == 'song']
        except Exception as e:
            print(f"[Saavn] Trending fetch failed: {e}")
            
        return []

    def decrypt_url(self, enc_url):
        """
        Decrypts the media URL using DES-ECB.
        """
        if not enc_url:
            return None
            
        try:
            cipher = DES.new(self.des_key, DES.MODE_ECB)
            # Base64 decode
            enc_data = base64.b64decode(enc_url.strip())
            # Decrypt
            dec_data = cipher.decrypt(enc_data)
            
            # Unpad PKCS5
            padding_len = dec_data[-1]
            if padding_len < 1 or padding_len > 8:
                return dec_data.decode('utf-8').strip()
                
            final_url = dec_data[:-padding_len].decode('utf-8').strip()
            
            # Convert to high quality (320kbps) if available
            # Standard formats: _96_v4.mp4, _160_v4.mp4, _320_v4.mp4
            final_url = final_url.replace('_96_v4.mp4', '_320.mp4')
            final_url = final_url.replace('_96.mp4', '_320.mp4')
            
            return final_url
        except Exception as e:
            print(f"[Saavn] Decryption failed: {e}")
            return None

    def get_lyrics(self, track_id):
        """
        Fetches lyrics for a specific track ID.
        """
        if not track_id:
            return None
            
        params = {
            '__call': 'lyrics.getLyrics',
            '_format': 'json',
            '_marker': '0',
            'api_version': '4',
            'ctx': 'web6dot0',
            'lyrics_id': track_id
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                lyrics_html = data.get('lyrics', '')
                # Clean up HTML if present
                if lyrics_html:
                    return html.unescape(lyrics_html).replace('<br />', '\n').strip()
        except Exception as e:
            print(f"[Saavn] Lyrics fetch failed: {e}")
            
        return None

    def _map_track(self, item):
        """
        Maps Saavn JSON response to our unified AudioTrack interface.
        """
        # Decode HTML entities in titles and artists
        title = html.unescape(item.get('song', item.get('title', 'Unknown')))
        artist = html.unescape(item.get('primary_artists', item.get('singers', 'Unknown')))
        
        # Format image URL (Saavn usually provides 150x150, we want 500x500)
        image_url = item.get('image', '')
        if '150x150' in image_url:
            image_url = image_url.replace('150x150', '500x500')
        
        encrypted_media_url = item.get('more_info', {}).get('encrypted_media_url')
        
        return {
            'id': item.get('id'),
            'title': title,
            'artist': artist,
            'cover_image_url': image_url,
            'file_url': self.decrypt_url(encrypted_media_url),
            'duration_ms': int(item.get('more_info', {}).get('duration', 0)) * 1000,
            'source': 'saavn',
            'is_favorite': False
        }
