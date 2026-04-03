from django.db.models import Count, Q
from django.contrib.auth.models import User
from ...models import Profile, Room, Message, Story
from datetime import datetime

def search_users(q: str = '', date: str = '', page: int = 1, page_size: int = 10):
    qs = Profile.objects.select_related('user')
    if q:
        qs = qs.filter(Q(display_name__icontains=q) | Q(phone_number__icontains=q) | Q(user__id__icontains=q))
    if date:
        try:
            dt = datetime.strptime(date, '%Y-%m-%d').date()
            qs = qs.filter(updated_at__date=dt)
        except ValueError:
            pass
    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    items = []
    for p in qs[start:end]:
        video_count = Room.objects.filter(caller=p.user, call_type='video').count() + Room.objects.filter(receiver=p.user, call_type='video').count()
        audio_count = Room.objects.filter(caller=p.user, call_type='audio').count() + Room.objects.filter(receiver=p.user, call_type='audio').count()
        items.append({
            'id': p.user.id,
            'name': p.display_name,
            'phone_number': p.phone_number,
            'video_call_count': video_count,
            'audio_call_count': audio_count,
        })
    return {'count': total, 'results': items}

