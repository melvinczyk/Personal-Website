import hashlib
import os

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from . import file_handler
from .forms import UploadFileForm
from .models import FileEntry

MODEL_PATH = os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth')

# species -> (reference photo, the model's accuracy on that class)
BIRDS = {
    'American Crow': ('https://cdn.mos.cms.futurecdn.net/PqHzRT5FnGPSoEUMfmGSWH.jpg', 82.71),
    'American Goldfinch': ('https://feederwatch.org/wp-content/uploads/2020/02/37B77335-C469-4D36-A535-059F40176E4E.jpeg', 83.51),
    'American Robin': ('https://static.wikia.nocookie.net/birds/images/1/15/Am_robin.jpg/revision/latest?cb=20070731192419', 86.69),
    'Barred Owl': ('https://bpraptorcenter.org/wp-content/uploads/2018/10/Barred-Owl.jpg', 73.71),
    'Blue Jay': ('https://upload.wikimedia.org/wikipedia/commons/f/f4/Blue_jay_in_PP_%2830960%29.jpg', 79.46),
    'Brown-headed Nuthatch': ('https://objects.liquidweb.services/images/202312/inat_657788b2b07e05.26918231.jpg', 85.20),
    'Carolina Chickadee': ('https://www.nps.gov/chat/learn/nature/images/chickadee.jpg?maxwidth=650&autorotate=false', 76.41),
    'Carolina Wren': ('https://i.natgeofe.com/n/9dfeaf41-ccd8-4234-a59a-e8f107fff63c/carolina-wren_3x4.jpg', 83.39),
    'Cedar Waxwing': ('https://upload.wikimedia.org/wikipedia/commons/7/73/Cedar_Waxwing_-_Bombycilla_cedrorum%2C_George_Washington%27s_Birthplace_National_Monument%2C_Colonial_Beach%2C_Virginia_%2839997434862%29.jpg', 79.12),
    'Chipping Sparrow': ('https://www.wintuaudubon.org/wp-content/uploads/2022/05/ChSp-DBogenerX700-1.png', 78.52),
    'Dark-eyed Junco': ('https://www.readingeagle.com/wp-content/uploads/migration/2014/03/854df37f69f90bfbc0e463cbfa794349.jpg?w=1024', 80.00),
    'Downy Woodpecker': ('https://www.allaboutbirds.org/guide/assets/photo/60397941-480px.jpg', 81.35),
    'Eastern Bluebird': ('https://nestwatch.org/wp-content/uploads/2019/10/EABL_GenaFlanigen-935x1024.jpg', 90.14),
    'Eastern Kingbird': ('https://upload.wikimedia.org/wikipedia/commons/1/13/Kingbird_Profile.jpg', 83.10),
    'Eastern Phoebe': ('https://www.allaboutbirds.org/guide/assets/photo/301877791-480px.jpg', 95.39),
    'Eastern Towhee': ('https://www.thebiofiles.com/img/1/202010/inat_1603124226-5f8dd33184e801.85622326.jpg', 85.82),
    'Empty': ('https://static.vecteezy.com/system/resources/previews/003/611/449/non_2x/do-not-make-a-loud-noise-no-speaker-no-sound-icon-free-vector.jpg', 100.00),
    'House Finch': ('https://www.allaboutbirds.org/guide/assets/photo/306327811-480px.jpg', 80.60),
    'Mourning Dove': ('https://inaturalist-open-data.s3.amazonaws.com/photos/513309/large.jpg', 58.00),
    'Myrtle Warbler': ('https://wildlife-species.canada.ca/bird-status/statique-static/oiseau-bird/YRWA_Jukka_Jantunen.jpg', 77.33),
    'Northern Cardinal': ('https://upload.wikimedia.org/wikipedia/commons/5/5c/Male_northern_cardinal_in_Central_Park_%2852612%29.jpg', 75.29),
    'Northern Flicker': ('https://www.allaboutbirds.org/guide/assets/photo/60403261-480px.jpg', 69.00),
    'Northern Mockingbird': ('https://lh5.googleusercontent.com/proxy/1AmgeTOj3a2rnvEenWkMoTVaNpGKAbzLpjep2X6pcLhseYGtdSqHs_ux9v_EkGvJH7jxE4PyauRXSKwBaWJQce2AGtrSo9HG7YAM0bU', 77.94),
    'Pine Warbler': ('https://feederwatch.org/wp-content/uploads/2010/12/pinwar_u228216_11a.jpg', 79.91),
    'Purple Finch': ('https://www.allaboutbirds.org/guide/assets/photo/306334001-480px.jpg', 74.81),
    'Red-bellied Woodpecker': ('https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Red-bellied_Woodpecker-27527.jpg/800px-Red-bellied_Woodpecker-27527.jpg', 75.82),
    'Red-winged Blackbird': ('https://www.galveston.com/red-winged-black-bird-by-rose-pool/', 73.60),
    'Song Sparrow': ('https://seasonwatch.umn.edu/sites/seasonwatch.umn.edu/files/styles/folwell_slideshow/public/2022-09/02_song_sparrow_05_04_c_andrea_kingsley_some_rights_reserved_cc-by-nc.jpg?itok=41i9V3wA', 71.00),
    'Tufted Titmouse': ('https://inaturalist-open-data.s3.amazonaws.com/photos/898/large.jpg', 78.27),
    'Unknown': ('https://www.pngitem.com/pimgs/m/527-5273123_bird-question-hd-png-download.png', 0.00),
    'White-breasted Nuthatch': ('https://media.audubon.org/nas_birdapi_hero/aud_gbbc-2016_white-breasted-nuthatch_35889_kk_mi_photo-joan-tisdale_adult-male.jpg', 82.41),
}


