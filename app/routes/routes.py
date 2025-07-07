import os
import uuid
from flask import render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

from app.routes import main_bp
from app.config import UPLOAD_FOLDER, OUTPUT_FOLDER, LANGUAGES, SAMPLE_VOICES
from app.utils import allowed_file
from app.audio import generate_audio


@main_bp.route('/')
def index():
    """Render the main page of the application"""
    return render_template('index.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES)


@main_bp.route('/generate', methods=['POST'])
def generate():
    """Handle the generation of audio from text"""
    # Get form data
    text = request.form.get('text', '')
    language = request.form.get('language', 'en')
    voice_type = request.form.get('voice_type', 'sample')

    # Validate inputs
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if language not in LANGUAGES:
        return jsonify({'error': 'Invalid language selected'}), 400

    # Handle voice selection
    voice_path = None
    if voice_type == 'sample':
        voice_id = request.form.get('sample_voice', '')
        if voice_id in SAMPLE_VOICES:
            voice_path = SAMPLE_VOICES[voice_id]['path']
        else:
            return jsonify({'error': 'Invalid sample voice selected'}), 400
    else:  # voice_type == 'upload'
        if 'voice_file' not in request.files:
            return jsonify({'error': 'No voice file uploaded'}), 400

        file = request.files['voice_file']
        if file.filename == '':
            return jsonify({'error': 'No voice file selected'}), 400

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{uuid.uuid4()}_{filename}")
            file.save(temp_path)
            voice_path = temp_path
        else:
            return jsonify({'error': 'Invalid file format'}), 400

    try:
        # Generate the audio file
        output_filename = generate_audio(text, language, voice_path)

        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)

        # Return the URL to the generated file
        return jsonify({
            'success': True,
            'filename': output_filename,
            'download_url': f'/download/{output_filename}'
        })
    except Exception as e:
        # Clean up temporary uploaded file if needed
        if voice_type == 'upload' and os.path.exists(voice_path) and 'temp_' in os.path.basename(voice_path):
            os.remove(voice_path)
        return jsonify({'error': f'Error generating audio: {str(e)}'}), 500


@main_bp.route('/download/<filename>')
def download(filename):
    """Handle the download of generated audio files"""
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)
