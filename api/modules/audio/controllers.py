from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import models
from ...models import Audio

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_audios_view(request):
    """List all available audios, ordered by latest."""
    audios = Audio.objects.all().order_by('-created_at')[:100]
    data = []
    
    for a in audios:
        cover_image = a.cover_image_url
        file_url = request.build_absolute_uri(a.file_url.url) if a.file_url else None
        data.append({
            'id': a.id,
            'title': a.title,
            'artist': a.artist,
            'cover_image_url': cover_image,
            'file_url': file_url,
            'is_trending': a.is_trending,
            'duration_ms': a.duration_ms,
            'language': a.language,
            'created_at': a.created_at.isoformat() if a.created_at else None
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trending_audios_view(request):
    """List trending audios."""
    audios = Audio.objects.filter(is_trending=True).order_by('-created_at')[:50]
    data = []
    for a in audios:
        cover_image = a.cover_image_url
        file_url = request.build_absolute_uri(a.file_url.url) if a.file_url else None
        data.append({
            'id': a.id,
            'title': a.title,
            'artist': a.artist,
            'cover_image_url': cover_image,
            'file_url': file_url,
            'is_trending': True,
            'duration_ms': a.duration_ms,
            'created_at': a.created_at.isoformat() if a.created_at else None
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_audios_view(request):
    """Search for audios by title or artist."""
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response([])
    
    audios = Audio.objects.filter(
        models.Q(title__icontains=query) | 
        models.Q(artist__icontains=query)
    ).order_by('-is_trending', '-created_at')[:50]
    
    data = []
    for a in audios:
        cover_image = a.cover_image_url
        file_url = request.build_absolute_uri(a.file_url.url) if a.file_url else None
        data.append({
            'id': a.id,
            'title': a.title,
            'artist': a.artist,
            'cover_image_url': cover_image,
            'file_url': file_url,
            'is_trending': a.is_trending,
            'duration_ms': a.duration_ms,
            'created_at': a.created_at.isoformat() if a.created_at else None
        })
    return Response(data)
