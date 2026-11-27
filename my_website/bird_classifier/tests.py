import importlib.util
import io
import math
import shutil
import struct
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from . import file_handler, views
from .models import FileEntry


def _wav(seconds, rate=16000):
    """A warbling tone: not a bird, but audio the whole pipeline will take."""
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b''.join(
            struct.pack('<h', int(9000 * math.sin(2 * math.pi * (3000 + i % 700) * i / rate)))
            for i in range(rate * seconds)))
    return buf.getvalue()


class HelperTests(TestCase):
    def test_model_stats(self):
        stats = views._model_stats()
        self.assertEqual(stats['model_accuracy'], 79.95)
        self.assertEqual((stats['most_accurate'], stats['most_accurate_bird']), ('Eastern Phoebe', 95.39))
        self.assertEqual((stats['least_accurate'], stats['least_accurate_bird']), ('Mourning Dove', 58.0))

    def test_severity(self):
        self.assertEqual([file_handler.get_severity(n) for n in ('85.2', 80, 60, 59.9)],
                         ['s', 's', 'w', 'e'])

    def test_asset_number_must_be_digits(self):
        for bad in ('../../etc/passwd', '12a', '', '1' * 13):
            with self.assertRaises(ValidationError):
                file_handler.download_from_macaulay(bad)

    def test_section_label_survives_underscores_in_the_stem(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'a.zip')
            with zipfile.ZipFile(path, 'w') as out:
                out.writestr('YV9i_Yw==_15.png', b'x')
            self.assertEqual(file_handler.get_list_spectrograms(path), (['eA=='], ['Section 15']))

    def test_pages_render(self):
        self.assertEqual(self.client.get('/bird_classifier/upload/').status_code, 200)
        self.assertContains(self.client.get('/bird_classifier/results/'), 'No result available.')

    def test_bad_asset_number_is_reported_not_raised(self):
        response = self.client.post('/bird_classifier/upload/', {'asset_num': '../x'})
        self.assertRedirects(response, '/bird_classifier/upload/')
        self.assertIn('digits only', str(list(get_messages(response.wsgi_request))[0]))


@unittest.skipUnless(importlib.util.find_spec('torch'), 'torch is not installed here')
class UploadTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.addCleanup(shutil.rmtree, self.media, True)

    def _upload(self, seconds):
        return self.client.post('/bird_classifier/upload/', {
            'file': SimpleUploadedFile('clip.wav', _wav(seconds), content_type='audio/wav')})

    def test_upload_classify_and_feedback(self):
        response = self._upload(12)
        entry = FileEntry.objects.get()
        self.assertRedirects(response, f'/bird_classifier/results/?hash={entry.hash}')
        self.assertEqual(entry.num_segments, 3)
        self.assertEqual(len(self.client.session['result']['image_list']), 3)
        self.assertEqual(self.client.get(response['Location']).status_code, 200)

        # only the two zips are kept: no wav, no loose spectrograms
        kept = sorted(p.suffix for p in Path(self.media).rglob('*') if p.is_file())
        self.assertEqual(kept, ['.zip', '.zip'])
        self.assertEqual(file_handler.mel_files(Path(str(entry.file_location)).stem), [])

        # the same bytes again are answered from the record, not re-classified
        self._upload(12)
        self.assertEqual(FileEntry.objects.count(), 1)

        self.client.post(response['Location'], {'accuracy': 'no', 'species': 'Blue Jay'})
        entry.refresh_from_db()
        self.assertEqual((entry.correct, entry.user_bird), (False, 'Blue Jay'))

    def test_too_short_is_an_error_message(self):
        response = self._upload(2)
        self.assertRedirects(response, '/bird_classifier/upload/')
        self.assertIn('too short', str(list(get_messages(response.wsgi_request))[0]))
        self.assertEqual(FileEntry.objects.count(), 0)
