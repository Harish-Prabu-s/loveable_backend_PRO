from django.core.cache import cache
from api.models import MusicTrack, MusicClipSelection, UserMusicFavorite
from .music_providers import MusicProviderFactory

class MusicService:
    @staticmethod
    def search_music(query, provider_name='jiosaavn', limit=20):
        """
        Searches music with a caching layer.
        """
        cache_key = f"music_search_{provider_name}_{query}_{limit}"
        cached_results = cache.get(cache_key)
        if cached_results:
            return cached_results

        provider = MusicProviderFactory.get_provider(provider_name)
        if not provider:
            return []

        results = provider.search_tracks(query, limit=limit)
        
        # Save results to local cache table (MusicTrack) for performance/persistence
        for track_data in results:
            MusicService._upsert_track(track_data)
        
        # Cache the search result list for 1 hour
        cache.set(cache_key, results, 3600)
        return results

    @staticmethod
    def get_track(provider_track_id, provider_name='jiosaavn'):
        """
        Fetches track details from DB or Provider.
        """
        # 1. Try DB first
        track = MusicTrack.objects.filter(provider_name=provider_name, provider_track_id=provider_track_id).first()
        if track:
            return track

        # 2. Try Provider
        provider = MusicProviderFactory.get_provider(provider_name)
        if provider:
            track_data = provider.get_track_details(provider_track_id)
            if track_data:
                return MusicService._upsert_track(track_data)
        
        return None

    @staticmethod
    def validate_clip_range(provider_track_id, start_sec, end_sec, provider_name='jiosaavn'):
        """
        Validates the 30-second clip range using metadata.
        """
        track = MusicService.get_track(provider_track_id, provider_name)
        if not track:
            return False, "Track not found"

        if start_sec < 0:
            return False, "Start time cannot be negative"
        
        duration = end_sec - start_sec
        if duration > 30.5:
            return False, "Clip duration cannot exceed 30 seconds"
        
        if end_sec > track.duration:
            return False, f"Clip ends at {end_sec}s but track only last {track.duration}s"
            
        return True, None

    @staticmethod
    def attach_clip_to_draft(user, draft, provider_track_id, start_sec, end_sec, provider_name='jiosaavn'):
        valid, error = MusicService.validate_clip_range(provider_track_id, start_sec, end_sec, provider_name)
        if not valid:
            raise ValueError(error)
            
        track = MusicService.get_track(provider_track_id, provider_name)
            
        selection, created = MusicClipSelection.objects.update_or_create(
            draft=draft,
            defaults={
                'user': user,
                'provider_name': provider_name,
                'provider_track_id': provider_track_id,
                'track': track,
                'clip_start_seconds': start_sec,
                'clip_end_seconds': end_sec,
                'clip_duration': end_sec - start_sec
            }
        )
        return selection

    @staticmethod
    def _upsert_track(data):
        """
        Internal helper to update or create a MusicTrack from normalized data.
        """
        track, created = MusicTrack.objects.update_or_create(
            provider_name=data['provider_name'],
            provider_track_id=data['provider_track_id'],
            defaults={
                'title': data['title'],
                'artist_name': data['artist_name'],
                'album_name': data.get('album_name'),
                'duration': data['duration_seconds'],
                'preview_url': data.get('preview_url'),
                'cover_image_url': data.get('cover_image_url'),
                'language': data.get('language'),
                'genre': data.get('genre'),
                'raw_provider_payload_json': data.get('raw_provider_payload_json', {})
            }
        )
        return track
