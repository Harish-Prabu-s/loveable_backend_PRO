from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from io import BytesIO
from .services import search_users
from ...models import Message, Story

@api_view(['GET'])
@permission_classes([IsAdminUser])
def users_overview_view(request):
    q = request.GET.get('q', '')
    date = request.GET.get('date', '')
    page = int(request.GET.get('page', '1'))
    data = search_users(q, date, page, 10)
    return Response(data)

def _pdf_response(title: str, lines: list):
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.setTitle(title)
    y = 800
    for line in lines:
        p.drawString(50, y, line[:1000])
        y -= 20
        if y < 50:
            p.showPage()
            y = 800
    p.save()
    buffer.seek(0)
    return HttpResponse(buffer.getvalue(), content_type='application/pdf')

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_chat_images_pdf(request, user_id: int):
    qs = Message.objects.filter(sender_id=user_id, type='image').order_by('-created_at')
    lines = [f"{m.created_at.isoformat()} {m.media_url or m.content}" for m in qs]
    return _pdf_response("Chat Images", lines)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_voice_messages_pdf(request, user_id: int):
    qs = Message.objects.filter(sender_id=user_id, type='audio').order_by('-created_at')
    lines = [f"{m.created_at.isoformat()} duration {m.duration_seconds}s" for m in qs]
    return _pdf_response("Voice Messages", lines)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_stories_pdf(request, user_id: int):
    qs = Story.objects.filter(user_id=user_id).order_by('-timestamp')
    lines = [f"{s.timestamp.isoformat()} {s.image_url}" for s in qs]
    return _pdf_response("Stories", lines)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def export_chat_conversation_pdf(request, user_id: int):
    qs = Message.objects.filter(sender_id=user_id).order_by('created_at')
    lines = [f"{m.created_at.isoformat()} {m.content}" for m in qs]
    return _pdf_response("Chat Conversation", lines)
