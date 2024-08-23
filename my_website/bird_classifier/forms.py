from django import forms
import librosa
from django.core.exceptions import ValidationError


def file_size(value):
    limit = 200 * 1024 * 1024
    if value.size > limit:
        print("Nuh uhh")
        raise ValidationError('File too large. Maximum size is 7 MB')

class UploadFileForm(forms.Form):
    file = forms.FileField(validators=[file_size])

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.content_type.startswith('audio/'):
                raise forms.ValidationError('Please upload a valid audio file.')
        return file

