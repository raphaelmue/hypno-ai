document.addEventListener('DOMContentLoaded', function() {
    // Toggle voice selection sections based on radio button selection
    const sampleVoiceRadio = document.getElementById('sample_voice_radio');
    const uploadVoiceRadio = document.getElementById('upload_voice_radio');
    const sampleVoiceSection = document.getElementById('sample_voice_section');
    const uploadVoiceSection = document.getElementById('upload_voice_section');

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

    // Handle form submission
    const form = document.getElementById('hypnosis-form');
    const statusDiv = document.getElementById('status');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const audioPreview = document.getElementById('audio-preview');
    const downloadLink = document.getElementById('download-link');
    const generateBtn = document.getElementById('generate-btn');

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Hide previous results and errors
        resultDiv.classList.add('d-none');
        errorDiv.classList.add('d-none');
        
        // Show status
        statusDiv.classList.remove('d-none');
        
        // Disable the generate button
        generateBtn.disabled = true;
        
        // Create FormData object
        const formData = new FormData(form);
        
        // If using uploaded voice, add the file
        if (uploadVoiceRadio.checked) {
            const voiceFile = document.getElementById('voice_file').files[0];
            if (voiceFile) {
                formData.append('voice_file', voiceFile);
            }
        }
        
        // Send the request
        fetch('/generate', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Hide status
            statusDiv.classList.add('d-none');
            
            // Enable the generate button
            generateBtn.disabled = false;
            
            if (data.error) {
                // Show error
                errorDiv.textContent = data.error;
                errorDiv.classList.remove('d-none');
            } else {
                // Show result
                audioPreview.src = data.download_url;
                downloadLink.href = data.download_url;
                resultDiv.classList.remove('d-none');
                
                // Scroll to result
                resultDiv.scrollIntoView({ behavior: 'smooth' });
            }
        })
        .catch(error => {
            // Hide status
            statusDiv.classList.add('d-none');
            
            // Enable the generate button
            generateBtn.disabled = false;
            
            // Show error
            errorDiv.textContent = 'An error occurred while communicating with the server. Please try again.';
            errorDiv.classList.remove('d-none');
            console.error('Error:', error);
        });
    });
});