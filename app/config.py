from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8000
    
    worker_host: str = "0.0.0.0"
    worker_port: int = 8001
    worker_gateway_url: str = "http://localhost:8000"
    
    inference_engine: str = "mock" # "mock" or "ollama"
    ollama_url: str = "http://localhost:11434"
    
    api_base_url: str = "https://api.openai.com/v1"
    api_key: str = "sk-placeholder"
    
    max_retries: int = 2
    
    gateway_api_keys: str = ""
    worker_shared_secret: str = "secret-placeholder"
    worker_allowed_hosts: str = ""
    cors_origins: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
