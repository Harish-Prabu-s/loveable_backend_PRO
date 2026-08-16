import os
import boto3
from botocore.client import Config
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
import django
django.setup()
from api.models import Reel

s3_client = boto3.client(
    service_name='s3',
    aws_access_key_id='UtoursgcA6hFq0pKBv7W39QVfaRIEekzMHji',
    aws_secret_access_key='0J7dNAmHRQcZSVzwugfb13i25CkOlavsWqY4',
    endpoint_url='https://innoida.utho.io',
    region_name='ap-south-in-noida-1',
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
)

bucket_name = 'loveable-bucket'

print("=== Checking Content-Type of Latest Reel Video ===")
latest_reel = Reel.objects.filter(video_url__isnull=False).last()
if latest_reel:
    key = str(latest_reel.video_url)
    print(f"Checking Key: {key}")
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=key)
        print("Content-Type:", response.get('ContentType'))
        print("Content-Length:", response.get('ContentLength'))
    except Exception as e:
        print("Error:", e)
else:
    print("No reel found.")
