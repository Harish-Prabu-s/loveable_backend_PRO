import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.modules.audio.spotify_service import SpotifyClient

def diagnostic():
    client_id = getattr(settings, 'SPOTIFY_CLIENT_ID', '')
    client_secret = getattr(settings, 'SPOTIFY_CLIENT_SECRET', '')
    
    print(f"--- Spotify Diagnostic ---")
    print(f"Client ID present: {'Yes' if client_id else 'No'}")
    print(f"Client Secret present: {'Yes' if client_secret else 'No'}")
    
    if not client_id or not client_secret:
        print("\nERROR: Spotify credentials are missing in settings.py or .env file.")
        print("Please check your .env file and ensure values are added.")
        return

    client = SpotifyClient()
    print("\nAttempting to get access token...")
    token = client.get_access_token()
    
    if token:
        print("SUCCESS: Got access token.")
        print("Attempting to search for 'Top Hits'...")
        results = client.search_spotify("Top Hits", limit=3)
        print(f"Found {len(results.get('tracks', []))} tracks.")
        print(f"Found {len(results.get('artists', []))} artists.")
        print(f"Found {len(results.get('albums', []))} albums.")
        
        tracks = results.get('tracks', [])
        if tracks:
            print("\nTop Tracks:")
            for i, track in enumerate(tracks[:3]):
                print(f" {i+1}. {track['title']} by {track['artist']}")
    else:
        print("FAILED: Could not get access token. Check your credentials.")

if __name__ == "__main__":
    diagnostic()
