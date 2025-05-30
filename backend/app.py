from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import asyncio
import os
# Import both the get_transcript function and process_youtube_video from yt_chat_rag_using_langchain
from yt_chat_rag_using_langchain import process_youtube_video
from transcript_helper import get_transcript, test_proxy_functionality, verify_proxy_connection
import uvicorn
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TubeMate AI API")

# Adding CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# Global cache for processed transcripts
video_cache = {}

class QueryRequest(BaseModel):
    videoId: str
    query: str

@app.on_event("startup")
async def startup_event():
    """Test proxy configuration on startup"""
    logger.info("Starting TubeMate AI API...")
    
    # Check if proxy credentials are available
    proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
    proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
    
    if proxy_username and proxy_password:
        logger.info("Proxy credentials found, testing proxy functionality...")
        if test_proxy_functionality():
            logger.info("✅ Proxy configuration is working correctly")
        else:
            logger.warning("⚠️ Proxy test failed - check your Webshare configuration")
    else:
        logger.warning("⚠️ No proxy credentials found - running without proxy (may be blocked by YouTube)")

@app.post("/query")
async def handle_query(request: QueryRequest, background_tasks: BackgroundTasks):
    vid = request.videoId
    q = request.query
    
    if not vid or not q:
        raise HTTPException(status_code=400, detail="videoId and query required")
    
    try:
        # Check if we've already processed this video
        if vid in video_cache:
            logger.info(f"Using cached transcript for video ID: {vid}")
            transcript = video_cache[vid]
        else:
            logger.info(f"Retrieving transcript for video ID: {vid}")
            transcript = get_transcript(vid)
            
            # Cache successful transcripts
            if isinstance(transcript, str) and not (transcript.startswith("Error") or transcript.startswith("No")):
                video_cache[vid] = transcript
        
        logger.info(f"Retrieved transcript length: {len(transcript) if isinstance(transcript, str) else 'N/A'}")
        
        # Check if transcript is an error message
        if isinstance(transcript, str) and (transcript.startswith("Error") or transcript.startswith("No")):
            logger.warning(f"Transcript issue: {transcript}")
            return {"answer": f"I couldn't analyze this video: {transcript}"}
        
        # For long transcripts, add message about potential delay
        if isinstance(transcript, str) and len(transcript) > 15000:
            task_key = f"{vid}:{q}"
            
            # Process in background for long videos
            background_tasks.add_task(process_long_video, transcript, q, vid)
            
            return {
                "answer": "I'm analyzing this long video (it may take a minute). Please ask your question again in about 15 seconds for a complete response."
            }
            
        # Process the video and get the answer for shorter videos
        logger.info(f"Processing query: {q}")
        resp = process_youtube_video(transcript, q)
        return {"answer": resp}
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Cache for background processing results
results_cache = {}

async def process_long_video(transcript, query, video_id):
    """Process long videos in the background"""
    try:
        logger.info(f"Background processing of long video transcript ({len(transcript)} chars)")
        start_time = time.time()
        result = process_youtube_video(transcript, query)
        
        # Cache the result
        cache_key = f"{video_id}:{query}"
        results_cache[cache_key] = {
            "result": result,
            "timestamp": time.time()
        }
        
        end_time = time.time()
        logger.info(f"Background processing complete in {end_time - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")

@app.get("/check_result")
async def check_result(videoId: str, query: str):
    """Endpoint to check if a background processing result is available"""
    cache_key = f"{videoId}:{query}"
    
    if cache_key in results_cache:
        cached_data = results_cache[cache_key]
        
        # Check if result is still fresh (5 minutes)
        if time.time() - cached_data["timestamp"] < 300:
            result = cached_data["result"]
            return {"found": True, "answer": result}
    
    return {"found": False}

@app.get("/proxy_test")
async def proxy_test():
    """Endpoint to test proxy functionality"""
    try:
        proxy_working = verify_proxy_connection()
        full_test = test_proxy_functionality()
        
        return {
            "proxy_configured": proxy_working,
            "youtube_access": full_test,
            "message": "Check logs for detailed information"
        }
    except Exception as e:
        return {
            "proxy_configured": False,
            "youtube_access": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "TubeMate AI API"}

if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
