from django import forms
import librosa
from django.core.exceptions import ValidationError


def file_size(value):
    limit = 7 * 1024 * 1024
    if value.size > limit:
        print("Nuh uhh")
        raise ValidationError('File too large. Maximum size is 7 MB')
    signal, sr = librosa.load(value)
    duration = librosa.get_duration(y=signal, sr=sr)

    if duration < 4:
        print(f"File too short: {duration}")
        raise ValidationError(f"Inputted file too short: {duration} seconds. Minimum duration: 5 seconds")

class UploadFileForm(forms.Form):
    file = forms.FileField(validators=[file_size])

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.content_type.startswith('audio/'):
                raise forms.ValidationError('Please upload a valid audio file.')
        return file

