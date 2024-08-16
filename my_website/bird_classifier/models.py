from django.db import models

# Create your models here.
class FileEntry(models.Model):
    file_name = models.CharField(max_length=255)
    date_time = models.DateTimeField(auto_now_add=True)
    predicted_bird = models.CharField(max_length=255)
    confidence = models.FloatField()
    audio_length = models.FloatField()

    def __str__(self):
        return f"{self.file_name} - {self.predicted_bird} ({self.confidence:.2f}"