document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const form = document.getElementById('hypnosis-form');
    const generateBtn = document.getElementById('generate-btn');
    const statusDiv = document.getElementById('status');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const audioPreview = document.getElementById('audio-preview');
    const downloadLink = document.getElementById('download-link');
    
    // Voice type selection
    const sampleVoiceRadio = document.getElementById('sample_voice_radio');
    const uploadVoiceRadio = document.getElementById('upload_voice_radio');
    const sampleVoiceSection = document.getElementById('sample_voice_section');
    const uploadVoiceSection = document.getElementById('upload_voice_section');
    
    // Toggle voice selection sections based on radio button selection
    sampleVoiceRadio.addEventListener('change', function() {
        if (this.checked) {
            sampleVoiceSection.classList.remove('d-none');
            uploadVoiceSection.classList.add('d-none');
        }
    });
    
    uploadVoiceRadio.addEventListener('change', function() {
        if (this.checked) {
            sampleVoiceSection.classList.add('d-none');
            uploadVoiceSection.classList.remove('d-none');
        }
    });
    
    // Form submission
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Hide previous results/errors
        resultDiv.classList.add('d-none');
        errorDiv.classList.add('d-none');
        
        // Show loading status
        statusDiv.classList.remove('d-none');
        generateBtn.disabled = true;
        
        // Create FormData object
        const formData = new FormData(form);
        
        // Handle file upload if upload voice is selected
        if (uploadVoiceRadio.checked) {
            const voiceFile = document.getElementById('voice_file').files[0];
            if (!voiceFile) {
                showError('Please select a voice file to upload.');
                return;
            }
            formData.append('voice_file', voiceFile);
        }
        
        // Send AJAX request
        fetch('/generate', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading status
            statusDiv.classList.add('d-none');
            generateBtn.disabled = false;
            
            if (data.error) {
                showError(data.error);
            } else {
                // Show result
                resultDiv.classList.remove('d-none');
                
                // Set audio source
                audioPreview.src = data.download_url;
                
                // Set download link
                downloadLink.href = data.download_url;
                downloadLink.download = data.filename;
            }
        })
        .catch(error => {
            // Hide loading status
            statusDiv.classList.add('d-none');
            generateBtn.disabled = false;
            
            showError('An error occurred while generating the audio. Please try again.');
            console.error('Error:', error);
        });
    });
    
    // Helper function to show error message
    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('d-none');
        statusDiv.classList.add('d-none');
        generateBtn.disabled = false;
    }
});