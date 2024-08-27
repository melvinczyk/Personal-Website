from django.db import models


# Create your models here.
class FileEntry(models.Model):
    hash = models.CharField(max_length=64, unique=True, null=True)
    upload_type = models.CharField(max_length=255)
    file_location = models.FileField(upload_to='media/uploads/originals', null=True)
    file_name = models.CharField(max_length=255, null=True)
    date_time = models.DateTimeField(auto_now_add=True)
    bird = models.CharField(max_length=255)
    confidence = models.FloatField()
    duration = models.FloatField()
    num_segments = models.IntegerField()
    spectrogram_path = models.FileField(upload_to='media/spectrograms', null=True)
    correct = models.BooleanField(null=True)
    user_bird = models.CharField(max_length=255, null=True)

    def __str__(self):
        return f"{self.file_name} - {self.hash} {self.confidence:.2f}"

