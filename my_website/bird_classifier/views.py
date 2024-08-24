from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import FileEntry
from .forms import UploadFileForm
from . import file_handler, classify
import hashlib
import datetime
import os

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        text_input = request.POST.get('asset_num')
        download_path = None
        request_error = None

        if text_input:
            try:
                download_path = file_handler.download_from_macaulay(text_input)
            except ValidationError as e:
                request_error = str(e)


        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            print(f"uploaded_file: {uploaded_file}")

            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            existing_entry = FileEntry.objects.filter(hash=file_hash).first()
            if existing_entry:
                return render(request, 'result.html', {
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
                    'file_length': db_entry.audio_length,
                    'exists': 'No',
                    'bird': db_entry.bird,
                    'confidence': db_entry.confidence,
                    'hash': db_entry.hash
                })

        elif download_path is not None:
            bird, confidence = classify.get_prediction(download_path, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth'))
            return render(request, 'result.html', {
                'file_name': os.path.basename(download_path),
                'bird': bird,
                'confidence': confidence
            })

        else:
            if request_error is not None:
                error_message = request_error
            else:
                error_message = form.errors.get('__all__') or form.errors.get('file')
            if error_message:
                messages.error(request, error_message)
            return redirect('upload_file')

    return render(request, 'upload.html')
