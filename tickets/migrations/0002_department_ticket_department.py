# Generated by Django 5.2.1 on 2025-05-18 17:32

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('it_support', 'IT Support'), ('customer_service', 'Customer Service'), ('hr', 'Human Resources'), ('finance', 'Finance'), ('operations', 'Operations'), ('maintenance', 'Maintenance'), ('security', 'Security'), ('sales', 'Sales')], max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('staff', models.ManyToManyField(limit_choices_to={'is_staff': True}, related_name='departments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='ticket',
            name='department',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='tickets', to='tickets.department'),
        ),
    ]
