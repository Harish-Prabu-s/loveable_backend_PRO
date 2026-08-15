from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.core.files.storage import default_storage
from django.conf import settings
import os
import uuid

from api.utils.media_compress import validate_and_compress

# ── Absolute hard limits (server will reject anything beyond these) ───────────
MAX_IMAGE_SIZE = 6  * 1024 * 1024   # 6 MB  — compressed automatically if over
MAX_VIDEO_SIZE = 20 * 1024 * 1024   # 20 MB — compressed to HEVC if over
MAX_VOICE_SIZE = 50 * 1024 * 1024   # 50 MB — no compression for audio

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_file_view(request):
    if 'file' not in request.FILES:
        return Response({'error': 'No file provided'}, status=400)

    file_obj  = request.FILES['file']
    file_type = request.data.get('type', 'misc')

    # Extension validation
    ext = os.path.splitext(file_obj.name)[1].lower()
    allowed_extensions = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.heif'],
        'video': ['.mp4', '.mov', '.avi', '.mkv', '.hevc', '.m4v'],
        'voice': ['.m4a', '.wav', '.mp3', '.aac'],
        'audio': ['.mp3', '.wav', '.m4a'],
        'misc':  ['.pdf', '.txt', '.doc', '.docx'],
    }

    valid_exts = allowed_extensions.get(file_type, allowed_extensions['misc'])
    if ext not in valid_exts:
        return Response({
            'error': f'Invalid file type {ext} for {file_type}. Allowed: {", ".join(valid_exts)}'
        }, status=400)

    # Hard reject if wildly oversized (before even attempting compression)
    hard_limit = MAX_VIDEO_SIZE * 5 if file_type == 'video' else MAX_IMAGE_SIZE * 10
    if file_obj.size > hard_limit:
        limit_mb = hard_limit // (1024 * 1024)
        return Response({'error': f'File too large (absolute max {limit_mb}MB)'}, status=413)

    try:
        # Compress / convert
        content, new_ext, error = validate_and_compress(file_obj, file_type)
        if error:
            return Response({'error': error}, status=400)

        filename      = f"{uuid.uuid4()}{new_ext or ext}"
        relative_path = f"uploads/{file_type}/{filename}"
        saved_name    = default_storage.save(relative_path, content)

        # Build the URL — works with both local storage and S3
        file_url = request.build_absolute_uri(default_storage.url(saved_name))

        return Response({
            'url':      file_url,
            'filename': saved_name,
            'type':     file_type,
            'size':     content.size if hasattr(content, 'size') else len(content.read()),
        })
    except Exception as e:
        return Response({'error': f'Failed to save file: {str(e)}'}, status=500)
