const menuButton = document.getElementById('menu-button');
const sideMenu = document.getElementById('side-menu');
const overlay = document.getElementById('overlay');

menuButton.addEventListener('click', () => {
    sideMenu.classList.toggle('-translate-x-full');
    overlay.classList.toggle('hidden');
});

overlay.addEventListener('click', () => {
    sideMenu.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
});

// Audio recording logic
let mediaRecorder;
let audioChunks = [];

const startRecordingButton = document.getElementById('start-recording');
const stopRecordingButton = document.getElementById('stop-recording');
const audioPreview = document.getElementById('audio-preview');
const audioDataInput = document.getElementById('audio_data');

startRecordingButton.addEventListener('click', async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };

    mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        audioPreview.src = audioUrl;
        audioDataInput.value = audioBlob;

        audioChunks = []; // Clear the chunks for the next recording
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
