from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.conf import settings
import os
import uuid

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_file_view(request):
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)
    
    file_obj = request.FILES['file']
    file_type = request.data.get('type', 'misc')
    
    # 1. Size Validation (50MB limit)
    MAX_SIZE = 50 * 1024 * 1024
    if file_obj.size > MAX_SIZE:
        return Response({'error': 'File too large (Max 50MB)'}, status=413)

    # 2. Extension Validation
    ext = os.path.splitext(file_obj.name)[1].lower()
    allowed_extensions = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
        'video': ['.mp4', '.mov', '.avi', '.mkv'],
        'voice': ['.m4a', '.wav', '.mp3', '.aac'],
        'audio': ['.mp3', '.wav', '.m4a'],
        'misc': ['.pdf', '.txt', '.doc', '.docx']
    }
    
    valid_extensions = allowed_extensions.get(file_type, allowed_extensions['misc'])
    if ext not in valid_extensions:
        return Response({
            'error': f'Invalid file extension {ext} for type {file_type}. Allowed: {", ".join(valid_extensions)}'
        }, status=400)

    try:
        # Generate unique filename
        filename = f"{uuid.uuid4()}{ext}"
        
        # Path based on type
        relative_path = f"uploads/{file_type}/{filename}"
        
        # Save file
        saved_name = default_storage.save(relative_path, file_obj)
        
        # Build absolute URL
        # ensure MEDIA_URL doesn't double slash
        media_url = settings.MEDIA_URL
        if not media_url.endswith('/'):
            media_url += '/'
            
        file_url = request.build_absolute_uri(media_url + saved_name)
        
        return Response({
            'url': file_url,
            'filename': saved_name,
            'type': file_type,
            'size': file_obj.size
        })
    except Exception as e:
        return Response({'error': f'Failed to save file: {str(e)}'}, status=500)
