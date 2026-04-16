from api.models import PublishedContent, PublishedMusicAttachment, MediaAsset
from django.db import transaction

class PublishService:
    @staticmethod
    def publish_draft(draft, visibility='all'):
        """
        Orchestrates publishing a draft into final content.
        """
        with transaction.atomic():
            # Create the final published record
            content = PublishedContent.objects.create(
                user=draft.user,
                content_type=draft.content_type,
                media_asset=draft.media_asset,
                caption=draft.caption,
                note_text=draft.note_text,
                editor_metadata_json=draft.editor_metadata_json,
                visibility=visibility,
                publish_status='published' # In a real queue system, maybe 'processing'
            )
            
            # Transfer music selection if exists
            if hasattr(draft, 'music_selection'):
                sel = draft.music_selection
                PublishedMusicAttachment.objects.create(
                    content=content,
                    provider_name=sel.provider_name,
                    provider_track_id=sel.provider_track_id,
                    track=sel.track,
                    clip_start_seconds=sel.clip_start_seconds,
                    clip_end_seconds=sel.clip_end_seconds,
                    clip_duration=sel.clip_duration
                )
            
            # Mark draft as archived
            draft.status = 'archived'
            draft.save()
            
            # Optional: Here we would trigger the Celery task for processing
            # from api.tasks import process_media_composition
            # process_media_composition.delay(content.id)
            
            return content
