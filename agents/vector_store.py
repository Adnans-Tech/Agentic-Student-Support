"""
Vector Store Management for RAG — Cloud Edition
Uses Pinecone (cloud vector DB) + HuggingFace Inference API (cloud embeddings)

Replaces: local FAISS + local sentence-transformers (was causing 7.5GB Vercel bundle)
Now:       Pinecone API + HuggingFace API (tiny HTTP clients, ~5MB total)
"""
import os
import sys
sys.path.append('..')

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core.config import CHUNK_SIZE, CHUNK_OVERLAP


def _get_embeddings():
    """
    Get HuggingFace Inference API embeddings client.
    Uses the cloud API instead of downloading the model locally.
    Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
    """
    from langchain_huggingface import HuggingFaceEndpointEmbeddings

    api_key = os.getenv('HUGGINGFACE_API_KEY')
    model = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')

    if not api_key:
        raise ValueError("[ERROR] HUGGINGFACE_API_KEY not set in environment variables.")

    # Use the Repo ID directly to let LangChain handle URL and headers
    return HuggingFaceEndpointEmbeddings(
        model=model,
        huggingfacehub_api_token=api_key,
        task="feature-extraction"
    )


def _get_pinecone_vectorstore(embeddings):
    """
    Connect to the existing Pinecone index.
    Index must already exist with 384 dimensions and cosine metric.
    """
    from langchain_pinecone import PineconeVectorStore
    from pinecone import Pinecone

    api_key = os.getenv('PINECONE_API_KEY')
    index_name = os.getenv('PINECONE_INDEX_NAME', 'ace-support')

    if not api_key:
        raise ValueError("[ERROR] PINECONE_API_KEY not set in environment variables.")

    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)

    return PineconeVectorStore(index=index, embedding=embeddings)


class VectorStoreManager:
    """
    Manages the Pinecone cloud vector database for college rules RAG.
    Replaces the old FAISS-based local vector store.
    """

    def __init__(self, rules_file='data/college_rules.txt'):
        self.rules_file = rules_file
        self.embeddings = None
        self.vectorstore = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-load the cloud embedding client on first use."""
        if not self._initialized:
            print("[INFO] Connecting to HuggingFace Inference API for embeddings...")
            self.embeddings = _get_embeddings()
            self._initialized = True
            print("[OK] HuggingFace Embeddings API client ready (no local model download)")

    def load_and_split_documents(self):
        """Load college rules and split into chunks for ingestion."""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                content = f.read()

            doc = Document(page_content=content, metadata={"source": "college_rules.txt"})

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
                separators=["\n\n", "\n", " ", ""]
            )

            chunks = text_splitter.split_documents([doc])
            print(f"[OK] Split college rules into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            print(f"[ERROR] Error loading documents: {e}")
            return []

    def initialize_vectorstore(self):
        """
        Connect to the Pinecone cloud index.
        Data is already there permanently — no re-ingestion needed unless you run
        the migration script (scripts/migrate_to_pinecone.py).
        """
        self._ensure_initialized()
        print("[INFO] Connecting to Pinecone cloud vector store...")
        self.vectorstore = _get_pinecone_vectorstore(self.embeddings)
        print("[OK] Pinecone vector store connected successfully")
        return self.vectorstore

    def ingest_documents(self):
        """
        One-time: upload college rules documents into Pinecone.
        Run this locally once via: python agents/vector_store.py
        No need to run again unless college_rules.txt changes.
        """
        import time
        self._ensure_initialized()
        documents = self.load_and_split_documents()

        if not documents:
            raise Exception("No documents to ingest into Pinecone")

        print(f"[INFO] Uploading {len(documents)} chunks to Pinecone sequentially to respect HuggingFace API limits...")
        
        from langchain_pinecone import PineconeVectorStore
        from pinecone import Pinecone
        api_key = os.getenv('PINECONE_API_KEY')
        index_name = os.getenv('PINECONE_INDEX_NAME', 'ace-support')
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)
        
        # Connect to existing store
        self.vectorstore = PineconeVectorStore(index=index, embedding=self.embeddings)

        for i, doc in enumerate(documents):
            print(f"[INFO] Uploading chunk {i+1}/{len(documents)}...")
            try:
                # Upload one by one
                self.vectorstore.add_documents([doc])
                time.sleep(1) # Be nice to the free HuggingFace API
            except Exception as e:
                print(f"[WARN] Failed to upload chunk {i+1}: {e}")
                print("[INFO] Waiting 5 seconds before retrying...")
                time.sleep(5)
                self.vectorstore.add_documents([doc])

        print(f"[OK] Successfully uploaded chunks to Pinecone index '{index_name}'")

    def get_retriever(self, k=3):
        """Get retriever for semantic search against Pinecone."""
        if not self.vectorstore:
            self.initialize_vectorstore()

        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

    def search(self, query, k=3):
        """Perform semantic search against Pinecone."""
        if not self.vectorstore:
            self.initialize_vectorstore()

        results = self.vectorstore.similarity_search(query, k=k)
        return results


def initialize_vector_store():
    """Connect to the Pinecone vector store (for use at startup)."""
    print("\n" + "=" * 60)
    print("  Connecting to Pinecone Cloud Vector Store")
    print("=" * 60 + "\n")

    manager = VectorStoreManager()
    manager.initialize_vectorstore()

    print("\n" + "=" * 60)
    print("  Pinecone Vector Store Ready!")
    print("=" * 60 + "\n")

    return manager


# =============================================================================
# SINGLETON INSTANCE — prevents duplicate API client creation
# =============================================================================
_vector_store_instance = None


def get_vector_store_manager(rules_file='data/college_rules.txt') -> VectorStoreManager:
    """Get singleton VectorStoreManager — prevents creating multiple API clients."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreManager(rules_file=rules_file)
    return _vector_store_instance


if __name__ == "__main__":
    # Run this once locally to upload your college_rules.txt to Pinecone
    print("Running one-time document ingestion into Pinecone...")
    manager = VectorStoreManager()
    manager.ingest_documents()
    print("Done! Your Pinecone index is now populated.")
