from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from openai import OpenAI
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
    def get_LLMDocker(self, model:str):

        llm = ChatOpenAI(base_url=os.getenv("base_url_Docker"), model=model, api_key=SecretStr("llm-doc"), streaming=True, max_retries=5, max_tokens=4096)

        return llm
    
    def get_Ollama_llm(self, model:str):

        llm = ChatOpenAI(base_url="http://host.docker.internal:8080/v1", model=model, api_key=SecretStr("ollama"), streaming=True, max_retries=5)

        return llm
    
    def get_OpenAI_llm(self, model:str):
        
        llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), streaming=True, max_retries=5)
        return llm
    
    def get_OpenAI(self, model:str):
        llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"), streaming=True, max_retries=5)
        return llm
    
    def get_llm_AzureOpenAI(self) -> AzureChatOpenAI:
        """
        Configura o cliente Azure OpenAI para uso com LangChain lib.
        """
        llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_BASE"), 
            azure_deployment= os.getenv("AZURE_OPENAI_DEPLOYMENT"), 
            api_key=SecretStr(os.getenv("AZURE_OPENAI_API_KEY", "")),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            # temperature=0.7,
            streaming=True,
                
        )
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")


        return llm

