import librosa
from matplotlib import pyplot as plt
import numpy as np


def generate_spectrogram(file_path):
    plt.figure(figsize=(6, 4))
    signal, sr = librosa.load(file_path)
    mel_spec = librosa.power_to_db(np.abs(librosa.stft(y=signal, n_fft=2048, hop_length=512)))
    librosa.display.specshow(mel_spec, fmax=8000, x_axis='time', y_axis='mel', cmap='magma')
    plt.title("American Crow")
    plt.savefig('./')