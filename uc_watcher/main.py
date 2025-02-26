#! /usr/bin/env python3
import logging
import signal
import sys
import time
import os
import subprocess

# Add these debug prints at the very top
print("Debug: Starting script")
print(f"Debug: sys.path = {sys.path}")
print(f"Debug: Current directory = {os.getcwd()}")
print(f"Debug: __name__ = {__name__}")

from .cli import parse_arguments
from .logger import setup_logging
from .stream import fetch_stream_url
from .ffmpeg import run_ffmpeg, monitor_ffmpeg
from .transcribe import TranscriptionWorker

# Add immediate logging test after imports
print("Debug: Imports completed")

logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    sig_name = signal.Signals(sig).name
    logger.info("Received %s signal - shutting down gracefully...", sig_name)
    sys.exit(0)

def check_file_growth(file_path, check_interval=2, timeout=30):
    """
    Monitor file size to ensure it's growing, indicating successful recording.
    Returns True if file is growing, False otherwise.
    """
    # Wait for file to be created (up to 10 seconds)
    wait_time = 0
    while not os.path.exists(file_path) and wait_time < 10:
        logger.info(f"Waiting for {os.path.basename(file_path)} to be created... ({wait_time}s)")
        time.sleep(1)
        wait_time += 1

    if not os.path.exists(file_path):
        logger.error(f"File not created after {wait_time} seconds: {file_path}")
        return False

    logger.info(f"File created: {file_path}")
    initial_size = os.path.getsize(file_path)
    elapsed_time = 0

    while elapsed_time < timeout:
        time.sleep(check_interval)
        elapsed_time += check_interval
        
        if not os.path.exists(file_path):
            logger.error(f"File disappeared: {file_path}")
            return False

        current_size = os.path.getsize(file_path)
        if current_size > initial_size:
            size_diff_kb = (current_size - initial_size) / 1024
            logger.info(f"File is growing: {os.path.basename(file_path)} (+{size_diff_kb:.1f}KB)")
            return True
        
        logger.debug(f"Checking file growth: {os.path.basename(file_path)} (No change in {check_interval}s)")
        initial_size = current_size
    
    logger.error(f"File not growing after {timeout} seconds: {file_path}")
    return False

def verify_recording(video_file, audio_file, process):
    """Verify that FFmpeg is recording properly."""
    logging.info("Verifying recording status...")
    
    # Check if process is still running
    if process.poll() is not None:
        logging.error("FFmpeg process ended prematurely with code: %d", process.returncode)
        return False

    # Check for file creation with longer timeout
    timeout = 30  # Increased timeout to 30 seconds
    start_time = time.time()
    files_exist = False
    files_growing = False
    
    while time.time() - start_time < timeout:
        # First, wait for files to exist
        if not files_exist and os.path.exists(video_file) and os.path.exists(audio_file):
            files_exist = True
            logging.info("✓ Files created successfully")
            logging.info("  - Video: %s", video_file)
            logging.info("  - Audio: %s", audio_file)
            time.sleep(3)  # Give files a moment to start growing
            continue

        # Then check if they're growing
        if files_exist and not files_growing:
            video_size = os.path.getsize(video_file)
            audio_size = os.path.getsize(audio_file)
            time.sleep(2)
            
            video_growth = os.path.getsize(video_file) - video_size
            audio_growth = os.path.getsize(audio_file) - audio_size
            
            if video_growth > 0 and audio_growth > 0:
                logging.info("✓ Files are growing:")
                logging.info("  - Video: +%d bytes", video_growth)
                logging.info("  - Audio: +%d bytes", audio_growth)
                return True
            
        time.sleep(1)
        logging.info("Waiting for files to be created and grow... (%ds)", int(time.time() - start_time))

    logging.error("Recording verification failed:")
    if not os.path.exists(video_file):
        logging.error("Video file was not created")
    elif os.path.getsize(video_file) == 0:
        logging.error("Video file exists but is empty")
    else:
        logging.info("Video file size: %d bytes", os.path.getsize(video_file))
        
    if not os.path.exists(audio_file):
        logging.error("Audio file was not created")
    elif os.path.getsize(audio_file) == 0:
        logging.error("Audio file exists but is empty")
    else:
        logging.info("Audio file size: %d bytes", os.path.getsize(audio_file))
    
    return False

def cleanup_handler(process, video_file, audio_file):
    """Clean up FFmpeg process and output files."""
    logging.info("Cleaning up...")
    
    # Gracefully stop FFmpeg
    if process and process.poll() is None:
        logging.info("Stopping FFmpeg process...")
        try:
            # Send SIGTERM first for graceful shutdown
            process.terminate()
            try:
                process.wait(timeout=5)
                logging.info("FFmpeg process stopped gracefully")
            except subprocess.TimeoutExpired:
                logging.warning("FFmpeg process didn't stop gracefully, forcing...")
                process.kill()
                process.wait()
                logging.info("FFmpeg process killed")
        except Exception as e:
            logging.error("Error stopping FFmpeg: %s", e)
    
    # Finalize output files
    for file_path in [video_file, audio_file]:
        if os.path.exists(file_path):
            try:
                size = os.path.getsize(file_path)
                logging.info("Final file size for %s: %d bytes", file_path, size)
            except Exception as e:
                logging.error("Error checking file %s: %s", file_path, e)

