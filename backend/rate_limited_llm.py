import time
import os
from dotenv import load_dotenv


load_dotenv()
api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")
print(f"API key loaded: {api_key[:8]}...")
from langchain_groq import ChatGroq
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
import logging

class RateLimitedLLM:
    """A wrapper around LLM calls that handles rate limiting"""
    
    def __init__(self, model_name="llama3-70b-8192", retry_limit=5, base_wait_time=5):
        self.model_name = model_name
        self.retry_limit = retry_limit
        self.base_wait_time = base_wait_time
        self.last_call_time = 0
        self.min_time_between_calls = 1.0  # Minimum 1 second between calls
        self.llm = self._create_llm()
        self.logger = logging.getLogger(__name__)
    
    def _create_llm(self):
        """Create the LLM with appropriate settings"""
        return ChatGroq(
            model=self.model_name,
            temperature=0.1,  
            streaming=True,
            callback_manager=CallbackManager([StreamingStdOutCallbackHandler()])
        )
    
    def invoke(self, prompt, max_tokens=None):
        """Invoke the LLM with rate limiting and retries"""
        # Ensure we don't call too frequently
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_time_between_calls:
            sleep_time = self.min_time_between_calls - time_since_last_call
            self.logger.info(f"Rate limiting: Sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        attempt = 0
        while attempt < self.retry_limit:
            try:
                
                self.last_call_time = time.time()
                
                
                kwargs = {}
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens
                    
                response = self.llm.invoke(prompt, **kwargs)
                return response
                
            except Exception as e:
                attempt += 1
                wait_time = self.base_wait_time * (2 ** attempt)  
                
                if "429" in str(e) or "Too Many Requests" in str(e):
                    self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds before retry {attempt}/{self.retry_limit}")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Error calling LLM: {str(e)}")
                    if attempt < self.retry_limit:
                        self.logger.info(f"Retrying in {wait_time} seconds. Attempt {attempt}/{self.retry_limit}")
                        time.sleep(wait_time)
                    else:
                        raise
        
        raise Exception(f"Failed to get response after {self.retry_limit} attempts")

# Singleton instance for use across the application
llm_instance = RateLimitedLLM()

def get_llm():
    """Get the singleton LLM instance"""
    return llm_instance