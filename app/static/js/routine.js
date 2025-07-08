document.addEventListener("DOMContentLoaded", function () {
    // Check TTS model status when page loads
    checkTTSModelStatus();

    // Toggle voice selection sections based on radio button selection
    const sampleVoiceRadio = document.getElementById("sample_voice_radio");
    const uploadVoiceRadio = document.getElementById("upload_voice_radio");
    const sampleVoiceSection = document.getElementById("sample_voice_section");
    const uploadVoiceSection = document.getElementById("upload_voice_section");

    sampleVoiceRadio.addEventListener("change", function () {
        if (this.checked) {
            sampleVoiceSection.classList.remove("d-none");
            uploadVoiceSection.classList.add("d-none");
        }
    });

    uploadVoiceRadio.addEventListener("change", function () {
        if (this.checked) {
            sampleVoiceSection.classList.add("d-none");
            uploadVoiceSection.classList.remove("d-none");
        }
    });

    // Handle form submission
    const form = document.getElementById("hypnosis-form");
    const statusDiv = document.getElementById("status");
    const resultDiv = document.getElementById("result");
    const errorDiv = document.getElementById("error");
    const audioPreview = document.getElementById("audio-preview");
    const downloadLink = document.getElementById("download-link");
    const generateBtn = document.getElementById("generate-btn");

    // Function to poll for task status
    function pollTaskStatus(taskId, redirectToList = false, pollCount = 0) {
        // Get UI elements for status updates
        const statusMessage = statusDiv.querySelector("div.d-flex div:last-child");
        const statusProgress = document.getElementById("status-progress");
        const statusDetails = document.getElementById("status-details");

        // Update progress based on poll count (simulated progress)
        let progress = 0;
        if (pollCount < 5) {
            progress = 10 + (pollCount * 5); // 10-35%: Starting
            statusDetails.textContent = "Starting the generation process...";
        } else if (pollCount < 10) {
            progress = 35 + ((pollCount - 5) * 5); // 35-60%: Processing text
            statusDetails.textContent = "Processing text and generating speech segments...";
        } else if (pollCount < 15) {
            progress = 60 + ((pollCount - 10) * 5); // 60-85%: Combining audio
            statusDetails.textContent = "Combining audio segments with pauses...";
        } else {
            progress = 85 + (Math.min(pollCount - 15, 3) * 5); // 85-100%: Finalizing
            statusDetails.textContent = "Finalizing your audio file...";
        }

        // Update progress bar
        if (statusProgress) {
            statusProgress.style.width = `${progress}%`;
        }

        // Construct the URL with redirect parameter if needed
        let url = `/task/${taskId}`;
        if (redirectToList) {
            url += "?redirect=true";
        }

        // Poll the server for task status
        fetch(url)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    // Hide status
                    statusDiv.classList.add("d-none");

                    // Enable the generate button
                    generateBtn.disabled = false;

                    // Show error
                    errorDiv.textContent = data.error;
                    errorDiv.classList.remove("d-none");
                } else if (data.status === "completed" && data.result) {
                    // Set progress to 100% before hiding
                    if (statusProgress) {
                        statusProgress.style.width = "100%";
                    }
                    if (statusDetails) {
                        statusDetails.textContent = "Audio generation complete!";
                    }

                    // Short delay to show the completed progress
                    setTimeout(() => {
                        // Hide status
                        statusDiv.classList.add("d-none");

                        // Enable the generate button
                        generateBtn.disabled = false;

                        // Show result
                        audioPreview.src = data.result.download_url;
                        downloadLink.href = data.result.download_url + "?download=true";
                        resultDiv.classList.remove("d-none");

                        // Scroll to result
                        resultDiv.scrollIntoView({behavior: "smooth"});

                        // Add a "Back to List" button to the result section
                        const resultCard = document.querySelector("#result .card-body");
                        if (resultCard && !document.getElementById("back-to-list-btn")) {
                            const backBtn = document.createElement("a");
                            backBtn.id = "back-to-list-btn";
                            backBtn.href = data.result.redirect_url || "/";
                            backBtn.className = "btn btn-secondary mt-3";
                            backBtn.textContent = "Back to Routines List";
                            resultCard.appendChild(backBtn);
                        }

                        // Update the form's routine_id field if this is a new routine
                        const routineIdField = document.getElementById("routine_id");
                        if (routineIdField && !routineIdField.value && data.result.routine_id) {
                            routineIdField.value = data.result.routine_id;

                            // Update the URL to reflect the routine ID
                            if (history.pushState) {
                                const newUrl = `/routine/${data.result.routine_id}`;
                                window.history.pushState({path: newUrl}, "", newUrl);
                            }
                        }
                    }, 500);
                } else if (data.status === "failed") {
                    // Hide status
                    statusDiv.classList.add("d-none");

                    // Enable the generate button
                    generateBtn.disabled = false;

                    // Show error
                    errorDiv.textContent = data.error || "An error occurred while generating the audio. Please try again.";
                    errorDiv.classList.remove("d-none");
                } else {
                    // Task is still processing, update status message with more details
                    if (data.status === "processing") {
                        if (statusMessage) {
                            statusMessage.textContent = "Processing your audio... This may take a few minutes.";
                        }
                    } else if (data.status === "pending") {
                        if (statusMessage) {
                            statusMessage.textContent = "Waiting for processing to begin...";
                        }
                    }

                    // Continue polling after a delay
                    setTimeout(() => pollTaskStatus(taskId, redirectToList, pollCount + 1), 2000);
                }
            })
            .catch(error => {
                // Hide status
                statusDiv.classList.add("d-none");

                // Enable the generate button
                generateBtn.disabled = false;

                // Show error
                errorDiv.textContent = "An error occurred while communicating with the server. Please try again.";
                errorDiv.classList.remove("d-none");
                console.error("Error:", error);
            });
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        // Hide previous results and errors
        resultDiv.classList.add("d-none");
        errorDiv.classList.add("d-none");

        // Show status
        statusDiv.classList.remove("d-none");

        // Disable the generate button
        generateBtn.disabled = true;

        // Create FormData object
        const formData = new FormData(form);

        // If using uploaded voice, add the file
        if (uploadVoiceRadio.checked) {
            const voiceFile = document.getElementById("voice_file").files[0];
            if (voiceFile) {
                formData.append("voice_file", voiceFile);
            }
        }

        // Send the request to start the task
        fetch("/generate", {
            method: "POST",
            body: formData
        })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    // Hide status
                    statusDiv.classList.add("d-none");

                    // Enable the generate button
                    generateBtn.disabled = false;

                    // Show error
                    errorDiv.textContent = data.error;
                    errorDiv.classList.remove("d-none");
                } else if (data.task_id) {
                    // Start polling for task status
                    const redirectToList = data.redirect_url !== null;
                    pollTaskStatus(data.task_id, redirectToList);
                }
            })
            .catch(error => {
                // Hide status
                statusDiv.classList.add("d-none");

                // Enable the generate button
                generateBtn.disabled = false;

                // Show error
                errorDiv.textContent = "An error occurred while communicating with the server. Please try again.";
                errorDiv.classList.remove("d-none");
                console.error("Error:", error);
            });
    });

    // If there's a routine ID in the form and an output filename in the routine,
    // show the audio preview
    const routineId = document.getElementById("routine_id").value;
    if (routineId) {
        fetch(`/routines/${routineId}`)
            .then(response => response.json())
            .then(routine => {
                if (routine.output_filename) {
                    audioPreview.src = `/download/${routine.output_filename}`;
                    downloadLink.href = `/download/${routine.output_filename}?download=true`;
                    resultDiv.classList.remove("d-none");
                }
            })
            .catch(error => {
                console.error("Error loading routine audio:", error);
            });
    }

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
        const generateBtn = document.getElementById('generate-btn');

        if (!statusContainer || !statusMessage || !downloadBtn) return;

        statusContainer.style.display = 'block';

        switch (data.status) {
            case 'not_downloaded':
                statusContainer.className = 'alert alert-warning mb-4';
                statusMessage.textContent = 'TTS model is not downloaded. You need to download it to generate audio.';
                downloadBtn.style.display = 'inline-block';
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Download TTS Model';
                // Disable the generate button if model is not downloaded
                if (generateBtn) {
                    generateBtn.disabled = true;
                    generateBtn.title = 'TTS model must be downloaded first';
                }
                break;
            case 'downloading':
                statusContainer.className = 'alert alert-info mb-4';
                statusMessage.textContent = 'TTS model is downloading. This may take several minutes...';
                downloadBtn.style.display = 'none';
                // Disable the generate button if model is downloading
                if (generateBtn) {
                    generateBtn.disabled = true;
                    generateBtn.title = 'TTS model is downloading';
                }
                break;
            case 'downloaded':
                statusContainer.className = 'alert alert-success mb-4';
                statusMessage.textContent = 'TTS model is downloaded and ready to use.';
                downloadBtn.style.display = 'none';
                // Enable the generate button if model is downloaded
                if (generateBtn) {
                    generateBtn.disabled = false;
                    generateBtn.title = '';
                }
                break;
            case 'failed':
                statusContainer.className = 'alert alert-danger mb-4';
                statusMessage.textContent = `TTS model download failed: ${data.error || 'Unknown error'}`;
                downloadBtn.style.display = 'inline-block';
                downloadBtn.disabled = false;
                downloadBtn.textContent = 'Retry Download';
                // Disable the generate button if model download failed
                if (generateBtn) {
                    generateBtn.disabled = true;
                    generateBtn.title = 'TTS model download failed';
                }
                break;
            default:
                statusContainer.className = 'alert alert-secondary mb-4';
                statusMessage.textContent = `TTS model status: ${data.status}`;
                downloadBtn.style.display = 'none';
                // Disable the generate button for unknown status
                if (generateBtn) {
                    generateBtn.disabled = true;
                    generateBtn.title = 'Unknown TTS model status';
                }
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
