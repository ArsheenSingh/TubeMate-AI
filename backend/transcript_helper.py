from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
from youtube_transcript_api.proxies import WebshareProxyConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_transcript_api():
    """Create and return a proxied instance of YouTubeTranscriptApi"""
    return YouTubeTranscriptApi(
        proxy_config=WebshareProxyConfig(
            proxy_username="pajswpqh",  # Replace with your actual proxy username
            proxy_password="nkmavgiwldpd",  # Replace with your actual proxy password
        )
    )

def get_transcript(video_id):
    """Get transcript for a YouTube video using proxy"""
    try:
        # Get proxied instance of the API
        transcript_api = get_transcript_api()
        
        # Use the proxied instance to get transcript
        transcript_list = transcript_api.get_transcript(
            video_id, 
            languages=["en","hi","sk","pa","en-GB","en-US","en-CA","en-AU","en-IN","en-NZ","en-IE","en-ZA","en-PH","en-MY","en-SG"]
        )

        # Join transcript parts into a single string
        transcript = " ".join(chunk["text"] for chunk in transcript_list)
        return transcript

    except TranscriptsDisabled:
        logger.error("No captions available for this video.")
        return "No captions available for this video."
    except Exception as e:
        logger.error(f"Error getting transcript: {str(e)}")
        return f"Error getting transcript: {str(e)}"