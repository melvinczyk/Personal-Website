from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import FileEntry
from .forms import UploadFileForm
from . import file_handler, classify
import hashlib
import datetime
import os


def get_image(bird):
    bird_images = {
        'american crow': 'https://cdn.mos.cms.futurecdn.net/PqHzRT5FnGPSoEUMfmGSWH.jpg',
        'american goldfinch': 'https://feederwatch.org/wp-content/uploads/2020/02/37B77335-C469-4D36-A535-059F40176E4E.jpeg',
        'american robin': 'https://static.wikia.nocookie.net/birds/images/1/15/Am_robin.jpg/revision/latest?cb=20070731192419',
        'barred owl': 'https://bpraptorcenter.org/wp-content/uploads/2018/10/Barred-Owl.jpg',
        'blue jay': 'https://upload.wikimedia.org/wikipedia/commons/f/f4/Blue_jay_in_PP_%2830960%29.jpg',
        'brown-headed nuthatch': 'https://objects.liquidweb.services/images/202312/inat_657788b2b07e05.26918231.jpg',
        'carolina chickadee': 'https://www.nps.gov/chat/learn/nature/images/chickadee.jpg?maxwidth=650&autorotate=false',
        'carolina wren': 'https://i.natgeofe.com/n/9dfeaf41-ccd8-4234-a59a-e8f107fff63c/carolina-wren_3x4.jpg',
        'cedar waxwing': 'https://upload.wikimedia.org/wikipedia/commons/7/73/Cedar_Waxwing_-_Bombycilla_cedrorum%2C_George_Washington%27s_Birthplace_National_Monument%2C_Colonial_Beach%2C_Virginia_%2839997434862%29.jpg',
        'chipping sparrow': 'https://www.wintuaudubon.org/wp-content/uploads/2022/05/ChSp-DBogenerX700-1.png',
        'dark-eyed junco': 'https://www.readingeagle.com/wp-content/uploads/migration/2014/03/854df37f69f90bfbc0e463cbfa794349.jpg?w=1024',
        'downy woodpecker': 'https://www.allaboutbirds.org/guide/assets/photo/60397941-480px.jpg',
        'eastern bluebird': 'https://nestwatch.org/wp-content/uploads/2019/10/EABL_GenaFlanigen-935x1024.jpg',
        'eastern kingbird': 'https://upload.wikimedia.org/wikipedia/commons/1/13/Kingbird_Profile.jpg',
        'eastern phoebe': 'https://www.allaboutbirds.org/guide/assets/photo/301877791-480px.jpg',
        'eastern towhee': 'https://www.thebiofiles.com/img/1/202010/inat_1603124226-5f8dd33184e801.85622326.jpg',
        'house finch': 'https://www.allaboutbirds.org/guide/assets/photo/306327811-480px.jpg',
        'mourning dove': 'https://inaturalist-open-data.s3.amazonaws.com/photos/513309/large.jpg',
        'myrtle warbler': 'https://wildlife-species.canada.ca/bird-status/statique-static/oiseau-bird/YRWA_Jukka_Jantunen.jpg',
        'northern cardinal': 'https://upload.wikimedia.org/wikipedia/commons/5/5c/Male_northern_cardinal_in_Central_Park_%2852612%29.jpg',
        'northern flicker': 'https://www.allaboutbirds.org/guide/assets/photo/60403261-480px.jpg',
        'northern mockingbird': 'https://lh5.googleusercontent.com/proxy/1AmgeTOj3a2rnvEenWkMoTVaNpGKAbzLpjep2X6pcLhseYGtdSqHs_ux9v_EkGvJH7jxE4PyauRXSKwBaWJQce2AGtrSo9HG7YAM0bU',
        'pine warbler': 'https://feederwatch.org/wp-content/uploads/2010/12/pinwar_u228216_11a.jpg',
        'purple finch': 'https://www.allaboutbirds.org/guide/assets/photo/306334001-480px.jpg',
        'red-bellied woodpecker': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Red-bellied_Woodpecker-27527.jpg/800px-Red-bellied_Woodpecker-27527.jpg',
        'red-winged blackbird': 'https://www.galveston.com/red-winged-black-bird-by-rose-pool/',
        'song sparrow': 'https://seasonwatch.umn.edu/sites/seasonwatch.umn.edu/files/styles/folwell_slideshow/public/2022-09/02_song_sparrow_05_04_c_andrea_kingsley_some_rights_reserved_cc-by-nc.jpg?itok=41i9V3wA',
        'tufted titmouse': 'https://inaturalist-open-data.s3.amazonaws.com/photos/898/large.jpg',
        'white-breasted nuthatch': 'https://media.audubon.org/nas_birdapi_hero/aud_gbbc-2016_white-breasted-nuthatch_35889_kk_mi_photo-joan-tisdale_adult-male.jpg',
    }
    return bird_images.get(bird)


