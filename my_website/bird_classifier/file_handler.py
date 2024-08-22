import os
from django.core.files.storage import default_storage
from django.conf import settings
import mimetypes
import base64
import librosa
import requests
import zipfile
from pydub import AudioSegment
import re


def clean_filename(file):
    cleaned_name = re.sub(r'[^\w\.-]', '_', file)
    cleaned_name = cleaned_name.strip('_')
    if not cleaned_name:
        cleaned_name = '_'
    return cleaned_name


def base64_encode_filename(filename):
    byte_data = filename.encode('utf-8')
    encoded_name = base64.urlsafe_b64encode(byte_data).decode('utf-8')
    return encoded_name


def compress_file(wav_file_path):
    directory, filename = os.path.split(wav_file_path)
    filename_no_ext = os.path.splitext(filename)[0]
    print(f"filename_no_ext: {filename_no_ext}")
    flac_path = os.path.join(directory, f"{filename_no_ext}.flac")
    print(f"flac path: {flac_path}")
    audio = AudioSegment.from_file(wav_file_path)
    audio.export(flac_path, format='flac')
    print(f"exported flac: {flac_path}")
    zip_filename = f"{filename_no_ext}.zip"
    zip_file_path = os.path.join(directory, zip_filename)

    with zipfile.ZipFile(zip_file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(flac_path, arcname=filename)
    os.remove(wav_file_path)
    os.remove(flac_path)
    print(f"Compressed to: {zip_file_path}")
    return zip_file_path


def save_uploaded_file(uploaded_file):
    directory = 'uploads/originals/'
    filename, ext = os.path.splitext(uploaded_file.name)
    encoded_name = base64_encode_filename(filename) + ext
    file_path = os.path.join(directory, encoded_name)

    cleaned_name = clean_filename(filename)

    print(f"{file_path}")

    saved_path = default_storage.save(file_path, uploaded_file)
    print(f"{saved_path}")
    saved_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)

    mime_type, _ = mimetypes.guess_type(saved_file_path)

    if mime_type != 'audio/wav' and mime_type != 'audio/x-wav':
        audio = AudioSegment.from_file(saved_file_path)
        wav_path = os.path.splitext(saved_file_path)[0] + '.wav'
        audio.export(wav_path, format='wav')
        os.remove(saved_file_path)
        print(f"{wav_path}")
        return wav_path
    print(f"{saved_file_path}")
    return saved_file_path, cleaned_name


def get_audio_data(file_path):
    signal, sr = librosa.load(file_path, sr=None)
    duration = librosa.get_duration(y=signal, sr=sr)
    return signal, sr, duration


def download_from_macaulay(asset_num):
    url = f"https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{asset_num}"
    output_path = os.path.join(settings.MEDIA_ROOT, 'downloads', f"{asset_num}.flac")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"File downloaded successfully and saved to {output_path}")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")

def download_birds(asset_num, bird):
    url = f"https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{asset_num}"
    output_path = os.path.join('..', 'static', 'audio', f"{bird}.flac")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"File downloaded successfully and saved to {output_path}")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")


if __name__ == "__main__":
    download_birds(622572493, 'american_crow')