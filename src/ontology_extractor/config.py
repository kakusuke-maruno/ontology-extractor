import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "lm-studio")
    llm_model: str = os.getenv("LLM_MODEL", "local-model")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-mxbai-embed-large-v1")

    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")

    class Config:
        env_file = ".env"

settings = Settings()
