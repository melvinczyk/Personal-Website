import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from PIL import Image
import torch
import torch.nn as nn
from torchvision import transforms


class BirdClassifierCNN(nn.Module):
    def __init__(self, num_classes=29):
        super(BirdClassifierCNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2, padding=0)
        self.fc1 = nn.Linear(128 * 28 * 28, 512)
        self.fc2 = nn.Linear(512, num_classes)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        x = self.pool(self.relu(self.conv1(x)))
        x = self.pool(self.relu(self.conv2(x)))
        x = self.pool(self.relu(self.conv3(x)))
        x = x.view(-1, 128 * 28 * 28)
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.fc2(x)
        return x


def save_mel_spectrogram(signal, sr):
    params = {
        'n_fft': 1024,
        'hop_length': 512,
        'n_mels': 128,
        'win_length': 1024,
        'window': 'hann',
        'htk': True,
        'fmin': 1400,
        'fmax': sr / 2
    }

    S = librosa.feature.melspectrogram(y=signal, sr=sr, **params)
    S_dB = librosa.power_to_db(S, ref=np.max)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=100, frameon=False)
    ax.set_axis_off()
    librosa.display.specshow(S_dB, sr=sr, fmin=params['fmin'], ax=ax)

    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    print(f"Canvas dimensions: width={width}, height={height}")

    image = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)

    print(f"Raw image data size: {image.size}")

    num_channels = 4
    print(f"Number of channels: {num_channels}")
    image = Image.frombytes('RGBA', (width, height), image.tobytes())
    image = image.convert('RGB')

    image = image.resize((224, 224))

    plt.close(fig)
    return image


def test_model(wav_file, model_path):
    model = BirdClassifierCNN(num_classes=29)
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu'), weights_only=True))
    model.eval()
    signal, sr = librosa.load(wav_file, sr=16000, duration=10)
    spectrogram = save_mel_spectrogram(signal, sr)

    transform = transforms.Compose([
        transforms.ToTensor(),
    ])

    with torch.no_grad():
        image = transform(spectrogram).unsqueeze(0)
        output = model(image)
        _, predicted = torch.max(output, 1)
        return predicted.item()


if __name__ == "__main__":
    wav_file = "./43850.wav"
    model_path = "best_model.pth"
    class_index = test_model(wav_file, model_path)
    print(f"Predicted class index: {class_index}")
