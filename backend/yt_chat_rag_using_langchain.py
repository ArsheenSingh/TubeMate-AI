# -*- coding: utf-8 -*-
"""YT-Chat-Rag-using-langchain - Optimized for Long Videos"""

import os
import logging
from langdetect import detect
from deep_translator import GoogleTranslator
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_huggingface import HuggingFaceEmbeddings
import re
import string
import nltk
import time
from rate_limited_llm import get_llm
from transcript_helper import get_transcript

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


embedding = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')


nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)

def process_transcript(transcript_text):
    """Clean and translate transcript if needed"""
    try:
        # Detect language
        lang = detect(transcript_text[:1000])  # useing first 1000 chars for detection to save time
        logger.info(f"Detected language: {lang}")

        # Translate if not English
        if lang != 'en':
            translator = GoogleTranslator(source=lang, target='en')
            # Translating in chunks 
            chunk_size = 2000
            chunks = [transcript_text[i:i+chunk_size] for i in range(0, len(transcript_text), chunk_size)]
            translated_chunks = [translator.translate(chunk) for chunk in chunks]
            transcript_text = ' '.join(translated_chunks)
            logger.info(f"Translated from {lang} to English")

        return transcript_text

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return transcript_text  # Returning original if translation fails

def clean_transcript(text):
    """Apply NLP cleaning techniques to improve transcript quality"""
    
    text = re.sub(r'\[.*?\]', '', text)  # Remove bracketed content
    text = re.sub(r'\(.*?\)', '', text)  # Remove parenthetical content
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = re.sub(r'(\w)\.(\w)', r'\1. \2', text)  # Fix sentence boundaries
    text = re.sub(r'([.!?]){2,}', r'\1', text)  # Remove excessive punctuation
    text = re.sub(r"(\w+)'(\w+)", r"\1'\2", text)  # Fix spacing in contractions
    return text.strip()

def improve_transcript_with_llm(transcript_text):
    """Use LLM to clean and improve the transcript text - optimized for long transcripts"""
    
    if len(transcript_text) > 30000:
        logger.info("Transcript is very long. Skipping LLM improvement to avoid rate limits.")
        return transcript_text
        
    cleaning_prompt = """
    You are an expert in correcting and improving automatically generated transcripts.
    Below is a raw transcript from a YouTube video that may contain errors or unclear sections.
    
    Please correct and improve this transcript to make it more coherent and accurate.
    Focus on fixing obvious errors and improving sentence structure while preserving the original meaning.
    
    RAW TRANSCRIPT:
    {transcript}
    
    IMPROVED TRANSCRIPT:
    """

    
    llm = get_llm()
    
    # Split long transcripts into manageable chunks for the LLM
    max_chunk_size = 4000  
    
    if len(transcript_text) > max_chunk_size:
        # Process only a sample of the transcript for very long videos
        if len(transcript_text) > 15000:
            
            logger.info("Using basic cleanup instead of LLM for very long transcript")
            return clean_transcript(transcript_text)
            
        # Split into large chunks with overlap to maintain context
        chunks = []
        overlap = 200
        for i in range(0, len(transcript_text), max_chunk_size - overlap):
            chunks.append(transcript_text[i:i + max_chunk_size])
        
        # Process each chunk separately
        improved_chunks = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} of transcript")
            try:
                
                if i > 0:
                    time.sleep(2)
                    
                response = llm.invoke(
                    cleaning_prompt.format(transcript=chunk)
                )
                improved_chunks.append(response.content)
            except Exception as e:
                logger.error(f"Error improving transcript chunk: {str(e)}")
                # Fall back to original chunk if improvement fails
                improved_chunks.append(chunk)
        
        # Combine the improved chunks
        improved_transcript = " ".join(improved_chunks)
    else:
        # Process the entire transcript at once
        try:
            response = llm.invoke(
                cleaning_prompt.format(transcript=transcript_text)
            )
            improved_transcript = response.content
        except Exception as e:
            logger.error(f"Error improving transcript: {str(e)}")
            improved_transcript = transcript_text  
    
    return improved_transcript

