import base64
import datetime
import mimetypes
import os
import re
import zipfile

import librosa
import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from pydub import AudioSegment

MELS_DIR = os.path.join(settings.BASE_DIR, 'bird_classifier', 'temp_mels')
MACAULAY = 'https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{}'
MAX_SECONDS = 90
MAX_DOWNLOAD = 50 * 1024 * 1024


def clean_filename(name):
    return re.sub(r'[^\w.-]', '_', name).strip('_') or '_'


def base64_encode_filename(filename):
    return base64.urlsafe_b64encode(filename.encode('utf-8')).decode('utf-8')


def mel_files(stem):
    """The spectrograms classify.py drew for one recording, as full paths."""
    pattern = re.compile(rf'^{re.escape(stem)}_\d+\.png$')
    return [os.path.join(MELS_DIR, name) for name in sorted(os.listdir(MELS_DIR))
            if pattern.match(name)]


def compress_spectrograms(stem):
    """Zip a recording's spectrograms into media and clear the originals."""
    out_dir = os.path.join(settings.MEDIA_ROOT, 'spectrograms')
    os.makedirs(out_dir, exist_ok=True)
    output_zip_path = os.path.join(out_dir, f'{stem}.zip')
    with zipfile.ZipFile(output_zip_path, 'w') as zip_file:
        for path in mel_files(stem):
            zip_file.write(path, os.path.basename(path))
            os.remove(path)
    return output_zip_path


def compress_file(wav_file_path):
    """Replace a wav with a zipped flac of it. Returns the zip's path."""
    stem = os.path.splitext(wav_file_path)[0]
    flac_path, zip_file_path = stem + '.flac', stem + '.zip'
    AudioSegment.from_file(wav_file_path).export(flac_path, format='flac')
    with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(flac_path, arcname=os.path.basename(flac_path))
    os.remove(wav_file_path)
    os.remove(flac_path)
    return zip_file_path


def save_uploaded_file(uploaded_file):
    """Store an upload as a wav. Returns (path or None, display name)."""
    filename, ext = os.path.splitext(uploaded_file.name)
    if filename == 'user_recording':
        folder, stem = 'uploads/recordings', str(datetime.datetime.now())
    else:
        folder, stem = 'uploads/originals', filename
    saved_path = default_storage.save(
        os.path.join(folder, base64_encode_filename(stem) + ext), uploaded_file)
    saved_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
    cleaned_name = clean_filename(filename)

    if mimetypes.guess_type(saved_file_path)[0] in ('audio/wav', 'audio/x-wav'):
        return saved_file_path, cleaned_name
    wav_path = os.path.splitext(saved_file_path)[0] + '.wav'
    try:
        AudioSegment.from_file(saved_file_path).export(wav_path, format='wav')
    except Exception as e:
        print(f"Error converting file to WAV: {e}")
        wav_path = None
    # either way the original is done with: it has been converted or it cannot be
    os.remove(saved_file_path)
    return wav_path, cleaned_name


def get_list_spectrograms(zip_path):
    """Every spectrogram in a zip as base64 PNG, with a label for each."""
    image_list, name_list = [], []
    with zipfile.ZipFile(str(zip_path)) as zip_file:
        for name in zip_file.namelist():
            image_list.append(base64.b64encode(zip_file.read(name)).decode('ascii'))
            # <stem>_<start second>.png - and the stem is base64, which may
            # hold underscores of its own, so the second is read off the end
            section = os.path.splitext(name)[0].rsplit('_', 1)[-1]
            name_list.append(f"Section {section}")
    return image_list, name_list


def get_audio_data(file_path):
    """The duration of an audio file in seconds, to two places, as text."""
    return '%.2f' % librosa.get_duration(path=file_path)


def get_severity(number):
    """'s', 'w' or 'e': the class the stat tiles are coloured by."""
    number = float(number)
    return 's' if number >= 80 else 'w' if number >= 60 else 'e'


def download_from_macaulay(asset_num):
    # the number goes into a URL and a path on disk, so it is a number or nothing
    if not re.fullmatch(r'\d{1,12}', str(asset_num)):
        raise ValidationError('A Macaulay Library asset number is digits only.')
    out_dir = os.path.join(settings.MEDIA_ROOT, 'downloads')
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{asset_num}.wav")
    try:
        response = requests.get(MACAULAY.format(asset_num), stream=True, timeout=20)
    except requests.RequestException as exc:
        raise ValidationError(f"Failed to download {asset_num}: {type(exc).__name__}")
    if response.status_code != 200:
        raise ValidationError(f"Failed to download {asset_num}: response status code {response.status_code}")
    try:
        size = 0
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise ValidationError('That recording is too large to classify.')
                f.write(chunk)
        try:
            duration = librosa.get_duration(path=output_path)
        except Exception:
            raise ValidationError(f"Asset {asset_num} is not audio that can be read.")
        if duration > MAX_SECONDS:
            raise ValidationError(f"Audio segment too long {duration:.0f} s. Maximum duration {MAX_SECONDS} s")
    except ValidationError:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise
    return output_path
