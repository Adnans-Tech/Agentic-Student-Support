import os
import sys
import time
import uuid
from dotenv import load_dotenv
from pinecone import Pinecone
from huggingface_hub import InferenceClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def main():
    print("=" * 60)
    print("  ACE Support — Pinecone Migration Script")
    print("=" * 60)

    hf_key = os.getenv('HUGGINGFACE_API_KEY')
    pc_key = os.getenv('PINECONE_API_KEY')
    index_name = os.getenv('PINECONE_INDEX_NAME', 'ace-support')
    model_id = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')

    if not hf_key or not pc_key:
        print("[ERROR] Missing keys!")
        sys.exit(1)

    print("[INFO] Loading rules...")
    rule_path = 'data/college_rules.txt'
    with open(rule_path, 'r', encoding='utf-8') as f:
        content = f.read()

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(content)
    
    print(f"[INFO] Processing {len(chunks)} chunks...")
    
    client = InferenceClient(token=hf_key)
    pc = Pinecone(api_key=pc_key)
    index = pc.Index(index_name)

    vectors = []
    for i, chunk in enumerate(chunks):
        print(f"Embedding chunk {i+1}/{len(chunks)}...", end="\r")
        success = False
        for _ in range(3):
            try:
                # Use feature_extraction for embeddings
                vec = client.feature_extraction(chunk, model=model_id)
                if hasattr(vec, "tolist"):
                    vec = vec.tolist()
                elif isinstance(vec, list):
                    pass
                else:
                    raise ValueError(f"Unexpected return type: {type(vec)}")
                
                vectors.append({
                    "id": str(uuid.uuid4()),
                    "values": vec,
                    "metadata": {"text": chunk, "source": "college_rules.txt"}
                })
                success = True
                break
            except Exception as e:
                print(f"\n[WARN] Retry {_+1} for chunk {i+1}: {e}")
                time.sleep(5)
        
        if not success:
            print(f"\n[ERROR] Persistent failure for chunk {i+1}")
        time.sleep(0.1)

    if vectors:
        print(f"\n[INFO] Pushing {len(vectors)} vectors to Pinecone...")
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            index.upsert(vectors=vectors[i:i + batch_size])
        print("\n[SUCCESS] Migration complete!")
    else:
        print("\n[ERROR] No vectors generated.")

if __name__ == "__main__":
    main()
