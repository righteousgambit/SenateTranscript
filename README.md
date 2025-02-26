# UC Watcher

A Python utility for recording US Senate live streams. This tool automatically captures both video and audio streams from Senate sessions.

## Features

- Automatic detection of Senate live streams
- Separate video and audio recording
- Resilient stream handling with automatic reconnection
- Configurable logging levels
- FFmpeg-based recording with optimized settings
- Stream-specific recordings with unique IDs
- Organized recordings directory structure

## Requirements

- Python 3.7 or higher
- FFmpeg installed and available in system PATH

## Installation

Using pipx (recommended):
```bash
pipx uninstall uc_watcher                                                                                                                                                         ✔  took 1m 18s   at 12:27:04 PM  ▓▒░
pipx install -e . --verbose --force
pipx inject uc_watcher git+https://github.com/openai/whisper.git
```

## Usage

```bash
# Basic usage
uc_watcher

# With custom logging level
uc_watcher --log-level DEBUG
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

The `stream_id` is automatically generated from the Senate stream parameters and uniquely identifies each session.

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