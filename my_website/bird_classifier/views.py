import datetime

from django.shortcuts import render
from django.core.files.storage import default_storage
from django.conf import settings
from . import audio_handler
from .models import FileEntry
import os


def upload_file(request):
    if request.method == 'POST' and request.FILES.get('file'):
        uploaded_file = request.FILES['file']

        saved_file = audio_handler.save_uploaded_file(uploaded_file)
        print(f"{saved_file}")
        signal, sr, duration = audio_handler.get_audio_data(saved_file)

        db_entry = FileEntry(
            file_name = uploaded_file.name,
            date_time = datetime.datetime.now(),
            predicted_bird = 'crow',
            confidence = 0,
            audio_length = duration
        )
        db_entry.save()
        return render(request, 'result.html', {
            'file_name': uploaded_file.name,
            'file_location': saved_file,
            'file_length' : duration
        })

    return render(request, 'upload.html')
