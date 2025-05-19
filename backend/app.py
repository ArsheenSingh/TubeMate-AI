from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import asyncio
from yt_chat_rag_using_langchain import get_transcript, process_youtube_video
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

@app.post("/query")
async def handle_query(request: QueryRequest, background_tasks: BackgroundTasks):
    vid = request.videoId
    q = request.query
    
    if not vid or not q:
        raise HTTPException(status_code=400, detail="videoId and query required")
    
    try:
        # Checking if we've already processed this video
        if vid in video_cache:
            logger.info(f"Using cached transcript for video ID: {vid}")
            transcript = video_cache[vid]
        else:
            
            logger.info(f"Retrieving transcript for video ID: {vid}")
            transcript = get_transcript(vid)
            
            
            if isinstance(transcript, str) and not (transcript.startswith("Error") or transcript.startswith("No")):
                video_cache[vid] = transcript
        
        
        logger.info(f"Retrieved transcript length: {len(transcript) if isinstance(transcript, str) else 'N/A'}")
        
        # Checking if transcript is an error message
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


results_cache = {}

async def process_long_video(transcript, query, video_id):
    """Process long videos in the background"""
    try:
        
        logger.info(f"Background processing of long video transcript ({len(transcript)} chars)")
        start_time = time.time()
        result = process_youtube_video(transcript, query)
        
        
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
        
        
        if time.time() - cached_data["timestamp"] < 300:  # 5 minutes
            
            result = cached_data["result"]
            
            return {"found": True, "answer": result}
    
    return {"found": False}

if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
