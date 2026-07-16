import os
from dotenv import load_dotenv

# Load local environment variables
load_dotenv()

from app.services.llm_service import LLMService

print("Testing LLMService chat completion...")
try:
    llm = LLMService()
    print("OpenAI Client initialized:", llm._openai_client is not None)
    res = llm.chat_completion([{"role": "user", "content": "Say hello!"}])
    print("LLM Response:", res)
except Exception as e:
    print("LLM Call Failed:", e)
