from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    MediaAsset, MusicTrack, EditorDraft, MusicClipSelection, 
    OverlayItem, FilterSelection, PublishedContent
)
from .serializers import (
    MediaAssetSerializer, MusicTrackSerializer, EditorDraftSerializer,
    PublishedContentSerializer
)
from .services.media_service import MediaService
from .services.music_service import MusicService
from .services.publish_service import PublishService

class MediaAssetViewSet(viewsets.ModelViewSet):
    queryset = MediaAsset.objects.all()
    serializer_class = MediaAssetSerializer

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        file = request.FILES.get('file')
        media_kind = request.data.get('media_kind', 'image')
        if not file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
        
        asset = MediaService.register_asset(request.user, file, media_kind)
        return Response(MediaAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

class MusicTrackViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MusicTrack.objects.filter(is_active=True)
    serializer_class = MusicTrackSerializer
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['title', 'artist_name']
    filterset_fields = ['language', 'genre', 'is_trending']

    def list(self, request, *args, **kwargs):
        query = request.query_params.get('search') or request.query_params.get('q')
        if query:
            # Trigger provider search if query is provided
            results = MusicService.search_music(query, provider_name=request.query_params.get('provider', 'jiosaavn'))
            # Note: We return normalized data directly from search, or we could fetch from DB
            return Response(results)
        return super().list(request, *args, **kwargs)

class EditorDraftViewSet(viewsets.ModelViewSet):
    queryset = EditorDraft.objects.all()
    serializer_class = EditorDraftSerializer

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user, status='draft')

    @action(detail=True, methods=['post'])
    def attach_music(self, request, pk=None):
        draft = self.get_object()
        provider_track_id = request.data.get('provider_track_id')
        provider_name = request.data.get('provider_name', 'jiosaavn')
        start_sec = float(request.data.get('clip_start_seconds', 0))
        end_sec = float(request.data.get('clip_end_seconds', 0))
        
        try:
            selection = MusicService.attach_clip_to_draft(
                request.user, draft, provider_track_id, start_sec, end_sec, provider_name
            )
            return Response({'status': 'music attached', 'selection_id': selection.id}, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def add_overlay(self, request, pk=None):
        draft = self.get_object()
        # Simplified overlay creation - in practice would use a dedicated serializer
        OverlayItem.objects.create(
            draft=draft,
            overlay_type=request.data.get('overlay_type'),
            content=request.data.get('content'),
            pos_x=request.data.get('pos_x'),
            pos_y=request.data.get('pos_y'),
            scale_value=request.data.get('scale_value', 1.0),
            rotation_value=request.data.get('rotation_value', 0.0),
            z_index=request.data.get('z_index', 0)
        )
        return Response({'status': 'overlay added'}, status=status.HTTP_201_CREATED)

class PublishViewSet(viewsets.GenericViewSet):
    queryset = PublishedContent.objects.all()
    
    @action(detail=False, methods=['post'])
    def story(self, request):
        draft_id = request.data.get('draft_id')
        try:
            draft = EditorDraft.objects.get(id=draft_id, user=request.user)
            content = PublishService.publish_draft(draft, visibility=request.data.get('visibility', 'all'))
            return Response(PublishedContentSerializer(content).data, status=status.HTTP_201_CREATED)
        except EditorDraft.DoesNotExist:
            return Response({'error': 'Draft not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def reel(self, request):
        # Similar to story but with specific reel logic if any
        return self.story(request)

    @action(detail=False, methods=['post'])
    def post(self, request):
        return self.story(request)
