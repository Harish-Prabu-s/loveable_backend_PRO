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

bucket_names = ['loveable-bucket', 'bucket-loveable-bucket']

for bucket_name in bucket_names:
    print(f"\n--- Testing Bucket: {bucket_name} ---")
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        print("Success: list_objects_v2 works!")
    except ClientError as e:
        print(f"Error list_objects_v2: {e}")

    try:
        response = s3_client.head_bucket(Bucket=bucket_name)
        print("Success: head_bucket works!")
    except ClientError as e:
        print(f"Error head_bucket: {e}")