def _model_stats():
    """The headline numbers for the upload page.

    'Empty' is silence, which the model gets right every time, so it counts
    towards the average but is never named as the most accurate bird.
    'Unknown' is the model declining to answer and counts towards nothing.
    """
    scores = {bird: acc for bird, (_, acc) in BIRDS.items() if bird != 'Unknown'}
    average = round(sum(scores.values()) / len(scores), 2)
    del scores['Empty']
    best, worst = max(scores, key=scores.get), min(scores, key=scores.get)
    return {
        'model_accuracy': average,
        'model_severity': file_handler.get_severity(average),
        'most_accurate': best,
        'most_accurate_bird': scores[best],
        'largest_severity': file_handler.get_severity(scores[best]),
        'least_accurate': worst,
        'least_accurate_bird': scores[worst],
        'smallest_severity': file_handler.get_severity(scores[worst]),
    }


def _sha256(chunks):
    hasher = hashlib.sha256()
    for chunk in chunks:
        hasher.update(chunk)
    return hasher.hexdigest()


def _classify(path, file_hash, **fields):
    """Run the model over a wav and file the answer under its hash."""
    from . import classify  # lazy: pulls in torch only when actually classifying
    duration = file_handler.get_audio_data(path)
    bird, confidence, num_segments, spectrogram_path = classify.get_prediction(path, MODEL_PATH)
    return FileEntry.objects.create(
        hash=file_hash, bird=bird, confidence=confidence, duration=duration,
        num_segments=num_segments, spectrogram_path=spectrogram_path, **fields)


def _show(request, entry):
    """Put an entry's result in the session and send the visitor to it."""
    image, accuracy = BIRDS.get(entry.bird, BIRDS['Unknown'])
    unknown = entry.bird == 'Unknown'
    image_list, name_list = file_handler.get_list_spectrograms(entry.spectrogram_path)
    request.session['file_hash'] = entry.hash
    request.session['result'] = {
        'bird': entry.bird,
        'bird_image': image,
        'confidence': entry.confidence,
        'severity': file_handler.get_severity(entry.confidence),
        'accuracy': '-.-' if unknown else accuracy,
        'acc_severity': 'e' if unknown else file_handler.get_severity(accuracy),
        'duration': entry.duration,
        'num_segments': entry.num_segments,
        'image_list': image_list,
        'image_name_list': name_list,
    }
    return redirect(reverse('result') + f'?hash={entry.hash}')


def _from_upload(uploaded_file):
    file_hash = _sha256(uploaded_file.chunks())
    entry = FileEntry.objects.filter(hash=file_hash).first()
    if entry:
        return entry
    uploaded_file.seek(0)
    saved_file, cleaned_name = file_handler.save_uploaded_file(uploaded_file)
    if saved_file is None:
        raise ValidationError('That file could not be read as audio.')
    entry = _classify(
        saved_file, file_hash, file_name=cleaned_name,
        upload_type='recording' if cleaned_name == 'user_recording' else 'file_upload')
    # the wav is gone once it is zipped, so this has to follow the classifying
    entry.file_location = file_handler.compress_file(saved_file)
    entry.save(update_fields=['file_location'])
    return entry


def _from_macaulay(asset_num):
    path = file_handler.download_from_macaulay(asset_num)
    try:
        with open(path, 'rb') as fh:
            file_hash = _sha256(iter(lambda: fh.read(65536), b''))
        # the hash is asked after first: a recording already on file is not
        # worth running the model over a second time
        return (FileEntry.objects.filter(hash=file_hash).first()
                or _classify(path, file_hash, upload_type='macaulay_library'))
    finally:
        if os.path.exists(path):
            os.remove(path)


def upload_file(request):
    if request.method != 'POST':
        return render(request, 'bird_classifier_upload.html', {
            **_model_stats(),
            'success_message': request.session.pop('success_message', None),
        })

    if request.POST.get('honeypot') or request.POST.get('honeypot_download'):
        return HttpResponse("Bot detected", status=403)

    form = UploadFileForm(request.POST, request.FILES)
    asset_num = request.POST.get('asset_num', '').strip()
    try:
        if form.is_valid():
            return _show(request, _from_upload(form.cleaned_data['file']))
        if asset_num:
            return _show(request, _from_macaulay(asset_num))
        error = form.errors.get('__all__') or form.errors.get('file')
    except ValidationError as exc:
        error = '; '.join(exc.messages)
    if error:
        messages.error(request, error)
    return redirect('upload_file')


def result(request):
    if request.method != 'POST':
        if 'result' in request.session:
            return render(request, 'result.html', {'result': request.session['result']})
        return render(request, 'result.html', {'error': 'No result available.'})

    if request.POST.get('honeypot'):
        return HttpResponse("Bot detected", status=403)

    entry = FileEntry.objects.filter(hash=request.GET.get('hash')).first()
    if entry is None:
        return render(request, 'result.html', {'error': 'No matching file entry found.'})

    verdict = request.POST.get('accuracy')
    species = request.POST.get('species', '')
    entry.correct = verdict == 'yes'
    if verdict == 'no' and species:
        entry.user_bird = species[:255]
    elif verdict in ('yes', 'not-sure'):
        entry.user_bird = None
    entry.save()

    request.session['success_message'] = 'Feedback has successfully been applied'
    return redirect('upload_file')
