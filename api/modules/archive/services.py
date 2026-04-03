from django.db import models
from django.contrib.auth.models import User
from ...models import Post, Reel, Room

def archive_content(user: User, content_type: str, content_id: int):
    """
    Archives a piece of content. 
    Supported types: 'post', 'reel', 'chat' (actually room)
    """
    try:
        if content_type == 'post':
            item = Post.objects.get(id=content_id, user=user)
        elif content_type == 'reel':
            item = Reel.objects.get(id=content_id, user=user)
        elif content_type == 'chat':
            # For chats, 'archive' means hiding the room from the list
            item = Room.objects.get(models.Q(caller=user) | models.Q(receiver=user), id=content_id)
        else:
            return {'error': 'Invalid content type'}
        
        item.is_archived = True
        item.save()
        return {'success': True}
    except (Post.DoesNotExist, Reel.DoesNotExist, Room.DoesNotExist):
        return {'error': 'Content not found or permission denied'}

def unarchive_content(user: User, content_type: str, content_id: int):
    """
    Unarchives a piece of content.
    """
    try:
        if content_type == 'post':
            item = Post.objects.get(id=content_id, user=user)
        elif content_type == 'reel':
            item = Reel.objects.get(id=content_id, user=user)
        elif content_type == 'chat':
            item = Room.objects.get(models.Q(caller=user) | models.Q(receiver=user), id=content_id)
        else:
            return {'error': 'Invalid content type'}
        
        item.is_archived = False
        item.save()
        return {'success': True}
    except (Post.DoesNotExist, Reel.DoesNotExist, Room.DoesNotExist):
        return {'error': 'Content not found or permission denied'}

def delete_content(user: User, content_type: str, content_id: int):
    """
    Permanently deletes a piece of content.
    """
    try:
        if content_type == 'post':
            item = Post.objects.get(id=content_id, user=user)
        elif content_type == 'reel':
            item = Reel.objects.get(id=content_id, user=user)
            # Should also delete media file
            if item.video_url:
                try: item.video_url.delete(save=False)
                except: pass
        elif content_type == 'chat':
            item = Room.objects.get(models.Q(caller=user) | models.Q(receiver=user), id=content_id)
            # Deleting a room deletes all messages due to CASCADE
        elif content_type == 'story':
            from ...models import Story
            item = Story.objects.get(id=content_id, user=user)
            if item.media_url:
                try: item.media_url.delete(save=False)
                except: pass
        else:
            return {'error': 'Invalid content type'}
        
        item.delete()
        return {'success': True}
    except Exception as e:
        return {'error': str(e)}

def get_archived_content(user, content_type: str):
    """
    Returns a list of archived items.
    """
    if content_type == 'post':
        from ...serializers import PostSerializer
        items = Post.objects.filter(user=user, is_archived=True).order_by('-created_at')
        return PostSerializer(items, many=True, context={'request_user': user}).data
    elif content_type == 'reel':
        from ...serializers import ReelSerializer
        items = Reel.objects.filter(user=user, is_archived=True).order_by('-created_at')
        return ReelSerializer(items, many=True, context={'request_user': user}).data
    elif content_type == 'chat':
        from ...serializers import RoomSerializer
        items = Room.objects.filter(models.Q(caller=user) | models.Q(receiver=user), is_archived=True).order_by('-created_at')
        return RoomSerializer(items, many=True, context={'request_user': user}).data
    return {'error': 'Invalid content type'}
