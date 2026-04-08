from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models import Highlight, HighlightStory, Story
from ...serializers import HighlightSerializer, StorySerializer

class HighlightViewSet(viewsets.ModelViewSet):
    serializer_class = HighlightSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.request.query_params.get('user_id')
        if user_id:
            return Highlight.objects.filter(user_id=user_id).order_by('-created_at')
        return Highlight.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        highlight = serializer.save(user=self.request.user)
        story_ids = self.request.data.getlist('story_ids', [])
        for sid in story_ids:
            try:
                story = Story.objects.get(id=sid)
                HighlightStory.objects.get_or_create(highlight=highlight, story=story)
            except Story.DoesNotExist:
                pass

    @action(detail=True, methods=['post'])
    def add_stories(self, request, pk=None):
        highlight = self.get_object()
        story_ids = request.data.getlist('story_ids', [])
        
        for sid in story_ids:
            try:
                story = Story.objects.get(id=sid)
                HighlightStory.objects.get_or_create(highlight=highlight, story=story)
            except Story.DoesNotExist:
                pass
        
        return Response(self.get_serializer(highlight).data)

    @action(detail=True, methods=['post'])
    def remove_story(self, request, pk=None):
        highlight = self.get_object()
        story_id = request.data.get('story_id')
        HighlightStory.objects.filter(highlight=highlight, story_id=story_id).delete()
        return Response(self.get_serializer(highlight).data)
