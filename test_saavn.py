import os
import django
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.modules.audio.saavn_service import SaavnClient

def test_saavn():
    print("--- JioSaavn Diagnostic ---")
    client = SaavnClient()
    
    # 1. Test Search
    query = "Tum Hi Ho"
    print(f"Searching for '{query}'...")
    results = client.search(query, limit=5)
    
    if not results:
        print("FAILED: No search results returned.")
        return
        
    print(f"SUCCESS: Found {len(results)} results.")
    
    # 2. Test First Result
    first = results[0]
    print(f"\nTop Result: {first['title']} by {first['artist']}")
    print(f"Direct URL (Decrypted): {first['file_url']}")
    
    if first['file_url'] and first['file_url'].startswith('http'):
        print("SUCCESS: Media URL successfully decrypted.")
    else:
        print("FAILED: Media URL decryption error or missing.")

    # 3. Test Trending
    print("\nFetching Trending Songs...")
    trending = client.get_top_trending()
    if trending:
        print(f"SUCCESS: Found {len(trending)} trending songs.")
        for i, track in enumerate(trending[:3]):
            print(f" {i+1}. {track['title']} by {track['artist']}")
    else:
        print("FAILED: No trending songs found.")

if __name__ == "__main__":
    test_saavn()
