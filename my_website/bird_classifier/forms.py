from django import forms
import librosa
from django.core.exceptions import ValidationError


def file_size(value):
    limit = 5 * 1024 * 1024
    file_size_mb = value.size / (1024 * 1024)
    if value.size > limit:
        raise ValidationError(f'File uploaded: {file_size_mb:.2f} MB. Maximum size is 5 MB.')


class UploadFileForm(forms.Form):
    file = forms.FileField(validators=[file_size])

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.content_type.startswith('audio/'):
                raise forms.ValidationError('Please upload a valid audio file.')
        return file

