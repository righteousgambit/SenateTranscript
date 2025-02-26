import json
import logging
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
import requests

def extract_stream_url_from_html(page_url):
    """
    Extract the actual video stream URL from the Senate's HTML page.
    Based on the Senate's video player JavaScript code.
    Returns a tuple of (stream_url, stream_info) where stream_info contains comm and filename.
    """
    logging.info("Analyzing stream page URL: %s", page_url)
    
    try:
        # Parse the URL parameters
        logging.debug("Validating URL format and parameters...")
        if 'type=live' not in page_url:
            logging.error("Invalid URL format: Missing 'type=live' parameter")
            return None, None
            
        # Extract comm and filename parameters
        comm_match = re.search(r'comm=([^&]+)', page_url)
        filename_match = re.search(r'filename=([^&]+)', page_url)
        
        if not comm_match:
            logging.error("Failed to extract 'comm' parameter from URL")
            return None, None
        if not filename_match:
            logging.error("Failed to extract 'filename' parameter from URL")
            return None, None
            
        comm = comm_match.group(1)
        filename = filename_match.group(1)
        
        logging.info("Extracted stream parameters:")
        logging.info("  - Committee: %s", comm)
        logging.info("  - Filename: %s", filename)
        
        # Store stream info
        stream_info = {
            'comm': comm,
            'filename': filename,
            'stream_id': f"{comm}_{filename}"
        }
        
        # Primary stream URL
        stream_url = f"https://www-senate-gov-media-srs.akamaized.net/hls/live/2096634/{comm}/{filename}/master.m3u8"
        logging.info("Attempting primary stream URL: %s", stream_url)
        
        # Store backup URLs in case the primary fails
        backup_urls = [
            f"https://www-senate-gov-msl3archive.akamaized.net/stv/{filename}_1/master.m3u8",
            f"https://stv-f.akamaihd.net/i/{filename}_1@76462/master.m3u8"
        ]
        
        # Try primary URL first
        try:
            logging.info("Testing primary stream URL...")
            response = requests.head(stream_url, timeout=5)
            logging.debug("Primary stream response headers: %s", dict(response.headers))
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', 'unknown')
                content_length = response.headers.get('content-length', 'unknown')
                logging.info("✓ Primary stream URL is accessible:")
                logging.info("  - Status: %d", response.status_code)
                logging.info("  - Content-Type: %s", content_type)
                logging.info("  - Content-Length: %s", content_length)
                return stream_url, stream_info
            else:
                logging.warning("Primary stream URL returned status code: %d", response.status_code)
                logging.debug("Response headers: %s", dict(response.headers))
        except requests.exceptions.Timeout:
            logging.warning("Primary stream URL timeout after 5 seconds")
        except requests.exceptions.RequestException as e:
            logging.warning("Primary stream URL not accessible: %s", str(e))
        
        # Try backup URLs in sequence
        for idx, backup_url in enumerate(backup_urls, 1):
            logging.info("Attempting backup URL #%d: %s", idx, backup_url)
            try:
                response = requests.head(backup_url, timeout=5)
                logging.debug("Backup stream #%d response headers: %s", idx, dict(response.headers))
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', 'unknown')
                    content_length = response.headers.get('content-length', 'unknown')
                    logging.info("✓ Backup stream URL #%d is accessible:", idx)
                    logging.info("  - Status: %d", response.status_code)
                    logging.info("  - Content-Type: %s", content_type)
                    logging.info("  - Content-Length: %s", content_length)
                    return backup_url, stream_info
                else:
                    logging.warning("Backup URL #%d returned status code: %d", idx, response.status_code)
                    logging.debug("Response headers: %s", dict(response.headers))
            except requests.exceptions.Timeout:
                logging.warning("Backup URL #%d timeout after 5 seconds", idx)
            except requests.exceptions.RequestException as e:
                logging.warning("Backup URL #%d not accessible: %s", idx, str(e))
        
        logging.error("❌ All stream URLs failed")
        return None, None
        
    except Exception as e:
        logging.error("❌ Error processing stream URL: %s", str(e))
        logging.debug("Full exception details:", exc_info=True)
        return None, None

def fetch_stream_url(json_url, max_attempts=3, delay=10):
    """
    Fetch the session JSON and extract the 'convenedSessionStream' URL.
    Retries up to max_attempts if failures occur.
    """
    attempts = 0
    while attempts < max_attempts:
        try:
            logging.info(
                "Attempt %d/%d: Fetching session data from %s",
                attempts + 1,
                max_attempts,
                json_url
            )
            
            with urlopen(json_url, timeout=10) as response:
                raw_data = response.read()
                logging.debug("Raw JSON response: %s", raw_data.decode('utf-8'))
                data = json.loads(raw_data)
                
            sessions = data.get("floorProceedings", [])
            if not sessions:
                logging.error("❌ No active sessions found in JSON response")
                raise ValueError("JSON does not contain 'floorProceedings' - Senate may not be in session")
                
            logging.info("Found %d session(s) in response", len(sessions))
            logging.debug("Sessions data: %s", json.dumps(sessions, indent=2))
            
            html_url = sessions[0].get("convenedSessionStream")
            if not html_url:
                logging.error("❌ No stream URL found in session data")
                raise ValueError("Stream URL not found - Senate stream may not be active")
                
            logging.info("Found stream page URL: %s", html_url)
            
            # Extract the actual stream URL from the HTML page
            stream_url, stream_info = extract_stream_url_from_html(html_url)
            if not stream_url:
                raise ValueError("Could not extract video stream URL from the HTML page")
                
            logging.info("✓ Successfully negotiated stream URL: %s", stream_url)
            return stream_url, stream_info
            
        except HTTPError as e:
            attempts += 1
            logging.error("❌ HTTP error %d: %s", e.code, e.reason)
            logging.error("  URL: %s", json_url)
            
        except URLError as e:
            attempts += 1
            logging.error("❌ Network error: %s", str(e))
            logging.error("  URL: %s", json_url)
            
        except json.JSONDecodeError as e:
            attempts += 1
            logging.error("❌ Invalid JSON received: %s", str(e))
            logging.error("  Position: %d", e.pos)
            logging.error("  Line: %d, Column: %d", e.lineno, e.colno)
            
        except ValueError as e:
            attempts += 1
            logging.error("❌ Stream data error: %s", str(e))
            
        except Exception as e:
            attempts += 1
            logging.error("❌ Unexpected error: %s", str(e))

        if attempts < max_attempts:
            logging.info("Waiting %d seconds before retry...", delay)
            time.sleep(delay)

    logging.error("❌ Failed to fetch stream URL after %d attempts", max_attempts)
    return None, None 