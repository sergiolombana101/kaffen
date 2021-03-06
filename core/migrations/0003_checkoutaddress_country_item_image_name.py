# Generated by Django 4.0.5 on 2022-06-05 02:04

from django.db import migrations, models
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_payment_checkoutaddress'),
    ]

    operations = [
        migrations.AddField(
            model_name='checkoutaddress',
            name='country',
            field=django_countries.fields.CountryField(default=1, max_length=2),
        ),
        migrations.AddField(
            model_name='item',
            name='image_name',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
