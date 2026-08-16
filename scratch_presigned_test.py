import requests
import boto3
from botocore.client import Config

s3_client = boto3.client(
    service_name='s3',
    aws_access_key_id='UtoursgcA6hFq0pKBv7W39QVfaRIEekzMHji',
    aws_secret_access_key='0J7dNAmHRQcZSVzwugfb13i25CkOlavsWqY4',
    endpoint_url='https://innoida.utho.io',
    region_name='ap-south-in-noida-1',
    config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
)

bucket_name = 'loveable-bucket'
key = 'posts/1_5fffb7e4_post_image.jpg'

# Generate a 7-day presigned URL (path style)
url = s3_client.generate_presigned_url(
    'get_object',
    Params={'Bucket': bucket_name, 'Key': key},
    ExpiresIn=604800
)

print("Presigned URL:", url)
print("")

# Test if it's accessible
resp = requests.get(url)
print("HTTP Status:", resp.status_code)
if resp.status_code == 200:
    print("SUCCESS! Image is accessible via presigned URL.")
else:
    print("Error:", resp.text[:300])
