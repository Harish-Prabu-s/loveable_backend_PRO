import pymysql
from dotenv import load_dotenv
import os

load_dotenv('.env')

connection = pymysql.connect(
    host=os.environ.get('DB_HOST'),
    user='harish',
    password=os.environ.get('DB_PASSWORD'),
    database='loveable',
    cursorclass=pymysql.cursors.DictCursor
)

with connection.cursor() as cursor:
    print('--- SCHEMA ---')
    cursor.execute("DESCRIBE api_recevent;")
    schema = cursor.fetchall()
    for row in schema:
        print(row)
        
    print('\n--- SAMPLE DATA ---')
    cursor.execute("SELECT * FROM api_recevent LIMIT 5;")
    data = cursor.fetchall()
    for row in data:
        print(row)

