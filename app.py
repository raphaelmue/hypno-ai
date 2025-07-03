import os
import uuid
import tempfile

from TTS.api import TTS
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pydub import AudioSegment

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'voices')
app.config['OUTPUT_FOLDER'] = os.path.join('static', 'output')
app.config['ALLOWED_EXTENSIONS'] = {'wav', 'mp3', 'ogg'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Sample voices (these would be pre-loaded)
SAMPLE_VOICES = {
    'male1': {'name': 'Male Voice 1', 'path': os.path.join(app.config['UPLOAD_FOLDER'], 'de-male-calm.mp3')}
}

# Available languages
LANGUAGES = {
    'en': 'English',
    'fr': 'French',
    'de': 'German',
    'es': 'Spanish',
    'it': 'Italian',
    'ja': 'Japanese',
    'zh': 'Chinese',
}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def generate_audio(text, language, voice_path):
    """Generate audio using XTTS-v2 with support for [break] markers"""
    # Initialize TTS with XTTS-v2
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    # Generate a unique filename
    output_filename = f"{uuid.uuid4()}.wav"
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

    # Check if text contains [break] markers
    if "[break]" in text:
        # Split text by [break] markers
        segments = text.split("[break]")

        # Create a temporary directory for segment audio files
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_files = []

            # Generate audio for each segment
            for i, segment in enumerate(segments):
                segment = segment.strip()
                if not segment:  # Skip empty segments
                    continue

                segment_path = os.path.join(temp_dir, f"segment_{i}.wav")
                tts.tts_to_file(
                    text=segment,
                    file_path=segment_path,
                    speaker_wav=voice_path,
                    language=language
                )
                segment_files.append(segment_path)

            # Combine audio segments with 2-second silence between them
            if segment_files:
                combined = AudioSegment.empty()
                silence = AudioSegment.silent(duration=2000)  # 2 seconds of silence

                for i, file_path in enumerate(segment_files):
                    segment_audio = AudioSegment.from_wav(file_path)
                    combined += segment_audio
                    if i < len(segment_files) - 1:  # Don't add silence after the last segment
                        combined += silence

                # Export the combined audio
                combined.export(output_path, format="wav")
            else:
                # Fallback if no valid segments were found
                tts.tts_to_file(
                    text="No valid text segments found",
                    file_path=output_path,
                    speaker_wav=voice_path,
                    language=language
                )
    else:
        # No breaks, generate speech normally
        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=voice_path,
            language=language
        )

    return output_filename


@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES, sample_voices=SAMPLE_VOICES)


@app.route('/generate', methods=['POST'])
def generate():
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
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{uuid.uuid4()}_{filename}")
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


@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)


if __name__ == '__main__':
    # In production, bind to all interfaces and disable debug mode
    app.run(host='0.0.0.0', port=5000, debug=False)
