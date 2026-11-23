from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("locations", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pollingunit",
            name="landmark",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AlterField(
            model_name="pollingunit",
            name="name",
            field=models.CharField(db_index=True, max_length=300),
        ),
        migrations.AlterField(
            model_name="pollingunit",
            name="pu_code",
            field=models.CharField(db_index=True, max_length=48, unique=True),
        ),
        migrations.AddIndex(
            model_name="pollingunit",
            index=models.Index(fields=["latitude", "longitude"], name="loc_pu_lat_lng_idx"),
        ),
    ]
