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

print("=== Files currently in S3 bucket ===")
response = s3_client.list_objects_v2(Bucket=bucket_name)
contents = response.get('Contents', [])
if not contents:
    print("Bucket is EMPTY - no files uploaded yet!")
else:
    for obj in contents:
        print(f"  {obj['Key']}  ({obj['Size']} bytes)")
