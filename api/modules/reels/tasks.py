import threading
import os
import asyncio
from django.conf import settings
from ...models import Reel, Audio
from django.core.files.base import ContentFile

def _extract_and_match_audio_sync(reel_id):
    try:
        reel = Reel.objects.get(pk=reel_id)
        if not reel.video_url:
            return
        video_path = reel.video_url.path

        # 1. Extract Audio
        audio_filename = f"audio_{reel.id}.mp3"
        audio_dir = os.path.join(settings.MEDIA_ROOT, 'audios')
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, audio_filename)
        
        try:
            from moviepy.editor import VideoFileClip
            video = VideoFileClip(video_path)
            if video.audio:
                video.audio.write_audiofile(audio_path, verbose=False, logger=None)
                video.close()
            else:
                video.close()
                return # No audio track
        except Exception as e:
            print("Moviepy Error:", e)
            return

        # 2. Match Audio
        title = "Original Audio"
        artist = reel.user.username
        cover_image_url = None
        
        try:
            import shazamio
            async def recognize_audio():
                shazam = shazamio.Shazam()
                out = await shazam.recognize(audio_path)
                return out
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            shazam_data = loop.run_until_complete(recognize_audio())
            if 'track' in shazam_data:
                track = shazam_data['track']
                title = track.get('title', title)
                artist = track.get('subtitle', artist)
                images = track.get('images', {})
                cover_image_url = images.get('coverart', None)
        except Exception as e:
            print("Shazamio Error:", e)
            pass
            
        # 3. Create Audio Record
        audio = Audio.objects.create(
            title=title,
            artist=artist,
            cover_image_url=cover_image_url,
            created_by=reel.user,
        )
        with open(audio_path, 'rb') as f:
            audio.file_url.save(audio_filename, ContentFile(f.read()), save=True)
            
        reel.audio = audio
        reel.save()
        
    except Exception as e:
        print("Extract Audio Task Error:", e)

def launch_audio_extraction(reel_id):
    thread = threading.Thread(target=_extract_and_match_audio_sync, args=(reel_id,))
    thread.start()
