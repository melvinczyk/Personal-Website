import os
import torch
import numpy as np
import librosa
import matplotlib
import matplotlib.pyplot as plt
import librosa.display
from PIL import Image
from torchvision import transforms
from torchvision import models
from torchvision.models import ResNet18_Weights
from django.core.exceptions import ValidationError
from scipy.io import wavfile
import noisereduce as nr
from . import file_handler
matplotlib.use('Agg')

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
    want = size['desired'] * sr
    starts = list(range(0, len(signal) - want + 1, (size['desired'] - size['stride']) * sr))
    # and one more window laid against the end, so the tail is not thrown away
    if len(signal) >= size['minimum'] * sr:
        starts.append(max(0, len(signal) - want))
    filename = os.path.splitext(os.path.basename(file_path))[0]
    os.makedirs(output_dir, exist_ok=True)

    mel_spectrogram_paths = []
    for start in dict.fromkeys(starts):          # the tail may be a window already drawn
        segment = signal[start:start + want]
        if len(segment) < want:
            segment = np.pad(segment, (0, want - len(segment)), mode='constant')
        mel_path = os.path.join(output_dir, f"{filename}_{start // sr}.png")
        if not os.path.exists(mel_path):
            save_mel_spectrogram(segment, mel_path, sr)
        mel_spectrogram_paths.append(mel_path)
    return mel_spectrogram_paths


def classify_audio_file(file_path, model, transform, device):
    model.eval()
    mel_spectrogram_paths = process_audio_file(file_path, file_handler.MELS_DIR,
                                               size={'desired': 5, 'minimum': 4, 'stride': 0})
    predictions = []

    for mel_path in mel_spectrogram_paths:
        image = transform(Image.open(mel_path).convert('RGB')).unsqueeze(0).to(device)
        with torch.no_grad():
            probabilities = torch.softmax(model(image), dim=1).cpu().numpy()[0]
        predictions.append({'predicted_class': int(probabilities.argmax()),
                            'probabilities': probabilities})

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


BIRDS = (
    "American Crow", "American Goldfinch", "American Robin", "Barred Owl",
    "Blue Jay", "Brown-headed Nuthatch", "Carolina Chickadee", "Carolina Wren",
    "Cedar Waxwing", "Chipping Sparrow", "Dark-eyed Junco", "Downy Woodpecker",
    "Eastern Bluebird", "Eastern Kingbird", "Eastern Phoebe", "Eastern Towhee",
    "Empty", "House Finch", "Mourning Dove", "Myrtle Warbler",
    "Northern Cardinal", "Northern Flicker", "Northern Mockingbird",
    "Pine Warbler", "Purple Finch", "Red-bellied Woodpecker",
    "Red-winged Blackbird", "Song Sparrow", "Tufted Titmouse",
    "White-breasted Nuthatch",
)

_model = None


def _get_model(model_path, device):
    """The network, loaded once per process rather than once per upload."""
    global _model
    if _model is None:
        _model = load_model(model_path, len(BIRDS), device)
    return _model


def get_prediction(file_path, model_path):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = _get_model(model_path, device)

    reduce_noise(file_path)
    predictions, _ = classify_audio_file(file_path, model, data_transforms, device)
    stem = os.path.splitext(os.path.basename(file_path))[0]
    if not predictions:
        for path in file_handler.mel_files(stem):
            os.remove(path)
        raise ValidationError('That recording is too short to classify - it needs at least four seconds.')

    # the class most segments agreed on, at the best confidence any of them had
    votes = [p['predicted_class'] for p in predictions]
    final_prediction = max(set(votes), key=votes.count)
    final_confidence = max(p['probabilities'][final_prediction] for p in predictions
                           if p['predicted_class'] == final_prediction) * 100
    predicted_bird = BIRDS[final_prediction]
    if final_confidence < 60.0:
        predicted_bird = 'Unknown'
        final_confidence = 100 - final_confidence

    zipped_image_path = file_handler.compress_spectrograms(stem)
    return predicted_bird, '%.2f' % final_confidence, len(predictions), zipped_image_path
