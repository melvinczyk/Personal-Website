import hashlib
import librosa
import os
from django.core.files.storage import default_storage
from django.conf import settings
from pydub import AudioSegment
import mimetypes
from .models import FileEntry


def save_uploaded_file(uploaded_file):
    directory = 'uploads/originals/'
    file_path = os.path.join(directory, uploaded_file.name)

    print(f"{file_path}")

    saved_path = default_storage.save(file_path, uploaded_file)
    print(f"{saved_path}")
    saved_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)

    mime_type, _ = mimetypes.guess_type(saved_file_path)

    if mime_type != 'audio/wav':
        audio = AudioSegment.from_file(saved_file_path)
        wav_path = os.path.splitext(saved_file_path)[0] + '.wav'
        audio.export(wav_path, format='wav')
        os.remove(saved_file_path)
        print(f"{wav_path}")
        return wav_path
    print(f"{saved_file_path}")
    return  saved_file_path


def get_audio_data(file_path):
    signal, sr = librosa.load(file_path, sr=None)
    duration = librosa.get_duration(y=signal, sr=sr)
    return signal, sr, duration


