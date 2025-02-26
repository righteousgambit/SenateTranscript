import logging
import subprocess
import time
import json
import os

def run_ffmpeg(stream_url, video_file, audio_file):
    """Run FFmpeg with the given stream URL and output files."""
    
    # 1. Basic command without complex options first
    command = [
        'ffmpeg',
        '-i', stream_url,
        '-c', 'copy',
        video_file
    ]
    
    logging.info("Testing simple FFmpeg command first...")
    logging.info("Command: %s", ' '.join(command))
    
    try:
        # Run a quick test
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Log the first few lines of output
        for _ in range(5):
            line = process.stderr.readline()
            if line:
                logging.debug("FFmpeg output: %s", line.strip())
        
        # Kill the test process
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            
        logging.info("Test completed")
        
    except Exception as e:
        logging.error("FFmpeg test failed: %s", e)
        return None
        
    # 2. Now try the full command
    full_command = [
        'ffmpeg',
        '-y',  # Overwrite output files
        '-i', stream_url,
        '-c:v', 'copy',
        video_file,
        '-c:a', 'libmp3lame',
        '-q:a', '2',
        audio_file
    ]
    
    logging.info("Starting FFmpeg with full command...")
    logging.info("Command: %s", ' '.join(full_command))
    
    try:
        process = subprocess.Popen(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(2)
        
        if process.poll() is not None:
            # Process ended too quickly
            out, err = process.communicate()
            logging.error("FFmpeg failed to start:")
            if out:
                logging.error("stdout: %s", out)
            if err:
                logging.error("stderr: %s", err)
            return None
            
        logging.info("FFmpeg process started successfully (PID: %d)", process.pid)
        return process
        
    except Exception as e:
        logging.error("Failed to start FFmpeg: %s", e)
        return None

def verify_recording(process, video_file, audio_file, timeout=30):
    """Verify that FFmpeg is recording properly."""
    if not process:
        return False
        
    start_time = time.time()
    video_seen = False
    audio_seen = False
    
    while time.time() - start_time < timeout:
        # Check if process is still running
        if process.poll() is not None:
            out, err = process.communicate()
            logging.error("FFmpeg process ended unexpectedly:")
            if out:
                logging.error("stdout: %s", out)
            if err:
                logging.error("stderr: %s", err)
            return False
            
        # Check video file
        if os.path.exists(video_file):
            size = os.path.getsize(video_file)
            if size > 0:
                if not video_seen:
                    logging.info("✓ Video file created: %s (%d bytes)", video_file, size)
                    video_seen = True
        else:
            logging.debug("Waiting for video file to be created...")
            
        # Check audio file
        if os.path.exists(audio_file):
            size = os.path.getsize(audio_file)
            if size > 0:
                if not audio_seen:
                    logging.info("✓ Audio file created: %s (%d bytes)", audio_file, size)
                    audio_seen = True
        else:
            logging.debug("Waiting for audio file to be created...")
            
        # Success if both files exist and have data
        if video_seen and audio_seen:
            logging.info("✓ Both output files verified")
            return True
                
        time.sleep(1)
        logging.info("Waiting for files... (%ds elapsed)", int(time.time() - start_time))
        
    logging.error("Timeout waiting for files to be created")
    if not video_seen:
        logging.error("Video file was never created")
    if not audio_seen:
        logging.error("Audio file was never created")
    return False

def monitor_ffmpeg(process):
    """
    Monitor FFmpeg's stderr output for logging and error detection.
    """
    if not process:
        logging.error("No FFmpeg process to monitor")
        return

    error_count = 0
    max_errors = 5
    ffmpeg_logger = logging.getLogger("ffmpeg_progress")
    
    try:
        # Start reading stderr immediately
        logging.info("Starting FFmpeg output monitoring")
        while True:
            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break
                
            if line:
                line = line.strip()
                # Log all FFmpeg output at debug level
                logging.debug("FFmpeg: %s", line)
                
                if "error" in line.lower():
                    logging.error("FFmpeg error: %s", line)
                elif "warning" in line.lower():
                    logging.warning("FFmpeg warning: %s", line)
                    
        # Process ended, get any remaining output
        out, err = process.communicate()
        if out:
            logging.debug("Final FFmpeg stdout: %s", out)
        if err:
            logging.debug("Final FFmpeg stderr: %s", err)
            
        exit_code = process.poll()
        logging.info("FFmpeg process ended with exit code: %d", exit_code)
        
    except Exception as e:
        logging.error("Error monitoring FFmpeg process: %s", e)
        logging.debug("Full exception details:", exc_info=True) 