from django import forms
from django_clamd.validators import validate_file_infection
from django.core.exceptions import ValidationError


def file_size(value):
    limit = 7 * 1024 * 1024
    if value.size > limit:
        print("Nuh uhh")
        raise ValidationError('File too large. Maximum size is 2 MB')


class UploadFileForm(forms.Form):
    file = forms.FileField(validators=[file_size])

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.content_type.startswith('audio/'):
                raise forms.ValidationError('Please upload a valid audio file.')
        return file