def verify_notifications(args):
    """Test if notifications are working."""
    if not args.notifications:
        return
        
    logger.info("Testing system notifications...")
    try:
        test_cmd = [
            'osascript', '-e',
            'display notification "Testing notifications..." with title "UC Watcher" subtitle "Notification Test" sound name "Glass"'
        ]
        result = subprocess.run(test_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("✓ Notifications test successful")
        else:
            logger.error("❌ Notifications test failed: %s", result.stderr)
            logger.error("Please check your macOS notification settings:")
            logger.error("1. Open System Preferences")
            logger.error("2. Go to Notifications & Focus")
            logger.error("3. Ensure notifications are enabled for Terminal/iTerm2")
    except Exception as e:
        logger.error("❌ Notifications test failed: %s", str(e))

def main():
    """
    Main entry point for the Senate Stream Recorder.
    """
    print("Debug: Starting main()")
    
    # Parse command line arguments and setup logging first
    args = parse_arguments()
    print(f"Debug: Args parsed: {vars(args)}")
    setup_logging(args.log_level)
    print("Debug: Logging setup complete")

    # Test notifications early
    verify_notifications(args)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Create recordings directory if it doesn't exist
        recordings_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        logger.info("Recordings directory: %s", recordings_dir)

        # Log system information
        logger.info("System Information:")
        logger.info("  - Python Version: %s", sys.version.split()[0])
        logger.info("  - Operating System: %s", os.uname().sysname)
        logger.info("  - Machine: %s", os.uname().machine)
        logger.info("  - Working Directory: %s", os.getcwd())
        logger.info("-" * 60)

        # Start with a simple FFmpeg version check
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            logging.info("FFmpeg version check:\n%s", result.stdout.split('\n')[0])
        except Exception as e:
            logging.error("FFmpeg not found: %s", e)
            return 1

        json_url = "https://www.senate.gov/legislative/schedule/floor_schedule.json"
        restart_delay = 5
        max_restarts = 5
        restart_count = 0

        # Log startup configuration
        logger.info("=" * 60)
        logger.info("Senate Stream Recorder - Starting Up")
        logger.info("=" * 60)
        logger.info("Configuration:")
        logger.info("  - Schedule JSON URL: %s", json_url)
        logger.info("  - Recordings Directory: %s", recordings_dir)
        logger.info("  - Max Restart Attempts: %d", max_restarts)
        logger.info("  - Restart Delay: %d seconds", restart_delay)
        logger.info("-" * 60)

        # Step 1: Fetch stream URL
        logger.info("Step 1/3: Checking Senate stream availability...")
        logger.info("-" * 40)
        logger.info("Checking Senate session status...")
        logger.debug("Requesting schedule data from: %s", json_url)
        
        stream_url, stream_info = fetch_stream_url(json_url)
        if not stream_url or not stream_info:
            logger.error("❌ Stream URL acquisition failed")
            logger.error("  - Possible reasons:")
            logger.error("    * Senate is not in session")
            logger.error("    * Network connectivity issues")
            logger.error("    * Schedule API is unavailable")
            logger.error("    * Stream servers are not responding")
            sys.exit(1)
        
        logger.info("✓ Successfully found active Senate stream")
        logger.info("  - Stream URL: %s", stream_url)
        logger.info("  - Stream ID: %s", stream_info['stream_id'])
        logger.info("-" * 40)

        # Set up output files with stream ID
        video_file = os.path.join(recordings_dir, f"{stream_info['stream_id']}_video.mp4")
        audio_file = os.path.join(recordings_dir, f"{stream_info['stream_id']}_audio.mp3")

        # Check if output files already exist
        for file_path in [video_file, audio_file]:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                logger.warning("Output file already exists: %s (Size: %.2f MB)", 
                              file_path, file_size / (1024 * 1024))

        # Start FFmpeg with simplified process
        process = run_ffmpeg(stream_url, video_file, audio_file)
        if not process:
            logging.error("Failed to start FFmpeg")
            return 1

        # Initialize and start transcription worker
        transcriber = None
        try:
            transcriber = TranscriptionWorker(
                audio_file, 
                model_name="base",
                notifications_enabled=args.notifications
            )
            transcriber.start()
            logger.info("Started real-time transcription")
            if args.notifications:
                logger.info("System notifications enabled")

            # Verify recording
            if not verify_recording(video_file, audio_file, process):
                logging.error("Failed to verify recording")
                cleanup_handler(process, video_file, audio_file)
                if transcriber:
                    transcriber.stop()
                return 1

            logger.info("✓ Recording verified - both streams are being captured")
            logger.info("  - Video file: %s", video_file)
            logger.info("  - Audio file: %s", audio_file)
            logger.info("  - Transcript file: %s", audio_file.rsplit('.', 1)[0] + '.txt')
            logger.info("-" * 40)
            logger.info("Recording in progress... (Press Ctrl+C to stop)")

            try:
                monitor_ffmpeg(process)
            except KeyboardInterrupt:
                logger.info("\nReceived interrupt signal - gracefully shutting down...")
            finally:
                if transcriber:
                    logger.info("Stopping transcription...")
                    transcriber.stop()
                cleanup_handler(process, video_file, audio_file)
                logger.info("Shutdown complete")
                return 0

        except Exception as e:
            logger.error("❌ Unexpected error occurred: %s", e, exc_info=True)
            if transcriber:
                transcriber.stop()
            cleanup_handler(process, video_file, audio_file)
            return 1

    except Exception as e:
        logger.error("❌ Unexpected error occurred: %s", e, exc_info=True)
        cleanup_handler(process, video_file, audio_file)
        return 1
    finally:
        logger.info("Senate Stream Recorder stopped")
        logger.info("=" * 60)
    
    return 0

def run():
    """Entry point that handles signals properly."""
    # Ensure SIGINT (Ctrl+C) is handled by the main thread
    signal.signal(signal.SIGINT, signal.default_int_handler)
    
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # This ensures we don't get an ugly traceback on Ctrl+C
        sys.exit(0)

if __name__ == '__main__':
    run()
