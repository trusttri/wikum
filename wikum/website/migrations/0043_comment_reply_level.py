# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2017-07-30 12:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0042_comment_deep_num_replies'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='reply_level',
            field=models.IntegerField(default=0),
        ),
    ]
