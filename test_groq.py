#!/usr/bin/env python3
import os
import logging
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('groq_test')

def test_groq_api():
    """Test Groq API with a sample vendor"""
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        logger.error("No Groq API key found in environment variables")
        return False
    
    logger.info("Testing Groq API with sample vendor: 'New Vendor'")
    
    # Prepare the request for Groq API
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Prepare the prompt
    prompt = "Categorize this vendor: New Vendor, This is a new technology vendor for testing into one of these categories: Office Supplies, Software as a Service (SaaS), Professional Services"
    
    # Prepare the request body
    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a professional business analyst specializing in vendor categorization."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 100
    }
    
    try:
        # Call Groq API with LLama 3 model
        logger.info(f"Using Groq model: llama3-70b-8192")
        logger.info(f"API Request: {prompt}")
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        # Process the response
        response_data = response.json()
        category = response_data['choices'][0]['message']['content'].strip()
        
        logger.info(f"API Response: {category}")
        return True
    except Exception as e:
        logger.error(f"Error calling Groq API: {e}")
        return False

if __name__ == "__main__":
    if test_groq_api():
        logger.info("✅ Groq API test successful!")
    else:
        logger.error("❌ Groq API test failed!")
