import os
import torch
import numpy as np
import librosa
import matplotlib
import matplotlib.pyplot as plt
import librosa.display
from PIL import Image
from torchvision import transforms
from torch.utils.data import Dataset
from torchvision import models
from torchvision.models import ResNet18_Weights
from django.conf import settings
from scipy.io import wavfile
import noisereduce as nr

matplotlib.use('Agg')
class BirdDataset(Dataset):
    def __init__(self, root_dir, transform=None):
        self.root_dir = root_dir
        self.transform = transform
        self.classes = sorted(os.listdir(root_dir))
        self.class_to_idx = {cls_name: idx for idx, cls_name in enumerate(self.classes)}
        self.file_paths = []
        self.labels = []

        for label, bird_class in enumerate(self.classes):
            class_dir = os.path.join(root_dir, bird_class)
            for file_name in os.listdir(class_dir):
                if file_name.endswith('.png'):
                    self.file_paths.append(os.path.join(class_dir, file_name))
                    self.labels.append(label)

    def __len__(self):
        return len(self.file_paths)

    def __getitem__(self, idx):
        img_path = self.file_paths[idx]
        image = Image.open(img_path).convert('RGB')
        label = self.labels[idx]

        if self.transform:
            image = self.transform(image)

        return image, label

data_transforms = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

class BirdClassifierCNN(torch.nn.Module):
    def __init__(self, num_classes):
        super(BirdClassifierCNN, self).__init__()
        self.model = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        num_ftrs = self.model.fc.in_features
        self.model.fc = torch.nn.Linear(num_ftrs, num_classes)

    def forward(self, x):
        return self.model(x)


def save_mel_spectrogram(signal, directory, sr):
    params = {
        'n_fft': 1024,
        'hop_length': 1024,
        'n_mels': 128,
        'win_length': 1024,
        'window': 'hann',
        'htk': True,
        'fmin': 1400,
        'fmax': sr / 2
    }

    fig, ax = plt.subplots(1, 1, figsize=(6, 6), frameon=False)
    ax.set_axis_off()

    S = librosa.feature.melspectrogram(y=signal, sr=sr, **params)
    S_dB = librosa.power_to_db(S ** 2, ref=np.max)
    librosa.display.specshow(S_dB, fmin=params['fmin'], ax=ax)
    fig.savefig(directory)
    plt.close(fig)


def process_audio_file(file_path, output_dir, size):
    signal, sr = librosa.load(file_path, sr=16000)
    step = (size['desired'] - size['stride']) * sr
    mel_spectrogram_paths = []

    for start in range(0, len(signal) - size['desired'] * sr + 1, step):
        end = start + size['desired'] * sr
        segment = signal[start:end]

        if len(segment) < size['desired'] * sr:
            segment = np.pad(segment, (0, size['desired'] * sr - len(segment)), mode='constant')

        mel_path = os.path.join(output_dir, f"segment_{start // sr}.png")
        if not os.path.exists(mel_path):
            save_mel_spectrogram(segment, mel_path, sr)
        mel_spectrogram_paths.append(mel_path)

    if len(signal) >= size['minimum'] * sr:
        start = max(0, len(signal) - size['desired'] * sr)
        segment = signal[start:]

        if len(segment) < size['desired'] * sr:
            segment = np.pad(segment, (0, size['desired'] * sr - len(segment)), mode='constant')

        mel_path = os.path.join(output_dir, f"segment_{start // sr}.png")
        if not os.path.exists(mel_path):
            save_mel_spectrogram(segment, mel_path, sr)
        mel_spectrogram_paths.append(mel_path)

    return mel_spectrogram_paths



def classify_audio_file(file_path, model, transform, device):
    model.eval()
    mel_spectrogram_paths = process_audio_file(file_path, os.path.join(settings.BASE_DIR, 'bird_classifier', 'temp_mels'),
                                               size={'desired': 5, 'minimum': 4, 'stride': 0, 'name': 5})
    predictions = []

    for mel_path in mel_spectrogram_paths:
        image = Image.open(mel_path).convert('RGB')
        image = transform(image).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(image)
            probabilities = torch.softmax(output, dim=1).cpu().numpy()[0]
            top_probs, top_classes = torch.topk(torch.tensor(probabilities), k=5)
            top_probs = top_probs.numpy()
            top_classes = top_classes.numpy()

            predictions.append({
                'predicted_class': torch.argmax(output, dim=1).item(),
                'probabilities': probabilities,
                'top_probs': top_probs,
                'top_classes': top_classes
            })

    return predictions, mel_spectrogram_paths


def load_model(model_path, num_classes, device):
    model = BirdClassifierCNN(num_classes=num_classes).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    return model


def reduce_noise(file_path):
    signal, rate = librosa.load(file_path)
    reduce = nr.reduce_noise(y=signal, sr=rate)
    reduce = (reduce * 32767).astype('int16')
    wavfile.write(file_path, rate, reduce)


def get_prediction(file_path, model_path):
    for file in os.listdir(os.path.join(settings.BASE_DIR, 'bird_classifier', 'temp_mels')):
        path = os.path.join(settings.BASE_DIR, 'bird_classifier', 'temp_mels', file)
        if os.path.isfile(path):
            os.remove(path)
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
        16: 'empty',
        17: "house finch",
        18: "mourning dove",
        19: "myrtle warbler",
        20: "northern cardinal",
        21: "northern flicker",
        22: "northern mockingbird",
        23: "pine warbler",
        24: "purple finch",
        25: "red-bellied woodpecker",
        26: "red-winged blackbird",
        27: "song sparrow",
        28: "tufted titmouse",
        29: "white-breasted nuthatch",
    }

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = len(bird_dict)
    model = load_model(model_path, num_classes, device)

    reduce_noise(file_path)

    predictions, mel_spectrogram_paths = classify_audio_file(file_path, model, data_transforms, device)

    num_segments = 0
    for i, (pred, mel_path) in enumerate(zip(predictions, mel_spectrogram_paths)):
        num_segments += 1
        predicted_class = pred['predicted_class']
        probabilities = pred['probabilities']
        top_probs = pred['top_probs']
        top_classes = pred['top_classes']

        print(f"Segment {i}:")
        print(
            f"  Predicted class: {bird_dict[predicted_class]} with confidence {probabilities[predicted_class] * 100:.2f}%")

        print("  Other guesses:")
        for prob, cls in zip(top_probs, top_classes):
            if cls != predicted_class:
                print(f"    {bird_dict[cls]}: {prob * 100:.2f}%")

    final_prediction = max(set(p['predicted_class'] for p in predictions),
                           key=lambda x: sum(p['predicted_class'] == x for p in predictions))
    final_confidence = np.max([p['probabilities'][p['predicted_class']] for p in predictions if
                               p['predicted_class'] == final_prediction]) * 100
    predicted_bird = bird_dict[final_prediction]
    if final_confidence < 40.0:
        predicted_bird = 'Unknown'
        final_confidence = 100 - final_confidence
    print(f"Final prediction for the audio file: {predicted_bird} with confidence {final_confidence:.2f}%")
    return predicted_bird, '%.2f'%final_confidence, num_segments

