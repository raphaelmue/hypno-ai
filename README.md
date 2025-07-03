# Hypnosis Audio Generator

A web application that generates hypnosis audio from text using XTTS-v2 text-to-speech technology.

## Features

- Generate hypnosis audio from text prompts
- Select from multiple languages
- Use sample voices or upload your own reference voice
- Download generated audio files

## Requirements

- Python 3.8+
- PyTorch
- TTS (Text-to-Speech) library with XTTS-v2 support
- Flask

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/hypno-ai.git
   cd hypno-ai
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   # On Windows
   .venv\Scripts\activate
   # On macOS/Linux
   source .venv/bin/activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Add sample voice files:
   - Place WAV files in the `static/voices` directory
   - Rename them to match the sample voice IDs in `app.py` (e.g., `male1.wav`, `female1.wav`)

## Usage

1. Start the Flask application:
   ```
   python app.py
   ```

2. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. Enter your hypnosis script, select a language, and choose a voice.

4. Click "Generate Hypnosis Audio" and wait for the processing to complete.

5. Once complete, you can preview and download the generated audio file.

## Notes on XTTS-v2

XTTS-v2 is a multilingual text-to-speech model that can clone voices from short audio samples. For best results:

- Use clear, high-quality audio samples for voice reference
- Keep samples between 5-10 seconds in length
- Ensure the reference voice is speaking clearly without background noise

## License

MIT