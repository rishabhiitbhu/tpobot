# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-16 08:34
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0012_auto_20170715_1717'),
    ]

    operations = [
        migrations.RenameField(
            model_name='company',
            old_name='departments',
            new_name='department',
        ),
    ]
