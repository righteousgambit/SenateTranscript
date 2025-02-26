# UC Watcher

A Python utility for recording US Senate live streams. This tool automatically captures both video and audio streams from Senate sessions, and provides real-time transcription with notifications for key events.

## Features

- Automatic detection of Senate live streams
- Separate video and audio recording
- Real-time speech transcription using OpenAI's Whisper
- System notifications for:
  - Stream start/stop events
  - "Unanimous consent" mentions
- Resilient stream handling with automatic reconnection
- Configurable logging levels
- FFmpeg-based recording with optimized settings
- Stream-specific recordings with unique IDs
- Organized recordings directory structure

## Requirements

- Python 3.7 or higher
- FFmpeg installed and available in system PATH
- macOS for system notifications (optional)

## Installation

Using pipx (recommended):
```bash
pipx uninstall uc_watcher
pipx install -e . --verbose --force
pipx inject uc_watcher git+https://github.com/openai/whisper.git
```

## Usage

```bash
# Basic usage
uc_watcher

# With custom logging level
uc_watcher --log-level DEBUG

# With system notifications enabled
uc_watcher --notifications
```

Available log levels:
- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

## Output Files

The tool creates a `recordings/` directory in the current working directory and stores recordings there. For each stream, it creates:

- `recordings/<stream_id>_video.mp4`: The video stream recording
- `recordings/<stream_id>_audio.mp3`: The audio stream recording in high-quality MP3 format
- `recordings/<stream_id>_audio.txt`: Real-time transcription of the audio

The `stream_id` is automatically generated from the Senate stream parameters and uniquely identifies each session.

### Transcription Format

The transcription file includes:
- Session start and end markers
- Timestamped entries for each transcribed segment
- Automatic detection and notification of "unanimous consent" mentions

Example:

## Development

To set up the development environment:

```bash
# Clone the repository
git clone https://github.com/yourusername/uc-watcher.git
cd uc-watcher

# Install with pipx
pipx install -e .
pipx inject uc_watcher requests beautifulsoup4 --force

# Or install with pip
pip install -e .
```

## License

MIT License 