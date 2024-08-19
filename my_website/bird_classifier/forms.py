from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.content_type.startswith('audio/'):
                raise forms.ValidationError('Please upload a valid audio file.')
        return file