import datetime
import hashlib

from django.shortcuts import render
from django.core.files.storage import default_storage
from django.conf import settings
from . import file_handler
from .models import FileEntry
from .forms import UploadFileForm
import os


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']

            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            existing_entry = FileEntry.objects.filter(hash=file_hash).first()
            if existing_entry:
                return render(request, 'result.html',
                              {
                                  'file_name': existing_entry.file_name,
                                  'file_location': existing_entry.audio_file,
                                  'file_length': existing_entry.audio_length,
                                  'exists': 'Yes',
                              })
            else:
                saved_file = file_handler.save_uploaded_file(uploaded_file)
                print(f"{saved_file}")
                signal, sr, duration = file_handler.get_audio_data(saved_file)

                db_entry = FileEntry(
                    audio_file = saved_file,
                    file_name = uploaded_file.name,
                    date_time = datetime.datetime.now(),
                    hash = file_hash,
                    predicted_bird = 'crow',
                    confidence=0,
                    audio_length=duration
                )
                db_entry.save()
                return render(request, 'result.html', {
                    'file_name': uploaded_file.name,
                    'file_location': saved_file,
                    'file_length' : duration
                })
        else:
            return render(request, 'upload.html')

    return render(request, 'upload.html')
