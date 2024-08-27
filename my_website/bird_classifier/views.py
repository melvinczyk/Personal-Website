from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.urls import reverse
from .models import FileEntry
from .forms import UploadFileForm
from . import file_handler, classify
import hashlib
import datetime
import os
from django.shortcuts import render, redirect


def get_image_accuracy(bird):
    bird_images = {
        'American Crow': {'https://cdn.mos.cms.futurecdn.net/PqHzRT5FnGPSoEUMfmGSWH.jpg': 82.71},
        'American Goldfinch': {
            'https://feederwatch.org/wp-content/uploads/2020/02/37B77335-C469-4D36-A535-059F40176E4E.jpeg': 83.51},
        'American Robin': {
            'https://static.wikia.nocookie.net/birds/images/1/15/Am_robin.jpg/revision/latest?cb=20070731192419': 86.69},
        'Barred Owl': {'https://bpraptorcenter.org/wp-content/uploads/2018/10/Barred-Owl.jpg': 73.71},
        'Blue Jay': {'https://upload.wikimedia.org/wikipedia/commons/f/f4/Blue_jay_in_PP_%2830960%29.jpg': 79.46},
        'Brown-headed Nuthatch': {
            'https://objects.liquidweb.services/images/202312/inat_657788b2b07e05.26918231.jpg': 85.20},
        'Carolina Chickadee': {
            'https://www.nps.gov/chat/learn/nature/images/chickadee.jpg?maxwidth=650&autorotate=false': 76.41},
        'Carolina Wren': {'https://i.natgeofe.com/n/9dfeaf41-ccd8-4234-a59a-e8f107fff63c/carolina-wren_3x4.jpg': 83.39},
        'Cedar Waxwing': {
            'https://upload.wikimedia.org/wikipedia/commons/7/73/Cedar_Waxwing_-_Bombycilla_cedrorum%2C_George_Washington%27s_Birthplace_National_Monument%2C_Colonial_Beach%2C_Virginia_%2839997434862%29.jpg': 79.12},
        'Chipping Sparrow': {'https://www.wintuaudubon.org/wp-content/uploads/2022/05/ChSp-DBogenerX700-1.png': 78.52},
        'Dark-eyed Junco': {
            'https://www.readingeagle.com/wp-content/uploads/migration/2014/03/854df37f69f90bfbc0e463cbfa794349.jpg?w=1024': 80.00},
        'Downy Woodpecker': {'https://www.allaboutbirds.org/guide/assets/photo/60397941-480px.jpg': 81.35},
        'Eastern Bluebird': {'https://nestwatch.org/wp-content/uploads/2019/10/EABL_GenaFlanigen-935x1024.jpg': 90.14},
        'Eastern Kingbird': {'https://upload.wikimedia.org/wikipedia/commons/1/13/Kingbird_Profile.jpg': 83.10},
        'Eastern Phoebe': {'https://www.allaboutbirds.org/guide/assets/photo/301877791-480px.jpg': 95.39},
        'Eastern Towhee': {
            'https://www.thebiofiles.com/img/1/202010/inat_1603124226-5f8dd33184e801.85622326.jpg': 85.82},
        'Empty': {
            'https://static.vecteezy.com/system/resources/previews/003/611/449/non_2x/do-not-make-a-loud-noise-no-speaker-no-sound-icon-free-vector.jpg': 100.00},
        'House Finch': {'https://www.allaboutbirds.org/guide/assets/photo/306327811-480px.jpg': 80.60},
        'Mourning Dove': {'https://inaturalist-open-data.s3.amazonaws.com/photos/513309/large.jpg': 58.00},
        'Myrtle Warbler': {
            'https://wildlife-species.canada.ca/bird-status/statique-static/oiseau-bird/YRWA_Jukka_Jantunen.jpg': 77.33},
        'Northern Cardinal': {
            'https://upload.wikimedia.org/wikipedia/commons/5/5c/Male_northern_cardinal_in_Central_Park_%2852612%29.jpg': 75.29},
        'Northern Flicker': {'https://www.allaboutbirds.org/guide/assets/photo/60403261-480px.jpg': 69.00},
        'Northern Mockingbird': {
            'https://lh5.googleusercontent.com/proxy/1AmgeTOj3a2rnvEenWkMoTVaNpGKAbzLpjep2X6pcLhseYGtdSqHs_ux9v_EkGvJH7jxE4PyauRXSKwBaWJQce2AGtrSo9HG7YAM0bU': 77.94},
        'Pine Warbler': {'https://feederwatch.org/wp-content/uploads/2010/12/pinwar_u228216_11a.jpg': 79.91},
        'Purple Finch': {'https://www.allaboutbirds.org/guide/assets/photo/306334001-480px.jpg': 74.81},
        'Red-bellied Woodpecker': {
            'https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/Red-bellied_Woodpecker-27527.jpg/800px-Red-bellied_Woodpecker-27527.jpg': 75.82},
        'Red-winged Blackbird': {'https://www.galveston.com/red-winged-black-bird-by-rose-pool/': 73.60},
        'Song Sparrow': {
            'https://seasonwatch.umn.edu/sites/seasonwatch.umn.edu/files/styles/folwell_slideshow/public/2022-09/02_song_sparrow_05_04_c_andrea_kingsley_some_rights_reserved_cc-by-nc.jpg?itok=41i9V3wA': 71.00},
        'Tufted Titmouse': {'https://inaturalist-open-data.s3.amazonaws.com/photos/898/large.jpg': 78.27},
        'Unknown': {'https://www.pngitem.com/pimgs/m/527-5273123_bird-question-hd-png-download.png': 0.00},
        'White-breasted Nuthatch': {
            'https://media.audubon.org/nas_birdapi_hero/aud_gbbc-2016_white-breasted-nuthatch_35889_kk_mi_photo-joan-tisdale_adult-male.jpg': 82.41},
    }
    for key, value in bird_images.get(bird).items():
        return key, value


