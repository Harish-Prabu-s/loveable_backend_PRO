import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

def check_indices():
    with connection.cursor() as cursor:
        cursor.execute("SHOW INDEX FROM api_pushtoken")
        indices = cursor.fetchall()
        with open("indices_output.txt", "w") as f:
            f.write("Table Indices:\n")
            for idx in indices:
                # Table, Non_unique, Key_name, Seq_in_index, Column_name
                non_unique = idx[1]
                key_name = idx[2]
                column_name = idx[4]
                f.write(f"Key: {key_name}, Column: {column_name}, Non-Unique: {non_unique}\n")

if __name__ == "__main__":
    check_indices()
