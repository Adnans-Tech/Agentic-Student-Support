"""
Vector Store Management for RAG
Handles FAISS vector database initialization and semantic search
"""
import os
import sys
sys.path.append('..')

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from config import VECTOR_STORE_PATH, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP


class VectorStoreManager:
    """Manages vector database for college rules RAG"""
    
    def __init__(self, rules_file='data/college_rules.txt'):
        self.rules_file = rules_file
        self.vector_store_path = VECTOR_STORE_PATH
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.vectorstore = None
        
    def load_and_split_documents(self):
        """Load college rules and split into chunks"""
        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create document
            doc = Document(page_content=content, metadata={"source": "college_rules.txt"})
            
            # Split into chunks
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
        """Create or load vector store"""
        # Check if vector store exists
        if os.path.exists(self.vector_store_path) and os.path.exists(f"{self.vector_store_path}/index.faiss"):
            try:
                print("[INFO] Loading existing vector store...")
                self.vectorstore = FAISS.load_local(
                    self.vector_store_path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print("[OK] Vector store loaded successfully")
                return self.vectorstore
            except Exception as e:
                print(f"[WARN] Could not load existing vector store: {e}")
                print("Creating new vector store...")
        
        # Create new vector store
        print("[INFO] Creating new vector store...")
        documents = self.load_and_split_documents()
        
        if not documents:
            raise Exception("No documents to create vector store")
        
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        
        # Save vector store
        os.makedirs(self.vector_store_path, exist_ok=True)
        self.vectorstore.save_local(self.vector_store_path)
        print(f"[OK] Vector store created and saved to {self.vector_store_path}")
        
        return self.vectorstore
    
    def get_retriever(self, k=3):
        """Get retriever for semantic search"""
        if not self.vectorstore:
            self.initialize_vectorstore()
        
        return self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )
    
    def search(self, query, k=3):
        """Perform semantic search"""
        if not self.vectorstore:
            self.initialize_vectorstore()
        
        results = self.vectorstore.similarity_search(query, k=k)
        return results


def initialize_vector_store():
    """Helper function to initialize vector store"""
    print("\n" + "=" * 60)
    print("  Initializing Vector Database for RAG")
    print("=" * 60 + "\n")
    
    manager = VectorStoreManager()
    manager.initialize_vectorstore()
    
    print("\n" + "=" * 60)
    print("  Vector Database Ready!")
    print("=" * 60 + "\n")
    
    return manager


# =============================================================================
# SINGLETON INSTANCE — prevents duplicate ML model loading
# =============================================================================
_vector_store_instance = None

def get_vector_store_manager(rules_file='data/college_rules.txt') -> VectorStoreManager:
    """Get singleton VectorStoreManager — prevents loading the HuggingFace
    embedding model (~400MB) multiple times."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreManager(rules_file=rules_file)
    return _vector_store_instance


if __name__ == "__main__":
    # Test vector store initialization
    initialize_vector_store()