def get_model_stats():
    model_accuracies = {
        'American Crow': 82.71,
        'American Goldfinch': 83.51,
        'American Robin': 86.69,
        'Barred Owl': 73.71,
        'Blue Jay': 79.46,
        'Brown-headed Nuthatch': 85.20,
        'Carolina Chickadee': 76.41,
        'Carolina Wren': 83.39,
        'Cedar Waxwing': 79.12,
        'Chipping Sparrow': 78.52,
        'Dark-eyed Junco': 80.00,
        'Downy Woodpecker': 81.35,
        'Eastern Bluebird': 90.14,
        'Eastern Kingbird': 83.10,
        'Eastern Phoebe': 95.39,
        'Eastern Towhee': 85.82,
        "Empty": 100.00,
        'House Finch': 80.60,
        'Mourning Dove': 58.00,
        'Myrtle Warbler': 77.33,
        'Northern Cardinal': 75.29,
        'Northern Flicker': 69.00,
        'Northern Mockingbird': 77.94,
        'Pine Warbler': 79.91,
        'Purple Finch': 74.81,
        'Red-bellied Woodpecker': 75.82,
        'Red-winged Blackbird': 73.60,
        'Song Sparrow': 71.00,
        'Tufted Titmouse': 78.27,
        'White-breasted Nuthatch': 82.41
    }
    accuracies = list(model_accuracies.values())
    sorted_accuracies = sorted(set(accuracies), reverse=True)
    smallest = min(accuracies)
    second_largest = sorted_accuracies[1]

    average = sum(accuracies) / len(accuracies)

    smallest_bird = next(bird for bird, accuracy in model_accuracies.items() if accuracy == smallest)
    second_largest_bird = next((bird for bird, accuracy in model_accuracies.items() if accuracy == second_largest),
                               None)
    return {
        'smallest': (smallest_bird, smallest),
        'largest': (second_largest_bird, second_largest),
        'average': round(average, 2)
    }


