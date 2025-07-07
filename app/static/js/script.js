document.addEventListener('DOMContentLoaded', function() {
    // Store the current routine ID if we're editing an existing routine
    let currentRoutineId = '';

    // Function to refresh the routines list
    function refreshRoutinesList() {
        fetch('/routines')
            .then(response => response.json())
            .then(routines => {
                const routinesList = document.getElementById('routines-list');

                // Clear the current list
                routinesList.innerHTML = '';

                if (routines.length === 0) {
                    // No routines yet
                    const row = document.createElement('tr');
                    row.innerHTML = '<td colspan="4" class="text-center">No saved routines yet.</td>';
                    routinesList.appendChild(row);
                } else {
                    // Add each routine to the list
                    routines.forEach(routine => {
                        const row = document.createElement('tr');
                        row.setAttribute('data-routine-id', routine.id);

                        // Format the date
                        const createdDate = routine.created_at.split('T')[0];

                        row.innerHTML = `
                            <td>${routine.name}</td>
                            <td>${routine.language}</td>
                            <td>${createdDate}</td>
                            <td>
                                <button class="btn btn-sm btn-primary load-routine" data-routine-id="${routine.id}">Load</button>
                                <button class="btn btn-sm btn-success regenerate-routine" data-routine-id="${routine.id}">Regenerate</button>
                                <button class="btn btn-sm btn-danger delete-routine" data-routine-id="${routine.id}">Delete</button>
                                <a href="/download/${routine.output_filename}" class="btn btn-sm btn-info">Download</a>
                            </td>
                        `;

                        routinesList.appendChild(row);
                    });

                    // Add event listeners to the new buttons
                    addRoutineButtonListeners();
                }
            })
            .catch(error => {
                console.error('Error fetching routines:', error);
            });
    }

    // Function to add event listeners to routine buttons
    function addRoutineButtonListeners() {
        // Load routine buttons
        document.querySelectorAll('.load-routine').forEach(button => {
            button.addEventListener('click', function() {
                const routineId = this.getAttribute('data-routine-id');
                loadRoutine(routineId);
            });
        });

        // Regenerate routine buttons
        document.querySelectorAll('.regenerate-routine').forEach(button => {
            button.addEventListener('click', function() {
                const routineId = this.getAttribute('data-routine-id');
                regenerateRoutine(routineId);
            });
        });

        // Delete routine buttons
        document.querySelectorAll('.delete-routine').forEach(button => {
            button.addEventListener('click', function() {
                const routineId = this.getAttribute('data-routine-id');
                deleteRoutine(routineId);
            });
        });
    }

    // Function to load a routine into the form
    function loadRoutine(routineId) {
        fetch(`/routines/${routineId}`)
            .then(response => response.json())
            .then(routine => {
                // Set the form fields
                document.getElementById('name').value = routine.name;
                document.getElementById('text').value = routine.text;
                document.getElementById('language').value = routine.language;

                // Set the voice type
                if (routine.voice_type === 'sample') {
                    document.getElementById('sample_voice_radio').checked = true;
                    document.getElementById('sample_voice').value = routine.voice_id;
                    sampleVoiceSection.classList.remove('d-none');
                    uploadVoiceSection.classList.add('d-none');
                } else {
                    document.getElementById('upload_voice_radio').checked = true;
                    sampleVoiceSection.classList.add('d-none');
                    uploadVoiceSection.classList.remove('d-none');
                }

                // Set the current routine ID
                currentRoutineId = routineId;

                // Scroll to the form
                form.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(error => {
                console.error('Error loading routine:', error);
                errorDiv.textContent = 'Error loading routine. Please try again.';
                errorDiv.classList.remove('d-none');
            });
    }

    // Function to regenerate a routine
    function regenerateRoutine(routineId) {
        // First load the routine
        fetch(`/routines/${routineId}`)
            .then(response => response.json())
            .then(routine => {
                // Create a FormData object with the routine data
                const formData = new FormData();
                formData.append('routine_id', routineId);
                formData.append('name', routine.name);
                formData.append('text', routine.text);
                formData.append('language', routine.language);
                formData.append('voice_type', routine.voice_type);

                if (routine.voice_type === 'sample') {
                    formData.append('sample_voice', routine.voice_id);
                } else {
                    // Can't regenerate with uploaded voice if we don't have the file
                    errorDiv.textContent = 'Cannot regenerate with uploaded voice. Please load the routine and upload a new voice file.';
                    errorDiv.classList.remove('d-none');
                    return;
                }

                // Show status
                statusDiv.classList.remove('d-none');

                // Send the request to generate
                fetch('/generate', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    // Hide status
                    statusDiv.classList.add('d-none');

                    if (data.error) {
                        // Show error
                        errorDiv.textContent = data.error;
                        errorDiv.classList.remove('d-none');
                    } else {
                        // Show result
                        audioPreview.src = data.download_url;
                        downloadLink.href = data.download_url;
                        resultDiv.classList.remove('d-none');

                        // Refresh the routines list
                        refreshRoutinesList();

                        // Scroll to result
                        resultDiv.scrollIntoView({ behavior: 'smooth' });
                    }
                })
                .catch(error => {
                    // Hide status
                    statusDiv.classList.add('d-none');

                    // Show error
                    errorDiv.textContent = 'An error occurred while communicating with the server. Please try again.';
                    errorDiv.classList.remove('d-none');
                    console.error('Error:', error);
                });
            })
            .catch(error => {
                console.error('Error loading routine for regeneration:', error);
                errorDiv.textContent = 'Error loading routine for regeneration. Please try again.';
                errorDiv.classList.remove('d-none');
            });
    }

    // Function to delete a routine
    function deleteRoutine(routineId) {
        if (confirm('Are you sure you want to delete this routine?')) {
            fetch(`/routines/${routineId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Refresh the routines list
                    refreshRoutinesList();

                    // If we were editing this routine, clear the form
                    if (currentRoutineId === routineId) {
                        form.reset();
                        currentRoutineId = '';
                    }
                } else {
                    errorDiv.textContent = data.error || 'Error deleting routine. Please try again.';
                    errorDiv.classList.remove('d-none');
                }
            })
            .catch(error => {
                console.error('Error deleting routine:', error);
                errorDiv.textContent = 'Error deleting routine. Please try again.';
                errorDiv.classList.remove('d-none');
            });
        }
    }

    // Initial setup: add event listeners to routine buttons and refresh the list
    addRoutineButtonListeners();
    refreshRoutinesList();

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

        // Add the routine ID if we're editing an existing routine
        if (currentRoutineId) {
            formData.append('routine_id', currentRoutineId);
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

                // Update the current routine ID
                currentRoutineId = data.routine_id;

                // Refresh the routines list
                refreshRoutinesList();

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
