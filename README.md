# Hypnosis Audio Generator

A desktop application that generates hypnosis audio from text using XTTS-v2 text-to-speech technology.

## Features

- Generate hypnosis audio from text prompts
- Name and save your hypnosis routines
- View a list of all saved routines
- Load and regenerate existing routines
- Select from multiple languages
- Use sample voices or upload your own reference voice
- Play and save generated audio files
- Cross-platform support (Windows, macOS, Linux)

## Requirements

- Python 3.8+
- PyTorch
- TTS (Text-to-Speech) library with XTTS-v2 support
- PyQt6 for the desktop UI

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/raphaelmue/hypno-ai.git
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
   - Place WAV files in the `app/static/voices` directory
   - Rename them to match the sample voice IDs in `app/config.py` (e.g., `male1.wav`, `female1.wav`)

## Usage

### Running the Application

1. Start the desktop application:
   ```
   python main.py
   ```

2. The application window will open, showing the list of saved routines.

3. Click "Create New Routine" to create a new hypnosis routine.

4. Enter your hypnosis script, select a language, and choose a voice.

5. Click "Generate Hypnosis Audio" and wait for the processing to complete.

6. Once complete, you can play the audio or save it to your device.

### Building Standalone Executables

You can build standalone executables for Windows, macOS, and Linux using PyInstaller:

#### Windows

```
pyinstaller hypno-ai.spec
```

The executable will be created in the `dist/Hypno-AI` directory.

#### macOS

```
pyinstaller hypno-ai.spec
```

The application bundle will be created as `dist/Hypno-AI.app`.

#### Linux

```
pyinstaller hypno-ai.spec
```

The executable will be created in the `dist/Hypno-AI` directory.

## Notes on XTTS-v2

XTTS-v2 is a multilingual text-to-speech model that can clone voices from short audio samples. For best results:

- Use clear, high-quality audio samples for voice reference
- Keep samples between 5-10 seconds in length
- Ensure the reference voice is speaking clearly without background noise

## License

MIT
