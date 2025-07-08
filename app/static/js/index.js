document.addEventListener('DOMContentLoaded', function() {
    // Check TTS model status when page loads
    checkTTSModelStatus();

    // Add event listeners to routine buttons
    function addRoutineButtonListeners() {
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

    // Function to poll for task status
    function pollTaskStatus(taskId, button, originalText) {
        // Poll the server for task status
        fetch(`/task/${taskId}?redirect=true`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    // Re-enable button
                    button.disabled = false;
                    button.textContent = originalText;

                    // Show error
                    alert(`Error: ${data.error}`);
                } else if (data.status === "completed" && data.result) {
                    // Re-enable button
                    button.disabled = false;
                    button.textContent = originalText;

                    // Show success message and redirect to the appropriate page
                    alert('Routine regenerated successfully!');
                    if (data.result.redirect_url) {
                        window.location.href = data.result.redirect_url;
                    } else {
                        window.location.reload();
                    }
                } else if (data.status === "failed") {
                    // Re-enable button
                    button.disabled = false;
                    button.textContent = originalText;

                    // Show error
                    alert(data.error || "An error occurred while generating the audio. Please try again.");
                } else {
                    // Task is still processing, update button text with more details
                    if (data.status === "processing") {
                        button.textContent = "Processing...";
                    }

                    // Continue polling after a delay
                    setTimeout(() => pollTaskStatus(taskId, button, originalText), 2000);
                }
            })
            .catch(error => {
                // Re-enable button
                button.disabled = false;
                button.textContent = originalText;

                // Show error
                alert('An error occurred while communicating with the server. Please try again.');
                console.error('Error:', error);
            });
    }

    // Function to regenerate a routine
    function regenerateRoutine(routineId) {
        if (confirm('Are you sure you want to regenerate this routine? This will create a new audio file.')) {
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
                    formData.append('redirect', 'true'); // Redirect to list page after regeneration

                    if (routine.voice_type === 'sample') {
                        formData.append('sample_voice', routine.voice_id);
                    } else {
                        // Can't regenerate with uploaded voice if we don't have the file
                        alert('Cannot regenerate with uploaded voice. Please edit the routine and upload a new voice file.');
                        return;
                    }

                    // Show loading indicator or disable button
                    const button = document.querySelector(`.regenerate-routine[data-routine-id="${routineId}"]`);
                    const originalText = button.textContent;
                    button.disabled = true;
                    button.textContent = 'Starting...';

                    // Send the request to start the task
                    fetch('/generate', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            // Re-enable button
                            button.disabled = false;
                            button.textContent = originalText;

                            // Show error
                            alert(`Error: ${data.error}`);
                        } else if (data.task_id) {
                            // Start polling for task status
                            button.textContent = 'Generating...';
                            pollTaskStatus(data.task_id, button, originalText);
                        }
                    })
                    .catch(error => {
                        // Re-enable button
                        button.disabled = false;
                        button.textContent = originalText;

                        // Show error
                        alert('An error occurred while communicating with the server. Please try again.');
                        console.error('Error:', error);
                    });
                })
                .catch(error => {
                    console.error('Error loading routine for regeneration:', error);
                    alert('Error loading routine for regeneration. Please try again.');
                });
        }
    }

    // Function to delete a routine
    function deleteRoutine(routineId) {
        if (confirm('Are you sure you want to delete this routine? This cannot be undone.')) {
            fetch(`/routines/${routineId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Remove the row from the table or refresh the page
                    const row = document.querySelector(`tr[data-routine-id="${routineId}"]`);
                    if (row) {
                        row.remove();
                    }

                    // If no more routines, show the "no routines" message
                    const routinesList = document.getElementById('routines-list');
                    if (routinesList.children.length === 0) {
                        const row = document.createElement('tr');
                        row.innerHTML = '<td colspan="4" class="text-center">No saved routines yet. <a href="/routine/new">Create your first routine</a>.</td>';
                        routinesList.appendChild(row);
                    }
                } else {
                    alert(data.error || 'Error deleting routine. Please try again.');
                }
            })
            .catch(error => {
                console.error('Error deleting routine:', error);
                alert('Error deleting routine. Please try again.');
            });
        }
    }

    // Initialize by adding event listeners to routine buttons
    addRoutineButtonListeners();

    // Add event listener to the download TTS model button
    const downloadModelBtn = document.getElementById('download-tts-model-btn');
    if (downloadModelBtn) {
        downloadModelBtn.addEventListener('click', downloadTTSModel);
    }

    // Function to check TTS model status
    function checkTTSModelStatus() {
        fetch('/tts-model/status')
            .then(response => response.json())
            .then(data => {
                updateTTSModelStatusUI(data);

                // If the model is downloading, poll for status updates
                if (data.status === 'downloading') {
                    setTimeout(checkTTSModelStatus, 5000); // Check every 5 seconds
                }
            })
            .catch(error => {
                console.error('Error checking TTS model status:', error);
                // Show error in the status container
                const statusContainer = document.getElementById('tts-model-status-container');
                const statusMessage = document.getElementById('tts-model-status-message');
                if (statusContainer && statusMessage) {
                    statusContainer.style.display = 'block';
                    statusContainer.className = 'alert alert-danger mb-4';
                    statusMessage.textContent = 'Error checking TTS model status. Please refresh the page.';
                }
            });
    }

    // Function to update the UI based on TTS model status
    function updateTTSModelStatusUI(data) {
        const statusContainer = document.getElementById('tts-model-status-container');
        const statusMessage = document.getElementById('tts-model-status-message');
        const downloadBtn = document.getElementById('download-tts-model-btn');

        if (!statusContainer || !statusMessage || !downloadBtn) return;

        statusContainer.style.display = 'block';

        switch (data.status) {
            case 'not_downloaded':
                statusContainer.className = 'alert alert-warning mb-4';
                statusMessage.textContent = 'TTS model is not downloaded. You need to download it to generate audio.';
                downloadBtn.style.display = 'inline-block';
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Download TTS Model';
                break;
            case 'downloading':
                statusContainer.className = 'alert alert-info mb-4';
                statusMessage.textContent = 'TTS model is downloading. This may take several minutes...';
                downloadBtn.style.display = 'none';
                break;
            case 'downloaded':
                statusContainer.className = 'alert alert-success mb-4';
                statusMessage.textContent = 'TTS model is downloaded and ready to use.';
                downloadBtn.style.display = 'none';
                break;
            case 'failed':
                statusContainer.className = 'alert alert-danger mb-4';
                statusMessage.textContent = `TTS model download failed: ${data.error || 'Unknown error'}`;
                downloadBtn.style.display = 'inline-block';
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Retry Download';
                break;
            default:
                statusContainer.className = 'alert alert-secondary mb-4';
                statusMessage.textContent = `TTS model status: ${data.status}`;
                downloadBtn.style.display = 'none';
        }
    }

    // Function to download the TTS model
    function downloadTTSModel() {
        const downloadBtn = document.getElementById('download-tts-model-btn');
        if (downloadBtn) {
            downloadBtn.disabled = true;
            downloadBtn.textContent = 'Starting download...';
        }

        fetch('/tts-model/download', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'downloading') {
                // Update UI to show downloading status
                updateTTSModelStatusUI({
                    status: 'downloading',
                    error: null
                });

                // Start polling for status updates
                setTimeout(checkTTSModelStatus, 5000); // Check every 5 seconds
            } else {
                // Update UI with the current status
                updateTTSModelStatusUI(data);
            }
        })
        .catch(error => {
            console.error('Error starting TTS model download:', error);
            // Show error in the status container
            updateTTSModelStatusUI({
                status: 'failed',
                error: 'Error starting download. Please try again.'
            });

            // Re-enable the download button
            if (downloadBtn) {
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Retry Download';
            }
        });
    }
});
