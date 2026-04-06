from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...models import Audio

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_audios_view(request):
    audios = Audio.objects.all().order_by('-created_at')[:50]
    data = []
    
    # We need full URL for audio files
    for a in audios:
        cover_image = a.cover_image_url
        file_url = request.build_absolute_uri(a.file_url.url) if a.file_url else None
        data.append({
            'id': a.id,
            'title': a.title,
            'artist': a.artist,
            'cover_image_url': cover_image,
            'file_url': file_url,
            'created_at': a.created_at.isoformat() if a.created_at else None
        })
    return Response(data)
