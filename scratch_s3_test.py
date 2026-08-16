import os
import boto3
from botocore.exceptions import ClientError

session = boto3.session.Session()
s3_client = session.client(
    service_name='s3',
    aws_access_key_id='UtoursgcA6hFq0pKBv7W39QVfaRIEekzMHji',
    aws_secret_access_key='0J7dNAmHRQcZSVzwugfb13i25CkOlavsWqY4',
    endpoint_url='https://innoida.utho.io',
    region_name='ap-south-in-noida-1',
)

bucket_name = 'loveable-bucket'

print(f"Testing with Bucket: {bucket_name}, Endpoint: https://innoida.utho.io")

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

try:
    response = s3_client.put_object(Bucket=bucket_name, Key='test_file.txt', Body=b'Hello World')
    print("Success: put_object works!")
except ClientError as e:
    print(f"Error put_object: {e}")
