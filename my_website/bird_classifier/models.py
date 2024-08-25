from django.db import models


# Create your models here.
class FileEntry(models.Model):
    hash = models.CharField(max_length=64, unique=True)
    upload_type = models.CharField(max_length=255)
    file_location = models.FileField(upload_to='media/uploads/originals')
    file_name = models.CharField(max_length=255)
    date_time = models.DateTimeField(auto_now_add=True)
    bird = models.CharField(max_length=255)
    confidence = models.FloatField()
    audio_length = models.FloatField()
    num_segments = models.IntegerField()
    spectrogram_path = models.FileField(upload_to='media/spectrograms')

    def __str__(self):
        return f"{self.file_name} - {self.hash} {self.confidence:.2f}"