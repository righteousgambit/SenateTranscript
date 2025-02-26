import logging
import threading
import time
import whisper
import os
import shutil
import tempfile
import subprocess

logger = logging.getLogger(__name__)

class TranscriptionWorker:
    def __init__(self, audio_file, model_name="base", notifications_enabled=False):
        self.audio_file = audio_file
        self.model_name = model_name
        self.stop_flag = False
        self.thread = None
        self.model = None
        self.transcript_file = audio_file.rsplit('.', 1)[0] + '.txt'
        self.last_processed_size = 0
        self.notifications_enabled = notifications_enabled
        
    def _send_system_notification(self, title, subtitle, message):
        """Send a macOS notification with the given parameters."""
        if not self.notifications_enabled:
            return
            
        try:
            # More visible notification with sound and force display
            cmd = [
                'osascript', '-e',
                f'''
                display notification "{message}" with title "{title}" subtitle "{subtitle}" sound name "Glass"
                '''
            ]
            
            # Log the exact command we're trying to run
            logger.debug("Notification command: %s", ' '.join(cmd))
            
            # First test if notifications are allowed
            test_cmd = [
                'osascript', '-e',
                'tell application "System Events" to get properties of current user'
            ]
            
            result = subprocess.run(test_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("No permission for notifications: %s", result.stderr)
                return
                
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("🔔 System notification sent: %s - %s", title, subtitle)
            else:
                logger.error("Notification failed: %s", result.stderr)
                
            # Try alternative notification method if the first one failed
            if result.returncode != 0:
                alt_cmd = [
                    'osascript', '-e',
                    f'''
                    tell application "System Events"
                        display dialog "{message}" with title "{title}" buttons {{"OK"}} default button 1
                    end tell
                    '''
                ]
                subprocess.run(alt_cmd, capture_output=True, text=True)
                
        except Exception as e:
            logger.error("Failed to send system notification: %s", str(e))
            logger.debug("Full exception details:", exc_info=True)
        
    def _send_notification(self, timestamp, text_snippet):
        """Send a macOS notification when unanimous consent is mentioned."""
        try:
            # Extract some context around "unanimous consent"
            words = text_snippet.split()
            for i, word in enumerate(words):
                if "unanimous" in word.lower() and i + 1 < len(words) and "consent" in words[i + 1].lower():
                    # Get up to 10 words before and after for context
                    start = max(0, i - 10)
                    end = min(len(words), i + 12)
                    context = " ".join(words[start:end])
                    
                    self._send_system_notification(
                        "Unanimous Consent Mentioned",
                        timestamp,
                        context
                    )
        except Exception as e:
            logger.error("Failed to send notification: %s", str(e))

    def start(self):
        """Start the transcription worker in a separate thread."""
        logger.info("Initializing Whisper model: %s", self.model_name)
        try:
            self.model = whisper.load_model(self.model_name)
            logger.info("✓ Whisper model loaded successfully")
            
            # Create transcript file or verify it's writable
            try:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                with open(self.transcript_file, 'a') as f:
                    f.write("=== Transcription Session Started ===\n")
                logger.info("✓ Transcript file initialized: %s", self.transcript_file)
                
                # Send start notification
                self._send_system_notification(
                    "Senate Stream Started",
                    timestamp,
                    f"Recording to {os.path.basename(self.audio_file)}"
                )
                
            except Exception as e:
                logger.error("Failed to initialize transcript file: %s", str(e))
                return
            
            self.thread = threading.Thread(target=self._transcribe_loop)
            self.thread.start()
            logger.info("✓ Transcription worker started")
        except Exception as e:
            logger.error("Failed to initialize Whisper model: %s", str(e))
        
    def stop(self):
        """Stop the transcription worker."""
        if self.thread:
            logger.info("Stopping transcription worker...")
            self.stop_flag = True
            self.thread.join()
            
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(self.transcript_file, 'a') as f:
                    f.write("\n=== Transcription Session Ended ===\n")
                    
                # Calculate session duration
                try:
                    file_size_mb = os.path.getsize(self.audio_file) / (1024 * 1024)
                    self._send_system_notification(
                        "Senate Stream Ended",
                        timestamp,
                        f"Recorded {file_size_mb:.1f}MB of audio"
                    )
                except Exception as e:
                    # Fallback if we can't get file size
                    self._send_system_notification(
                        "Senate Stream Ended",
                        timestamp,
                        "Recording stopped"
                    )
                    
            except Exception as e:
                logger.error("Failed to write session end marker: %s", str(e))
            logger.info("✓ Transcription worker stopped")
    
    def _extract_new_audio_segment(self, current_size):
        """Extract only the new portion of audio to a temporary file."""
        if current_size <= self.last_processed_size:
            return None
            
        try:
            # Create a temporary file for the new segment
            temp_fd, temp_path = tempfile.mkstemp(suffix='.mp3')
            os.close(temp_fd)
            
            # Copy only the new portion to the temp file
            with open(self.audio_file, 'rb') as src, open(temp_path, 'wb') as dst:
                src.seek(self.last_processed_size)
                shutil.copyfileobj(src, dst)
            
            return temp_path
        except Exception as e:
            logger.error("Failed to extract new audio segment: %s", str(e))
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
        
    def _transcribe_loop(self):
        """Main transcription loop."""
        min_chunk_size = 256 * 1024  # 256KB minimum to process
        check_interval = 1  # Check every second
        last_transcription_time = time.time()
        
        while not self.stop_flag:
            try:
                if not os.path.exists(self.audio_file):
                    logger.debug("Waiting for audio file to be created...")
                    time.sleep(check_interval)
                    continue
                    
                current_size = os.path.getsize(self.audio_file)
                time_since_last = time.time() - last_transcription_time
                
                # Process if we have new data and either:
                # 1. We have accumulated enough new data, or
                # 2. It's been more than 30 seconds since last transcription
                if current_size > self.last_processed_size and (
                    current_size - self.last_processed_size >= min_chunk_size or
                    time_since_last >= 30
                ):
                    logger.info("Processing new audio segment (+%dKB)", 
                              (current_size - self.last_processed_size) // 1024)
                    
                    # Extract new segment to temp file
                    temp_path = self._extract_new_audio_segment(current_size)
                    if not temp_path:
                        time.sleep(check_interval)
                        continue
                    
                    try:
                        # Transcribe only the new segment
                        result = self.model.transcribe(
                            temp_path,
                            initial_prompt="United States Senate proceedings."
                        )
                        
                        # Get current timestamp
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Check for "unanimous consent" in the transcription
                        text = result["text"].strip()
                        if "unanimous consent" in text.lower():
                            self._send_notification(timestamp, text)
                        
                        # Append transcription to file with timestamp
                        with open(self.transcript_file, 'a') as f:
                            f.write(f"\n[{timestamp}]\n{text}\n")
                        
                        logger.info("✓ Transcription updated (+%d chars)", len(text))
                        self.last_processed_size = current_size
                        last_transcription_time = time.time()
                        
                    except Exception as e:
                        logger.error("Transcription error: %s", str(e))
                        time.sleep(5)  # Wait before retrying
                    finally:
                        # Clean up temp file
                        try:
                            os.unlink(temp_path)
                        except Exception as e:
                            logger.error("Failed to clean up temp file: %s", str(e))
                else:
                    logger.debug("Waiting for more audio data... (Current: %dKB, Delta: %dKB)", 
                               current_size // 1024, 
                               (current_size - self.last_processed_size) // 1024)
                    time.sleep(check_interval)
                
            except Exception as e:
                logger.error("Error in transcription loop: %s", str(e))
                time.sleep(5)  # Wait before retrying

