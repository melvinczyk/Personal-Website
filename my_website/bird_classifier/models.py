from django.db import models

# Create your models here.
class FileEntry(models.Model):
    audio_file = models.FileField(upload_to='media/uploads/originals')
    date_time = models.DateTimeField(auto_now_add=True)
    hash = models.CharField(max_length=64, unique=True)
    predicted_bird = models.CharField(max_length=255)
    confidence = models.FloatField()
    audio_length = models.FloatField()

    def __str__(self):
        return f"{self.audio_file} - {self.predicted_bird} ({self.confidence:.2f}"