def create_semantic_chunks(transcript):
    """Create chunks with better semantic boundaries"""
    # Adjust chunk size based on transcript length
    chunk_size = 800  
    chunk_overlap = 150
    
    if len(transcript) > 20000:
        # For longer transcripts, use larger chunks with less overlap
        chunk_size = 1200
        chunk_overlap = 200
    
    # First split by paragraphs or major breaks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", ";", ",", " ", ""],
        keep_separator=True
    )
    chunks = splitter.create_documents([transcript])
    
    # Add metadata to chunks
    for i, chunk in enumerate(chunks):
        
        chunk.page_content = chunk.page_content.strip()
        # Add metadata about position in original text
        chunk.metadata["position"] = i
        chunk.metadata["total_chunks"] = len(chunks)
    
    return chunks

def query_rewriting(user_query):
    """Use LLM to rewrite and improve user queries - with rate limiting"""
   
    return user_query

def process_youtube_video(raw_transcript, user_query):
    """
    Processes a YouTube video and answers a user query based on its transcript.
    Optimized for longer videos with rate limiting.
    
    """
    
    try:
        start_time = time.time()
        
        # Step 1: Transcript Processing
        logger.info("Processing transcript")
        translated_transcript = process_transcript(raw_transcript)
        cleaned_transcript = clean_transcript(translated_transcript)
        
        # Check if transcript is too long
        is_long_transcript = len(cleaned_transcript) > 15000
        
        # Only improve with LLM if not too long
        if not is_long_transcript:
            logger.info("Improving transcript with LLM")
            improved_transcript = improve_transcript_with_llm(cleaned_transcript)
        else:
            logger.info("Skipping LLM transcript improvement due to length")
            improved_transcript = cleaned_transcript
            
        logger.info("Creating semantic chunks")
        chunked_transcript = create_semantic_chunks(improved_transcript)
        logger.info(f"Created {len(chunked_transcript)} chunks")
        
        
        logger.info("Creating vector store")
        vector_store = FAISS.from_documents(chunked_transcript, embedding)
        
        
        rewritten_query = user_query
        
        
        logger.info("Retrieving relevant chunks")
        # For long transcripts, retrieve more chunks to ensure coverage
        k_chunks = 8 if is_long_transcript else 5
        
        retriever = vector_store.as_retriever(
            search_type="similarity", 
            search_kwargs={"k": k_chunks}
        )
        retrieved_docs = retriever.invoke(rewritten_query)
        
        # Format retrieved docs for the LLM
        context_text = "\n\n".join(doc.page_content for doc in retrieved_docs)
        
        logger.info(f"Retrieved {len(retrieved_docs)} chunks, total context length: {len(context_text)}")
        
        # Step 4: Generation using Langchain chain with rate limiting
        logger.info("Generating answer")
        
        # Improved prompt to get better answers
        enhanced_prompt = PromptTemplate(
            template="""
            You are a helpful assistant analyzing a YouTube video transcript. You need to answer questions about the content of the video based ONLY on the transcript context provided.

            IMPORTANT: 
            - Provide a direct answer to the question based on the context.
            - If you can find ANY relevant information in the transcript context that helps answer the question, include it.
            - If the exact answer isn't in the context but you can infer a reasonable answer from what's provided, do so.
            - Don't say words like according to the transcript or according to the context instead just provide the answer.
            - Be polite , helpful and informative.
            - Only say "I don't know" if there is absolutely nothing relevant to the question in the context.
            - Be concise but complete in your answers.

            Context:
            {context}

            Question: {question}

            Answer:
            """,
            input_variables=["context", "question"],
        )

        def format_docs(retrieved_docs):
            context_text = "\n\n".join(doc.page_content for doc in retrieved_docs)
            return context_text

        llm = get_llm()
        
        try:
            
            context = format_docs(retrieved_docs)
            prompt_text = enhanced_prompt.format(context=context, question=rewritten_query)
            
            response = llm.invoke(prompt_text)
            answer = response.content.strip()
            
            
            if answer.lower() in ["i don't know.", "i don't know", "i don't know", "i do not know"]:
                
                fallback_prompt = "Based on this YouTube video transcript extract, please answer this question as best you can: " + rewritten_query + "\n\nTranscript context:\n" + context
                fallback_response = llm.invoke(fallback_prompt)
                answer = fallback_response.content.strip()
            
            
            end_time = time.time()
            logger.info(f"Total processing time: {end_time - start_time:.2f} seconds")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"I'm sorry, I encountered an error while analyzing this video. Error: {str(e)}"

    except Exception as e:
        logger.error(f"Error in process_youtube_video: {str(e)}", exc_info=True)
        return f"An error occurred while processing the video: {str(e)}"

