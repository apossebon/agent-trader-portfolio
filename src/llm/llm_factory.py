from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
import os

load_dotenv(override=True)

class LLMFactory:
    def __init__(self):
        self.llm = os.getenv("LLM")

    def get_llm(self):
        return self.llm
    
    def get_LMStudio_llm(self, model:str):

        llm = ChatOpenAI(base_url=os.getenv("base_url_LMStudio"), model=model, api_key=SecretStr("lm-studio"), streaming=True, max_retries=5)

        return llm
    
    def get_Ollama_llm(self, model:str):

        llm = ChatOpenAI(base_url=os.getenv("base_url_Ollama"), model=model, api_key=SecretStr("ollama"), streaming=True, max_retries=5)

        return llm
    
    def get_OpenAI_llm(self, model:str):
        llm = ChatOpenAI(model=model, api_key=SecretStr("OPENAI_API_KEY"), streaming=True, max_retries=5)
        return llm
