import os
import uuid
from django.core.files.base import ContentFile
from api.models import MediaAsset

class MediaService:
    @staticmethod
    def register_asset(user, file, media_kind, metadata=None):
        """
        Registers a new media asset, extracting metadata and handling storage.
        """
        filename = f"{uuid.uuid4()}_{file.name}"
        
        # In a real scalable system, we'd use S3 but here we stick to configured MEDIA_ROOT
        asset = MediaAsset.objects.create(
            user=user,
            file_type=file.content_type,
            media_kind=media_kind,
            original_url=file,
            mime_type=file.content_type,
            file_size=file.size,
            status='ready' # Initially ready for local storage
        )
        
        if metadata:
            if 'width' in metadata: asset.width = metadata['width']
            if 'height' in metadata: asset.height = metadata['height']
            if 'duration' in metadata: asset.duration = metadata['duration']
            asset.save()
            
        return asset

    @staticmethod
    def get_asset_url(asset):
        return asset.original_url.url if asset.original_url else None
