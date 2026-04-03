# Generated to explicitly safely allow emoji insertions on live server.
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('api', '0036_usersetting_face_registration_data_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER DATABASE loveable CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;",
                "ALTER TABLE api_gift CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            ],
            reverse_sql=[
                "ALTER TABLE api_gift CONVERT TO CHARACTER SET utf8;"
            ]
        ),
    ]
