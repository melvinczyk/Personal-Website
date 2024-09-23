import os
from django.core.files.storage import default_storage
from django.conf import settings
import mimetypes
import base64
import librosa
import requests
import zipfile
from pydub import AudioSegment
from PIL import  Image
import io
import re
import datetime
from django.core.exceptions import ValidationError


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


def compress_spectrograms(encoded_name):
    output_zip_path = os.path.join(settings.MEDIA_ROOT, 'spectrograms',f'{encoded_name}.zip')

    input_dir = os.path.join(settings.BASE_DIR, 'bird_classifier', 'temp_mels')
    pattern = re.compile(rf"^{encoded_name}_\d+")
    with zipfile.ZipFile(output_zip_path, 'w') as zip_file:
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if pattern.match(file):
                    full_path = os.path.join(root, file)
                    zip_file.write(full_path, os.path.relpath(full_path, input_dir))

    print(f"All files compressed to {output_zip_path}")
    return output_zip_path

def compress_file(wav_file_path):
    directory, filename = os.path.split(wav_file_path)
    filename_no_ext = os.path.splitext(filename)[0]
    flac_path = os.path.join(directory, f"{filename_no_ext}.flac")
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


def mp3_to_wav(file_path):
    try:
        sound = AudioSegment.from_file(file_path)
        wav_path = file_path.replace(os.path.splitext(file_path)[1], 'test.wav')
        sound.export(wav_path, format="wav")
        return wav_path
    except Exception as e:
        print(f"Error converting MP3 to WAV: {e}")
        return None


def save_uploaded_file(uploaded_file):
    print(f"save_uploaded_file: uploaded_file: {uploaded_file}")
    directory = 'uploads/originals/'
    recorded_directory = 'uploads/recordings'
    filename, ext = os.path.splitext(uploaded_file.name)
    print(f"save_uploaded_file: filename: {filename}")
    encoded_name = base64_encode_filename(filename) + ext
    if filename == 'user_recording':
        encoded_name = base64_encode_filename(str(datetime.datetime.now())) + ext
        file_path = os.path.join(recorded_directory, encoded_name)
    else:
        file_path = os.path.join(directory, encoded_name)

    cleaned_name = clean_filename(filename)

    print(f"save_uploaded_file: file_path: {file_path}")

    saved_path = default_storage.save(file_path, uploaded_file)
    print(f"save_uploaded_file: saved_path: {saved_path}")

    print(f"save_uploaded_file: file size before saving {uploaded_file.size}")
    saved_file_path = os.path.join(settings.MEDIA_ROOT, saved_path)
    print(f"save_uploaded_file: saved_file_path: {saved_file_path}")
    print(f"save_uploaded_file: file size: {os.path.getsize(saved_file_path)}")

    #duration = get_audio_data(saved_file_path)
    #print(f"save_uploaded_file: duration:{duration}")

    mime_type, _ = mimetypes.guess_type(saved_file_path)
    print(f"save_uploaded_file: mine_type: {mime_type}")


    if mime_type not in ['audio/wav', 'audio/x-wav']:
        try:
            print("Converting file to WAV format...")
            audio = AudioSegment.from_file(saved_file_path)
            wav_path = os.path.splitext(saved_file_path)[0] + '.wav'
            print(f"save_uploaded_file: wav_path: {wav_path}")

            audio.export(wav_path, format='wav')
            print(f"save_uploaded_file: deleting path: {saved_file_path}")
            return wav_path, cleaned_name
        except Exception as e:
            print(f"Error converting file to WAV: {e}")
            return None, cleaned_name
    else:
        print(f"File saved at: saved_file_path: {saved_file_path}")
        return saved_file_path, cleaned_name



def get_list_spectrograms(file_path):
    tmp_path = os.path.join(settings.MEDIA_ROOT, 'spectrograms', 'tmp')
    image_list = []
    name_list = []
    with zipfile.ZipFile(file_path, 'r') as zip_file:
        zip_file.extractall(tmp_path)
    for root, dirs, files in os.walk(tmp_path):
        for file in files:
            full_path = os.path.join(root, file)
            with open(full_path, 'rb') as img_file:
                image = Image.open(io.BytesIO(img_file.read()))
                image_list.append(image_to_64(image))
                filename = os.path.basename(full_path)
                parts = filename.split('_')
                section = os.path.splitext(parts[1])[0]
                name_list.append(f"Section {section}")
            os.remove(full_path)
    return image_list, name_list

def macaulay_list_spectrograms():
    pass
def image_to_64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_audio_data(file_path):
    print(f"get_audio_data: file_path: {file_path}")
    print(f"get_audio_data: file size: {os.path.getsize(file_path)}")
    mime_type, _ = mimetypes.guess_type(file_path)
    print(f"get_audio_data: mine_type: {mime_type}")
    signal, sr = librosa.load(file_path, sr=None)
    duration = librosa.get_duration(y=signal, sr=sr)
    print(f"get_audio_data: duration: {duration}")
    return '%.2f'%duration

def get_severity(number):
    if float(number) >= 80:
        severity = 'secondary'
    elif 80 > float(number) >= 60:
        severity = 'warning'
    else:
        severity = 'error'
    return  severity

def download_from_macaulay(asset_num):
    url = f"https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{asset_num}"
    output_path = os.path.join(settings.MEDIA_ROOT, 'downloads', f"{asset_num}.wav")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        signal, sr = librosa.load(output_path)
        duration = librosa.get_duration(y=signal, sr=sr)
        if duration > 90:
            raise ValidationError(f"Audio segment too long {duration} s. Maximum duration 90 s")
        return output_path
    else:
        raise ValidationError(f"Failed to download {asset_num}: response status code {response.status_code}")


def download_birds(asset_num, bird):
    url = f"https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{asset_num}"
    output_path = os.path.join('..', 'static', 'audio', f"{bird}.mp3")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"File downloaded successfully and saved to {output_path}")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")


if __name__ == "__main__":
    download_birds(619644408, 'titmouse')