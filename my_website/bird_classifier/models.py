from django.db import models
from django.core.exceptions import ValidationError
import hashlib


# Create your models here.
class FileEntry(models.Model):
    file_location = models.FileField(upload_to='media/uploads/originals')
    file_name = models.CharField(max_length=255)
    date_time = models.DateTimeField(auto_now_add=True)
    hash = models.CharField(max_length=64, unique=True)
    bird = models.CharField(max_length=255)
    confidence = models.FloatField()
    audio_length = models.FloatField()

    def __str__(self):
        return f"{self.audio_file} - {self.hash} {self.confidence:.2f}"