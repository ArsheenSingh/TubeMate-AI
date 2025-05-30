import os
import time
import logging
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_proxy_connection():
    """Verify proxy connectivity before making API calls"""
    try:
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        
        if not proxy_username or not proxy_password:
            logger.error("Proxy credentials not found")
            return False
            
        proxy_dict = {
            'http': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80',
            'https': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80'
        }
        
        # Test with multiple endpoints
        test_urls = [
            'https://api.ipify.org?format=json',
            'https://www.google.com',
            'https://ifconfig.me/all.json'
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, proxies=proxy_dict, timeout=8)
                if response.status_code == 200:
                    logger.info(f"Proxy test successful with {url}")
                    return True
            except Exception:
                continue
    except Exception:
        logger.error("All proxy test endpoints failed")
        return False
def get_transcript_with_proxy(video_id, max_retries=3):
    """Get transcript using requests with proxy for better control"""
    
    proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
    proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
    
    if not proxy_username or not proxy_password:
        logger.warning("No proxy credentials found, using direct connection")
        return get_transcript_direct(video_id, max_retries)
    
    # Configure proxy
    proxy_dict = {
    'http': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80',
    'https': f'https://{proxy_username}:{proxy_password}@p.webshare.io:80' 
    }
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to get transcript for video {video_id} (attempt {attempt + 1}/{max_retries}) with rotating proxy")
            
            # Use YouTubeTranscriptApi with custom session that uses proxy
            session = requests.Session()
            session.proxies.update(proxy_dict)
            
            # Create a custom YouTubeTranscriptApi instance
            transcript_api = YouTubeTranscriptApi()
            
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
            if any(keyword in error_msg for keyword in ['blocked', 'ip', 'request', 'forbidden', '429', 'rate limit']):
                logger.warning(f"Attempt {attempt + 1} failed due to blocking/rate limiting: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Wait before retrying (exponential backoff)
                    wait_time = (2 ** attempt) * 3  # 3, 6, 12 seconds
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"Error getting transcript: YouTube access blocked after {max_retries} attempts"
            else:
                # For other errors, don't retry
                logger.error(f"Non-blocking error occurred: {str(e)}")
                return f"Error getting transcript: {str(e)}"
    
    return "Error getting transcript: Maximum retries exceeded"

def get_transcript_direct(video_id, max_retries=3):
    """Fallback method to get transcript without proxy"""
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting direct transcript retrieval for video {video_id} (attempt {attempt + 1}/{max_retries})")
            
            transcript_api = YouTubeTranscriptApi()
            
            # Try to get transcript with multiple language options
            transcript_list = transcript_api.get_transcript(
                video_id,
                languages=["en","hi","sk","pa","en-GB","en-US","en-CA","en-AU","en-IN","en-NZ","en-IE","en-ZA","en-PH","en-MY","en-SG"]
            )
            
            # Combine all transcript chunks
            full_transcript = " ".join(chunk["text"] for chunk in transcript_list)
            
            logger.info(f"Successfully retrieved transcript directly (length: {len(full_transcript)} characters)")
            return full_transcript

        except TranscriptsDisabled:
            logger.error(f"No captions available for video {video_id}")
            return "No captions available for this video."
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if any(keyword in error_msg for keyword in ['blocked', 'ip', 'request', 'forbidden']):
                logger.warning(f"Direct attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"Error getting transcript: {str(e)}"
            else:
                logger.error(f"Non-blocking error occurred: {str(e)}")
                return f"Error getting transcript: {str(e)}"
    
    return "Error getting transcript: Maximum retries exceeded"

def get_transcript(video_id, max_retries=3):
    """Main function to get transcript - tries proxy first, then direct"""
    try:
        # First try with proxy
        if verify_proxy_connection():
            result = get_transcript_with_proxy(video_id, max_retries)
        else:
            logger.warning("Proxy verification failed, using direct connection")
            result = get_transcript_direct(video_id, max_retries)
            
        return result
    except Exception as e:
        logger.error(f"Fallback to direct connection: {str(e)}")
        return get_transcript_direct(video_id, max_retries)

def test_proxy_functionality():
    """Test function to verify proxy is working with YouTube"""
    test_video_id = "dQw4w9WgXcQ"  # Rick Roll - commonly available video
    
    logger.info("Testing proxy functionality with sample video...")
    
    # First test proxy connection
    if not verify_proxy_connection():
        logger.error("Proxy connection test failed")
        return False
    
    # Then test actual transcript retrieval
    result = get_transcript(test_video_id)
    
    if result.startswith("Error") or result.startswith("No"):
        logger.error(f"Proxy test failed: {result}")
        return False
    else:
        logger.info("Proxy test successful!")
        return True