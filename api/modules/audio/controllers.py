from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets, status
from django.db import models
from ...models import Audio, FavoriteAudio
from ...serializers import AudioSerializer

class AudioViewSet(viewsets.ModelViewSet):
    queryset = Audio.objects.all().order_by('-created_at')
    serializer_class = AudioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search', '').strip()
        category = self.request.query_params.get('category', '').strip()
        language = self.request.query_params.get('language', '').strip()

        if search:
            qs = qs.filter(
                models.Q(title__icontains=search) | 
                models.Q(artist__icontains=search)
            )
        
        if category:
            if category.lower() == 'favorites':
                favorite_ids = FavoriteAudio.objects.filter(user=self.request.user).values_list('audio_id', flat=True)
                qs = qs.filter(id__in=favorite_ids)
            elif category.lower() == 'trending':
                qs = qs.filter(is_trending=True)
            else:
                qs = qs.filter(category__icontains=category)
        
        if language:
            qs = qs.filter(language__icontains=language)

        return qs[:100]

    @action(detail=False, methods=['post'])
    def toggle_favorite(self, request):
        audio_id = request.data.get('audio_id')
        external_id = request.data.get('external_id')
        track_data = request.data.get('track_data', {})
        
        audio = None
        # Try local ID first
        if audio_id:
            if isinstance(audio_id, int) or (isinstance(audio_id, str) and audio_id.isdigit()):
                audio = Audio.objects.filter(id=audio_id).first()
            else:
                # It might be an external ID passed as audio_id
                external_id = audio_id
        
        # Try external ID
        if not audio and external_id:
            audio = Audio.objects.filter(external_id=external_id).first()
            # Auto-import if track data is provided
            if not audio and track_data:
                audio = Audio.objects.create(
                    title=track_data.get('title', 'Unknown'),
                    artist=track_data.get('artist', 'Unknown'),
                    cover_image_url=track_data.get('cover_image_url', ''),
                    file_url=track_data.get('file_url', ''),
                    duration_ms=track_data.get('duration_ms', 0),
                    external_id=external_id,
                    created_by=request.user
                )

        if not audio:
            return Response({'error': 'Audio track not found in library or provided metadata is missing.'}, status=404)
        
        user = request.user
        fav, created = FavoriteAudio.objects.get_or_create(user=user, audio=audio)
        
        if not created:
            fav.delete()
            return Response({'status': 'unfavorited', 'is_favorite': False})
        
        return Response({'status': 'favorited', 'is_favorite': True})

    @action(detail=False, methods=['get'])
    def spotify_search(self, request):
        query = request.query_params.get('q', '').strip()
        
        if not query:
            query = "Trending"
            
        from .spotify_service import SpotifyClient
        client = SpotifyClient()
        results = client.search_spotify(query)
        
        return Response(results)

    @action(detail=False, methods=['get'])
    def spotify_artist_tracks(self, request):
        artist_id = request.query_params.get('id')
        if not artist_id:
            return Response({'error': 'id required'}, status=400)
            
        from .spotify_service import SpotifyClient
        client = SpotifyClient()
        tracks = client.get_artist_top_tracks(artist_id)
        return Response(tracks)

    @action(detail=False, methods=['get'])
    def saavn_search(self, request):
        query = request.query_params.get('q', '').strip()
        
        from .saavn_service import SaavnClient
        client = SaavnClient()
        
        if not query:
            results = client.get_top_trending()
        else:
            results = client.search(query)
            
        return Response(results)

    @action(detail=False, methods=['post'])
    def import_spotify_track(self, request):
        track_data = request.data
        external_id = track_data.get('external_id')
        
        if not external_id:
            return Response({'error': 'external_id required'}, status=400)
            
        # Check if already exists
        audio = Audio.objects.filter(external_id=external_id).first()
        if not audio:
            audio = Audio.objects.create(
                title=track_data.get('title', 'Unknown'),
                artist=track_data.get('artist', 'Unknown'),
                cover_image_url=track_data.get('cover_image_url', ''),
                file_url=track_data.get('file_url', ''),
                duration_ms=track_data.get('duration_ms', 0),
                external_id=external_id,
                created_by=request.user
            )
        
        serializer = AudioSerializer(audio, context={'request': request})
        return Response(serializer.data, status=201)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_audios_view(request):
    """Fallback for old endpoints if needed"""
    qs = Audio.objects.all().order_by('-is_trending', '-created_at')[:100]
    serializer = AudioSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_audios_view(request):
    """Fallback for old search endpoint"""
    query = request.query_params.get('q', request.query_params.get('search', '')).strip()
    qs = Audio.objects.filter(
        models.Q(title__icontains=query) | models.Q(artist__icontains=query)
    ).order_by('-is_trending', '-created_at')[:50]
    serializer = AudioSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data)
