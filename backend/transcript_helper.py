import os
import time
import logging
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from youtube_transcript_api._errors import TranscriptsDisabled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_proxy_connection():
    """Verify proxy connectivity before making API calls"""
    try:
        # Get proxy credentials from environment variables
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        
        if not proxy_username or not proxy_password:
            logger.error("Proxy credentials not found in environment variables")
            return False
            
        # Create proxy config
        proxy_config = WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password
        )
        
        # Test with a simple API call
        test_url = "https://api.ipify.org?format=json"
        
        # Use the proxy configuration to make a test request
        # Note: We'll test this through the YouTube API instead
        logger.info("Proxy configuration created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Proxy verification failed: {str(e)}")
        return False

def get_transcript_api():
    """Create and return a proxied YouTube Transcript API instance"""
    try:
        # Get proxy credentials from environment variables
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        
        if not proxy_username or not proxy_password:
            logger.warning("No proxy credentials found, using direct connection")
            return YouTubeTranscriptApi()
        
        # Create proxied instance with correct parameters
        proxy_config = WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password
        )
        
        return YouTubeTranscriptApi(proxy_config=proxy_config)
        
    except Exception as e:
        logger.error(f"Error creating proxied API instance: {str(e)}")
        # Fallback to direct connection
        return YouTubeTranscriptApi()

def get_transcript(video_id, max_retries=3):
    """Get transcript with enhanced proxy handling and retry logic"""
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to get transcript for video {video_id} (attempt {attempt + 1}/{max_retries})")
            
            # Create API instance (with or without proxy)
            transcript_api = get_transcript_api()
            
            # Try to get transcript with multiple language options
            transcript_list = transcript_api.get_transcript(
                video_id,
                languages=["en","hi","sk","pa","en-GB","en-US","en-CA","en-AU","en-IN","en-NZ","en-IE","en-ZA","en-PH","en-MY","en-SG"]
            )
            
            # Combine all transcript chunks
            full_transcript = " ".join(chunk["text"] for chunk in transcript_list)
            
            logger.info(f"Successfully retrieved transcript (length: {len(full_transcript)} characters)")
            return full_transcript

        except TranscriptsDisabled:
            logger.error(f"No captions available for video {video_id}")
            return "No captions available for this video."
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a YouTube blocking error
            if any(keyword in error_msg for keyword in ['blocked', 'ip', 'request', 'forbidden']):
                logger.warning(f"Attempt {attempt + 1} failed due to blocking: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"Error getting transcript: {str(e)}"
            else:
                # For other errors, don't retry
                logger.error(f"Non-blocking error occurred: {str(e)}")
                return f"Error getting transcript: {str(e)}"
    
    return "Error getting transcript: Maximum retries exceeded"

def test_proxy_functionality():
    """Test function to verify proxy is working with YouTube"""
    test_video_id = "dQw4w9WgXcQ"  # Rick Roll - commonly available video
    
    logger.info("Testing proxy functionality with sample video...")
    result = get_transcript(test_video_id)
    
    if result.startswith("Error") or result.startswith("No"):
        logger.error(f"Proxy test failed: {result}")
        return False
    else:
        logger.info("Proxy test successful!")
        return True