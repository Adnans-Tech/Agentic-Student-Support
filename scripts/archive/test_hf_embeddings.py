import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEndpointEmbeddings

load_dotenv()

def test_embeddings():
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    model_id = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    
    print(f"Testing with model: {model_id}")
    
    # Current configuration in the app
    try:
        url_format = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        print(f"Testing URL format: {url_format}")
        embeddings_url = HuggingFaceEndpointEmbeddings(
            model=url_format,
            huggingfacehub_api_token=api_key,
            task="feature-extraction"
        )
        res = embeddings_url.embed_query("what are college timings?")
        print(f"URL format success! Vector length: {len(res)}")
    except Exception as e:
        print(f"URL format failed: {e}")

    # Simplified configuration (Repo ID only)
    try:
        print(f"Testing Repo ID format: {model_id}")
        embeddings_repo = HuggingFaceEndpointEmbeddings(
            model=model_id,
            huggingfacehub_api_token=api_key,
            task="feature-extraction"
        )
        res = embeddings_repo.embed_query("what are college timings?")
        print(f"Repo ID format success! Vector length: {len(res)}")
    except Exception as e:
        print(f"Repo ID format failed: {e}")

if __name__ == "__main__":
    test_embeddings()