def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        text_input = request.POST.get('asset_num')
        download_path = None
        request_error = None

        if text_input:
            try:
                download_path = file_handler.download_from_macaulay(text_input)
            except ValidationError as e:
                request_error = str(e)


        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            print(f"uploaded_file: {uploaded_file}")

            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            existing_entry = FileEntry.objects.filter(hash=file_hash).first()
            if existing_entry:
                image = get_image(existing_entry.bird)
                return render(request, 'result.html', {
                    'file_name': existing_entry.file_name,
                    'file_location': existing_entry.file_location,
                    'file_length': existing_entry.audio_length,
                    'exists': 'Yes',
                    'bird_image': image,
                    'bird': existing_entry.bird,
                    'confidence': existing_entry.confidence,
                    'hash': existing_entry.hash,
                    'spectrogram_path': existing_entry.spectrogram_path,
                })
            else:
                saved_file, cleaned_name = file_handler.save_uploaded_file(uploaded_file)
                if uploaded_file.name == 'user_recording':
                    upload_type = 'recording'
                else:
                    upload_type = 'file_upload'
                duration = file_handler.get_audio_data(saved_file)
                bird, confidence, num_segments = classify.get_prediction(saved_file, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth'))
                zipped_path = file_handler.compress_file(saved_file)
                image = get_image(bird)
                filename = os.path.basename(saved_file)
                spectrogram_path = file_handler.compress_spectrograms(os.path.splitext(filename)[0])

                db_entry = FileEntry(
                    file_location=zipped_path,
                    file_name=cleaned_name,
                    date_time=datetime.datetime.now(),
                    hash=file_hash,
                    bird=bird,
                    confidence=confidence,
                    audio_length=duration,
                    num_segments=num_segments,
                    spectrogram_path=spectrogram_path,
                    upload_type=upload_type
                )
                db_entry.save()
                return render(request, 'result.html', {
                    'file_name': db_entry.file_name,
                    'file_location': db_entry.file_location,
                    'file_length': db_entry.audio_length,
                    'exists': 'No',
                    'bird': db_entry.bird,
                    'bird_image': image,
                    'confidence': db_entry.confidence,
                    'hash': db_entry.hash,
                    'spectrogram_path': db_entry.spectrogram_path,
                    'num_segments': db_entry.num_segments,
                })

        elif download_path is not None:
            bird, confidence, num_segments = classify.get_prediction(download_path, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth'))
            duration = file_handler.get_audio_data(download_path)
            os.remove(download_path)
            image = get_image(bird)
            db_entry = FileEntry(
                file_location=None,
                file_name=None,
                date_time=datetime.datetime.now(),
                hash=None,
                bird=bird,
                confidence=confidence,
                audio_length=duration,
                num_segments=num_segments,
                spectrogram_path=None,
                upload_type='macaulay_library'
            )
            db_entry.save()
            return render(request, 'result.html', {
                'file_name': os.path.basename(download_path),
                'bird': db_entry.bird,
                'confidence': db_entry.confidence,
                'num_segments': db_entry.num_segments,
                'bird_image': image
            })

        else:
            if request_error is not None:
                error_message = request_error
            else:
                error_message = form.errors.get('__all__') or form.errors.get('file')
            if error_message:
                messages.error(request, error_message)
            return redirect('upload_file')

    return render(request, 'upload.html')
