import os
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config

session = boto3.session.Session()
s3_client = session.client(
    service_name='s3',
    aws_access_key_id='UtoursgcA6hFq0pKBv7W39QVfaRIEekzMHji',
    aws_secret_access_key='0J7dNAmHRQcZSVzwugfb13i25CkOlavsWqY4',
    endpoint_url='https://innoida.utho.io',
    region_name='ap-south-in-noida-1',
    config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
)

bucket_name = 'loveable-bucket'

print("Attempting to set bucket ACL to public-read...")
try:
    s3_client.put_bucket_acl(Bucket=bucket_name, ACL='public-read')
    print("Success: Bucket is now public-read!")
except ClientError as e:
    print(f"Error put_bucket_acl: {e}")

print("Attempting to generate presigned URL to see if it works as a fallback...")
try:
    url = s3_client.generate_presigned_url('get_object',
                                            Params={'Bucket': bucket_name,
                                                    'Key': 'posts/1_5fffb7e4_post_image.jpg'},
                                            ExpiresIn=3600)
    print("Presigned URL:", url)
except Exception as e:
    print("Error presigned url:", e)
