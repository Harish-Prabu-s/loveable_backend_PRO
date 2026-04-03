from django.core.management.base import BaseCommand
from api.models import Story, Reel, Profile, Post
from api.utils import strip_base_url

class Command(BaseCommand):
    help = 'Fixes absolute media URLs in the database by converting them to relative paths.'

    def handle(self, *args, **options):
        # Fix Stories
        stories = Story.objects.filter(media_url__icontains='http')
        self.stdout.write(f"Found {stories.count()} stories with absolute URLs.")
        for story in stories:
            old_url = str(story.media_url)
            new_path = strip_base_url(old_url)
            if old_url != new_path:
                story.media_url = new_path
                story.save()
                self.stdout.write(self.style.SUCCESS(f"Fixed Story {story.id}: {old_url} -> {new_path}"))

        # Fix Reels
        reels = Reel.objects.filter(video_url__icontains='http')
        self.stdout.write(f"Found {reels.count()} reels with absolute URLs.")
        for reel in reels:
            old_url = str(reel.video_url)
            new_path = strip_base_url(old_url)
            if old_url != new_path:
                reel.video_url = new_path
                reel.save()
                self.stdout.write(self.style.SUCCESS(f"Fixed Reel {reel.id}: {old_url} -> {new_path}"))

        # Fix Profiles
        profiles = Profile.objects.filter(photo__icontains='http')
        self.stdout.write(f"Found {profiles.count()} profiles with absolute URLs.")
        for profile in profiles:
            old_url = str(profile.photo)
            new_path = strip_base_url(old_url)
            if old_url != new_path:
                profile.photo = new_path
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"Fixed Profile {profile.id}: {old_url} -> {new_path}"))

        # Fix Posts
        posts = Post.objects.filter(image__icontains='http')
        self.stdout.write(f"Found {posts.count()} posts with absolute URLs.")
        for post in posts:
            old_url = str(post.image)
            new_path = strip_base_url(old_url)
            if old_url != new_path:
                post.image = new_path
                post.save()
                self.stdout.write(self.style.SUCCESS(f"Fixed Post {post.id}: {old_url} -> {new_path}"))

        self.stdout.write(self.style.SUCCESS('Successfully fixed media paths.'))
