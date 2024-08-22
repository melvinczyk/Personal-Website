// Menu sidebar

const menuButton = document.getElementById('menu-button');
    const closeMenu = document.getElementById('close-menu');
    const sideMenu = document.getElementById('side-menu');
    const overlay = document.getElementById('overlay');
    const links = document.querySelectorAll('#side-menu .link');

    const toggleMenu = () => {
        sideMenu.classList.toggle('-translate-x-full');
        overlay.classList.toggle('hidden');
    };

    if (menuButton) {
        menuButton.addEventListener('click', toggleMenu);
    }
    closeMenu.addEventListener('click', toggleMenu);
    overlay.addEventListener('click', toggleMenu);

    links.forEach(link => {
        link.addEventListener('click', toggleMenu);
    });

    function displayFileName() {
    const fileInput = document.getElementById('file-upload');
    const fileNameDisplay = document.getElementById('file-name-display');
        if (fileInput.files.length > 0) {
            fileNameDisplay.textContent = fileInput.files[0].name;
        } else {
            fileNameDisplay.textContent = 'No file chosen';
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
    const startRecordingButton = document.getElementById('start-recording');
    const stopRecordingButton = document.getElementById('stop-recording');
    const audioPlayback = document.getElementById('audio-playback');
    const recordedAudioInput = document.getElementById('recorded-audio');

    let mediaRecorder;
    let recordedChunks = [];

    startRecordingButton.addEventListener('click', async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        recordedChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recordedChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const recordedBlob = new Blob(recordedChunks, { type: 'audio/wav' });
            const recordedUrl = URL.createObjectURL(recordedBlob);
            audioPlayback.src = recordedUrl;
            audioPlayback.classList.remove('hidden');
            recordedAudioInput.value = recordedUrl;
        };

        mediaRecorder.start();
        startRecordingButton.disabled = true;
        stopRecordingButton.disabled = false;
    });

    stopRecordingButton.addEventListener('click', () => {
        mediaRecorder.stop();
        startRecordingButton.disabled = false;
        stopRecordingButton.disabled = true;
    });
});