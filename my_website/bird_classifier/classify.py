import matplotlib
matplotlib.use('Agg')  # Set backend to 'Agg' for non-GUI operations
import numpy as np
import librosa
import librosa.display
import matplotlib.pyplot as plt
from PIL import Image
import torch
import torch.nn as nn
from torchvision import transforms
import noisereduce as nr
from collections import Counter
from scipy.io import wavfile
from pathlib import Path
from django.conf import settings

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

bird_dict = {
    0: "american crow",
    1: "american goldfinch",
    2: "american robin",
    3: "barred owl",
    4: "blue jay",
    5: "brown-headed nuthatch",
    6: "carolina chickadee",
    7: "carolina wren",
    8: "cedar waxwing",
    9: "chipping sparrow",
    10: "dark-eyed junco",
    11: "downy woodpecker",
    12: "eastern bluebird",
    13: "eastern kingbird",
    14: "eastern phoebe",
    15: "eastern towhee",
    16: "house finch",
    17: "mourning dove",
    18: "myrtle warbler",
    19: "northern cardinal",
    20: "northern flicker",
    21: "northern mockingbird",
    22: "pine warbler",
    23: "purple finch",
    24: "red-bellied woodpecker",
    25: "red-winged blackbird",
    26: "song sparrow",
    27: "tufted titmouse",
    28: "white-breasted nuthatch"
}

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

    # Convert the canvas to an image
    image = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
    image = Image.frombytes('RGBA', (width, height), image.tobytes())
    image = image.convert('RGB')
    image = image.resize((224, 224))

    plt.close(fig)
    image.save('temp.png')
    return image

def classify_segment(model, signal, sr, threshold=0.7):
    spectrogram = save_mel_spectrogram(signal, sr)

    transform = transforms.Compose([
        transforms.ToTensor(),
    ])

    with torch.no_grad():
        image = transform(spectrogram).unsqueeze(0)
        output = model(image)
        probabilities = torch.nn.functional.softmax(output, dim=1)
        confidence, predicted = torch.max(probabilities, 1)
        confidence = confidence.item()

        bird_name = bird_dict.get(predicted.item(), "Unknown")
        return bird_name, confidence * 100

def test_model(wav_file, model_path, threshold=0.7):
    model = BirdClassifierCNN(num_classes=29)
    model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    model.eval()

    signal, sr = librosa.load(wav_file, sr=16000)

    segment_duration = 10
    segment_samples = segment_duration * sr

    segments = []
    for i in range(0, len(signal), segment_samples):
        segment = signal[i:i + segment_samples]

        if len(segment) < segment_samples:
            padding = np.zeros(segment_samples - len(segment))
            segment = np.concatenate((segment, padding))

        segments.append(segment)

    predictions = []
    confidences = []
    for segment in segments:
        bird_name, confidence = classify_segment(model, segment, sr, threshold)
        predictions.append(bird_name)
        confidences.append(confidence)

    most_common_prediction = Counter(predictions).most_common(1)[0][0]
    avg_confidence = np.mean([conf for pred, conf in zip(predictions, confidences) if pred == most_common_prediction])

    return most_common_prediction, avg_confidence

def reduce_noise(file_path):
    signal, sr = librosa.load(file_path)
    reduce = nr.reduce_noise(y=signal, sr=sr)
    reduce = (reduce * 32767).astype('int16')
    output_path = settings.MEDIA_ROOT + f"/{Path(file_path).stem}_clean.wav"
    wavfile.write(output_path, sr, reduce)
    return output_path

if __name__ == "__main__":
    wav_file = "./chipping_sparrow_clean.wav"
    model_path = "best_model.pth"
    bird_name, confidence = test_model(wav_file, model_path)
    print(f"Predicted bird: {bird_name} with confidence: {confidence:.2f}%")
