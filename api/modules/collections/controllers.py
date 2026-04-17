from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models import Collection, SavedItem
from ...serializers import CollectionSerializer, SavedItemSerializer

class CollectionViewSet(viewsets.ModelViewSet):
    serializer_class = CollectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        type_filter = self.request.query_params.get('type')
        qs = Collection.objects.filter(user=user).order_by('-created_at')
        if type_filter:
            qs = qs.filter(type=type_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def toggle_save(self, request):
        """
        Generic toggle save for Posts, Reels, or Audio.
        Payload: { item_type: 'post'|'reel'|'audio', item_id: 123 }
        """
        user = request.user
        item_type = request.data.get('item_type')
        item_id = request.data.get('item_id')
        collection_id = request.data.get('collection_id')

        if not item_type or not item_id:
            return Response({'error': 'item_type and item_id required'}, status=400)

        # Get or create the appropriate collection
        if collection_id:
            collection = Collection.objects.filter(user=user, id=collection_id).first()
        else:
            collection, _ = Collection.objects.get_or_create(user=user, type=item_type, name=f'Saved {item_type.capitalize()}s')

        if not collection:
            return Response({'error': 'Collection not found'}, status=404)

        # Build the toggle logic
        filter_kwargs = {'collection': collection}
        if item_type == 'post': filter_kwargs['post_id'] = item_id
        elif item_type == 'reel': filter_kwargs['reel_id'] = item_id
        elif item_type == 'audio': filter_kwargs['audio_id'] = item_id
        else: return Response({'error': 'Invalid item type'}, status=400)

        saved_item = SavedItem.objects.filter(**filter_kwargs).first()
        if saved_item:
            saved_item.delete()
            return Response({'status': 'unsaved', 'is_saved': False})
        
        SavedItem.objects.create(**filter_kwargs)
        return Response({'status': 'saved', 'is_saved': True})
