# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2017-10-14 23:29
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('website', '0048_auto_20171014_1801'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetaComment',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('datetime', models.DateTimeField(auto_now=True)),
                ('text', models.TextField()),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Article')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Comment')),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]