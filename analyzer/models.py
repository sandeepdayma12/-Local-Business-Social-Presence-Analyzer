from django.db import models

from django.db import models

class Business(models.Model):
    name = models.CharField(max_length=255)
    contact = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    linkedin = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name