def upload_file(request):
    model_stats = get_model_stats()
    success_message = request.session.pop('success_message', None)
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        text_input = request.POST.get('asset_num')
        honeypot = request.POST.get('honeypot')
        honeypot_download = request.POST.get('honeypot_download')

        download_path = None
        request_error = None

        if honeypot or honeypot_download:
            return HttpResponse("Bot detected", status=403)

        if text_input:
            try:
                download_path = file_handler.download_from_macaulay(text_input)
            except ValidationError as e:
                request_error = str(e)

        if form.is_valid():
            uploaded_file = form.cleaned_data['file']
            print(f"uploaded_file: {uploaded_file}")

            print(f'uploaded_file: {uploaded_file}')
            hasher = hashlib.sha256()
            for chunk in uploaded_file.chunks():
                hasher.update(chunk)
            file_hash = hasher.hexdigest()

            existing_entry = FileEntry.objects.filter(hash=file_hash).first()
            if existing_entry:
                image, accuracy = get_image_accuracy(existing_entry.bird)
                image_list, name_list = file_handler.get_list_spectrograms(existing_entry.spectrogram_path)
                acc_severity = file_handler.get_severity(accuracy)

                print(f'acc_severity: {acc_severity}')
                if existing_entry.bird == 'Unknown':
                    accuracy = '-.-'
                    acc_severity = ''

                request.session['file_hash'] = existing_entry.hash
                request.session['result'] = {
                    'duration': existing_entry.duration,
                    'exists': 'Yes',
                    'num_segments': existing_entry.num_segments,
                    'bird_image': image,
                    'bird': existing_entry.bird,
                    'confidence': existing_entry.confidence,
                    'severity': file_handler.get_severity(existing_entry.confidence),
                    'acc_severity': acc_severity,
                    'image_list': image_list,
                    'image_name_list': name_list,
                    'accuracy': accuracy,
                }
                return redirect(reverse('result') + f'?hash={file_hash}')
            else:
                saved_file, cleaned_name = file_handler.save_uploaded_file(uploaded_file)
                upload_type = 'recording' if uploaded_file.name == 'user_recording' else 'file_upload'
                duration = file_handler.get_audio_data(saved_file)
                bird, confidence, num_segments, spectrogram_path = classify.get_prediction(
                    saved_file, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth')
                )
                zipped_path = file_handler.compress_file(saved_file)
                image, accuracy = get_image_accuracy(bird)
                image_list, name_list = file_handler.get_list_spectrograms(spectrogram_path)

                db_entry = FileEntry(
                    file_location=zipped_path,
                    file_name=cleaned_name,
                    date_time=datetime.datetime.now(),
                    hash=file_hash,
                    bird=bird,
                    confidence=confidence,
                    duration=duration,
                    num_segments=num_segments,
                    spectrogram_path=spectrogram_path,
                    upload_type=upload_type,
                    user_bird=None,
                    correct=None,
                )
                db_entry.save()

                acc_severity = file_handler.get_severity(accuracy)
                if bird == 'Unknown':
                    acc_severity = ''
                    accuracy = '-.-'
                print(f'acc_severity: {acc_severity}')

                request.session['file_hash'] = db_entry.hash
                request.session['result'] = {
                    'duration': db_entry.duration,
                    'exists': 'No',
                    'bird': db_entry.bird,
                    'bird_image': image,
                    'confidence': db_entry.confidence,
                    'num_segments': db_entry.num_segments,
                    'acc_severity': acc_severity,
                    'severity': file_handler.get_severity(confidence),
                    'image_list': image_list,
                    'image_name_list': name_list,
                    'accuracy': accuracy,
                    'success_message': success_message,
                }
                return redirect(reverse('result') + f'?hash={file_hash}')

        elif download_path is not None:

            # TODO: Optimize this

            bird, confidence, num_segments, spectrogram_path = classify.get_prediction(
                download_path, os.path.join(settings.BASE_DIR, 'bird_classifier', 'bird_classifier_best_model.pth')
            )
            duration = file_handler.get_audio_data(download_path)
            image, accuracy = get_image_accuracy(bird)

            with open(download_path, 'rb') as file:
                hasher = hashlib.sha256()
                for chunk in file:
                    hasher.update(chunk)
                file_hash = hasher.hexdigest()

            image_list, name_list = file_handler.get_list_spectrograms(spectrogram_path)
            acc_severity = file_handler.get_severity(accuracy)
            existing_entry = FileEntry.objects.filter(hash=file_hash).first()

            if existing_entry:
                os.remove(download_path)
                request.session['file_hash'] = existing_entry.hash
                request.session['result'] = {
                    'file_name': os.path.basename(download_path),
                    'bird': existing_entry.bird,
                    'confidence': existing_entry.confidence,
                    'num_segments': existing_entry.num_segments,
                    'bird_image': image,
                    'severity': file_handler.get_severity(existing_entry.confidence),
                    'acc_severity': acc_severity,
                    'duration': existing_entry.duration,
                    'accuracy': accuracy,
                    'image_list': image_list,
                    'image_name_list': name_list,
                    'hash': existing_entry.hash,
                    'success_message': success_message,
                }

                return redirect(reverse('result') + f'?hash={existing_entry.hash}')

            db_entry = FileEntry(
                file_location=None,
                file_name=None,
                date_time=datetime.datetime.now(),
                hash=file_hash,
                bird=bird,
                confidence=confidence,
                duration=duration,
                num_segments=num_segments,
                spectrogram_path=spectrogram_path,
                upload_type='macaulay_library',
                user_bird=None,
                correct=None,
            )
            db_entry.save()

            acc_severity = file_handler.get_severity(accuracy)
            if bird == 'Unknown':
                acc_severity = ''
                accuracy = '-.-'
            print(f'acc_severity: {acc_severity}')
            os.remove(download_path)

            request.session['file_hash'] = db_entry.hash
            request.session['result'] = {
                'file_name': os.path.basename(download_path),
                'bird': db_entry.bird,
                'confidence': db_entry.confidence,
                'num_segments': db_entry.num_segments,
                'bird_image': image,
                'severity': file_handler.get_severity(db_entry.confidence),
                'acc_severity': acc_severity,
                'duration': db_entry.duration,
                'accuracy': accuracy,
                'image_list': image_list,
                'image_name_list': name_list,
                'hash': db_entry.hash,
                'success_message': success_message,
            }

            return redirect(reverse('result') + f'?hash={db_entry.hash}')
        else:
            error_message = request_error or form.errors.get('__all__') or form.errors.get('file')
            if error_message:
                messages.error(request, error_message)
            return redirect('upload_file')

    return render(request, 'upload.html', {
        'model_accuracy': model_stats.get('average'),
        'most_accurate_bird': model_stats.get('largest')[1],
        'most_accurate': model_stats.get('largest')[0],
        'least_accurate_bird': model_stats.get('smallest')[1],
        'least_accurate': model_stats.get('smallest')[0],
        'model_severity': file_handler.get_severity(model_stats.get('average')),
        'largest_severity': file_handler.get_severity(model_stats.get('largest')[1]),
        'smallest_severity': file_handler.get_severity(model_stats.get('smallest')[1]),
        'success_message': success_message
    })


