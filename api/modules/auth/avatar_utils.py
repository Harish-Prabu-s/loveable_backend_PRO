import os
import random
from django.conf import settings
from api.models import Profile

def assign_default_avatar(profile: Profile):
    """
    Assigns a random default avatar to the profile based on gender.
    """
    gender_map = {
        'M': 'male',
        'F': 'female',
        'O': 'male' # Default to male for Other if no specific assets
    }
    
    sub_dir = gender_map.get(profile.gender, 'male')
    avatar_dir = os.path.join(settings.MEDIA_ROOT, 'default_avatars', sub_dir)
    
    # Ensure directory exists
    if not os.path.exists(avatar_dir):
        return
        
    avatars = [f for f in os.listdir(avatar_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    if avatars:
        selected_avatar = random.choice(avatars)
        profile.photo = os.path.join('default_avatars', sub_dir, selected_avatar)
        profile.save(update_fields=['photo'])
