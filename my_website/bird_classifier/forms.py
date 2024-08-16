from django import forms

class UploadFileForm(forms.Form):
    file = forms.FileField()
    location = forms.CharField(max_length=255, required=False)