def result(request):
    if request.method == 'POST':
        try:
            honeypot = request.POST.get('honeypot')
            hash_value = request.GET.get('hash')
            accuracy = request.POST.get('accuracy')
            species = request.POST.get('species', '')

            if honeypot:
                return HttpResponse("Bot detected", status=403)

            print(f'hash_value: {hash_value}')
            print(f'accuracy: {accuracy}')
            print(f'species: {species}')
            file_entries = FileEntry.objects.filter(hash=hash_value)
            print(f'file_entries: {file_entries}')

            if file_entries.exists():
                print(f'file_entries exists: {file_entries}')
                for file_entry in file_entries:
                    file_entry.correct = (accuracy == 'yes')

                    if accuracy in ['no'] and species:
                        file_entry.user_bird = species
                    elif accuracy == 'yes' or accuracy == 'not-sure':
                        file_entry.user_bird = None
                    file_entry.save()

                    request.session['success_message'] = 'Feedback has successfully been applied'
                    return redirect(reverse('upload_file'))

            else:
                return render(request, 'result.html', {'error': 'No matching file entry found.'})

        except Exception as e:
            print(f"Error in result view: {e}")
            return render(request, 'result.html', {'error': 'An error occurred.'})
    else:
        try:
            # Handle GET request
            if 'result' in request.session:
                result_data = request.session['result']
                return render(request, 'result.html', {'result': result_data})
            else:
                return render(request, 'result.html', {'error': 'No result available.'})
        except Exception as e:
            print(f"Error in result view: {e}")
            return render(request, 'result.html', {'error': 'An error occurred.'})
