from rest_framework.decorators import api_view
from rest_framework.response import Response
from ...serializers import LevelProgressSerializer
from .services import get_level_progress

@api_view(['GET'])
def my_level_view(request):
    lp = get_level_progress(request.user)
    return Response(LevelProgressSerializer(lp).data)
