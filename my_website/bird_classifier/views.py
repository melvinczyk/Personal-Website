import datetime
import hashlib
from django.shortcuts import render
from django.conf import settings
from . import file_handler
from .models import FileEntry
from .forms import UploadFileForm
from . import classify
import os


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            print(f"uploaded_file: {uploaded_file.name}")

            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            existing_entry = FileEntry.objects.filter(hash=file_hash).first()
            if existing_entry:
                return render(request, 'result.html',
                              {
                                  'file_name': existing_entry.file_name,
                                  'file_location': existing_entry.file_location,
                                  'file_length': existing_entry.audio_length,
                                  'exists': 'Yes',
                                  'bird': existing_entry.bird,
                                  'confidence': existing_entry.confidence,
                                  'hash': existing_entry.hash
                              })
            else:
                saved_file, cleaned_name = file_handler.save_uploaded_file(uploaded_file)
                print(f"saved_file: {saved_file}")
                signal, sr, duration = file_handler.get_audio_data(saved_file)
                bird, confidence = classify.get_prediction(saved_file, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth'))
                zipped_path = file_handler.compress_file(saved_file)

                db_entry = FileEntry(
                    file_location=zipped_path,
                    file_name=cleaned_name,
                    date_time=datetime.datetime.now(),
                    hash=file_hash,
                    bird=bird,
                    confidence=confidence,
                    audio_length=duration
                )
                db_entry.save()
                return render(request, 'result.html', {
                    'file_name': db_entry.file_name,
                    'file_location': db_entry.file_location,
                    'file_length' : db_entry.audio_length,
                    'bird': db_entry.bird,
                    'confidence': db_entry.confidence,
                    'hash': db_entry.hash,
                    'exists': 'No'
                })
        else:
            return render(request, 'upload.html')

    return render(request, 'upload.html')
