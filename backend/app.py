from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import asyncio
import os
from yt_chat_rag_using_langchain import process_youtube_video
from transcript_helper import get_transcript, test_proxy_functionality, verify_proxy_connection
import uvicorn
import time
import requests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TubeMate AI API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


video_cache = {}

class QueryRequest(BaseModel):
    videoId: str
    query: str

_app_initialized = False
_initialization_error = None

@app.on_event("startup")
async def startup_event():
    """Optimized startup with timeout and non-blocking proxy test"""
    global _app_initialized, _initialization_error
    
    try:
        logger.info("Starting TubeMate AI API...")
        
        _app_initialized = True
        
        
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        
        if proxy_username and proxy_password:
            logger.info("Proxy credentials found, testing proxy functionality in background...")
            
            asyncio.create_task(background_proxy_test())
        else:
            logger.warning("⚠️ No proxy credentials found - running without proxy (may be blocked by YouTube)")
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        _initialization_error = str(e)
        _app_initialized = True

async def background_proxy_test():
    """Test proxy functionality in background without blocking startup"""
    try:
        
        await asyncio.sleep(2)
        
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, test_proxy_functionality_quick)
        
        if result:
            logger.info("✅ Proxy configuration is working correctly")
        else:
            logger.warning("⚠️ Proxy test failed - check your Webshare configuration")
    except Exception as e:
        logger.warning(f"Background proxy test failed: {str(e)}")

def test_proxy_functionality_quick():
    """Quick proxy test with shorter timeout"""
    try:
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        
        if not proxy_username or not proxy_password:
            return False
            
        proxy_dict = {
            'http': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80',
            'https': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80'
        }
        
        
        response = requests.get('https://api.ipify.org?format=json', 
                              proxies=proxy_dict, 
                              timeout=5)
        return response.status_code == 200
    except:
        return False

@app.post("/query")
async def handle_query(request: QueryRequest, background_tasks: BackgroundTasks):
    vid = request.videoId
    q = request.query
    
    if not vid or not q:
        raise HTTPException(status_code=400, detail="videoId and query required")
    
    try:
        
        if vid in video_cache:
            logger.info(f"Using cached transcript for video ID: {vid}")
            transcript = video_cache[vid]
        else:
            logger.info(f"Retrieving transcript for video ID: {vid}")
            transcript = get_transcript(vid)
            
            
            if isinstance(transcript, str) and not (transcript.startswith("Error") or transcript.startswith("No")):
                video_cache[vid] = transcript
        
        logger.info(f"Retrieved transcript length: {len(transcript) if isinstance(transcript, str) else 'N/A'}")
        
        
        if isinstance(transcript, str) and (transcript.startswith("Error") or transcript.startswith("No")):
            logger.warning(f"Transcript issue: {transcript}")
            return {"answer": f"I couldn't analyze this video: {transcript}"}
        
        
        if isinstance(transcript, str) and len(transcript) > 15000:
            task_key = f"{vid}:{q}"
            
            
            background_tasks.add_task(process_long_video, transcript, q, vid)
            
            return {
                "answer": "I'm analyzing this long video (it may take a minute). Please ask your question again in about 15 seconds for a complete response."
            }
            
        
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
        
        
        if time.time() - cached_data["timestamp"] < 300:
            result = cached_data["result"]
            return {"found": True, "answer": result}
    
    return {"found": False}

@app.get("/proxy_test")
async def proxy_test():
    """Simplified proxy test endpoint"""
    try:
        proxy_working = verify_proxy_connection()
        return {
            "proxy_configured": proxy_working,
            "message": "Proxy test completed"
        }
    except Exception as e:
        return {
            "proxy_configured": False,
            "error": str(e)
        }

@app.get("/test_connectivity")
async def test_connectivity():
    """Test external connectivity from container"""
    try:
        
        direct_response = requests.get('https://api.ipify.org?format=json', timeout=10)
        direct_ip = direct_response.json().get('ip', 'Unknown')
        
        
        proxy_username = os.getenv('WEBSHARE_PROXY_USERNAME')
        proxy_password = os.getenv('WEBSHARE_PROXY_PASSWORD')
        proxy_dict = {
            'https': f'http://{proxy_username}:{proxy_password}@p.webshare.io:80'
        }
        proxy_response = requests.get('https://api.ipify.org?format=json', 
                                    proxies=proxy_dict, 
                                    timeout=30)
        proxy_ip = proxy_response.json().get('ip', 'Unknown')
        
        return {
            "direct_connection": True,
            "direct_ip": direct_ip,
            "proxy_connection": True,
            "proxy_ip": proxy_ip
        }
    except Exception as e:
        return {
            "direct_connection": False,
            "proxy_connection": False,
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Optimized health check endpoint"""
    global _app_initialized, _initialization_error
    
    
    if _app_initialized:
        status = {
            "status": "healthy", 
            "service": "TubeMate AI API",
            "timestamp": time.time()
        }
        
        if _initialization_error:
            status["warning"] = _initialization_error
            
        return status
    else:
        raise HTTPException(status_code=503, detail="Service starting up")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "TubeMate AI API is running", "version": "1.0"}

if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
