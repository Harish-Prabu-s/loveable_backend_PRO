import requests

with open('dummy.mp4', 'wb') as f:
    f.write(b'0' * 1024 * 1024)

files = {'media': ('reel_video.mp4', open('dummy.mp4', 'rb'), 'video/mp4')}
response = requests.post('http://127.0.0.1:8000/api/reels/upload/', files=files)
print('STATUS:', response.status_code)
print('BODY:', response.text)
