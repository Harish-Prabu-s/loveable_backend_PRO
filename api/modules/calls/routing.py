# WebSocket routing for calls is handled by api.modules.realtime.routing
# which registers:
#   /ws/call/{user_id}/       → CallConsumer  (incoming call notifications)
#   /ws/call/room/{room_id}/  → CallRoomConsumer (P2P WebRTC signaling)
#
# This file is kept for import compatibility only.
websocket_urlpatterns = []
