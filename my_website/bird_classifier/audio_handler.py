import librosa
import os
from django.core.files.storage import default_storage
from django.conf import settings


def save_uploaded_file(uploaded_file):
    directory = 'uploads/originals/'
    file_path = os.path.join(directory, uploaded_file.name)

    if default_storage.exists(file_path):
        return os.path.join(settings.MEDIA_ROOT, file_path)
    saved_path = default_storage.save(file_path, uploaded_file)
    return os.path.join(settings.MEDIA_ROOT, saved_path)

def get_audio_data(file_path):
    signal, sr = librosa.load(file_path, sr=None)
    duration = librosa.get_duration(y=signal, sr=sr)
    return signal, sr, duration


