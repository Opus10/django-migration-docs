from django.db import models


class TestModel(models.Model):
    """For testing migration docs"""

    field1 = models.CharField(max_length=100)
    field2 = models.CharField(max_length=100)
    field3 = models.CharField(max_length=100)
