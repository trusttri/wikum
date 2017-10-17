# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2017-07-18 17:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0039_change_comment_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='CloseComment',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Article')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.CommentAuthor')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Comment')),
            ],
        ),
        migrations.CreateModel(
            name='OpenComment',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Article')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.CommentAuthor')),
                ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='website.Comment')),
            ],
        ),
    ]