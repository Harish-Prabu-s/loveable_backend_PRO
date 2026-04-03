from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from ...models import Report

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_report(request):
    reported_user_id = request.data.get('reported_user_id')
    reason = request.data.get('reason')
    description = request.data.get('description', '')

    if not reported_user_id or not reason:
        return Response({'error': 'reported_user_id and reason are required'}, status=400)

    try:
        reported_user = User.objects.get(id=reported_user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    if reported_user.id == request.user.id:
        return Response({'error': 'You cannot report yourself'}, status=400)

    Report.objects.create(
        reporter=request.user,
        reported_user=reported_user,
        reason=reason,
        description=description
    )

    return Response({'success': True, 'message': 'Report submitted successfully'})
