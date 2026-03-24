import os
import sys
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def main():
    print("=" * 60)
    print("  ACE Support — Pinecone Migration Script")
    print("=" * 60)

    hf_key = os.getenv('HUGGINGFACE_API_KEY')
    pc_key = os.getenv('PINECONE_API_KEY')
    index_name = os.getenv('PINECONE_INDEX_NAME', 'ace-support')

    if not hf_key or not pc_key:
        print("[ERROR] Missing keys!")
        sys.exit(1)

    print("[INFO] Loading rules...")
    with open('data/college_rules.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(content)
    
    print(f"[INFO] Uploading {len(chunks)} chunks sequentially...")
    
    from pinecone import Pinecone
    pc = Pinecone(api_key=pc_key)
    index = pc.Index(index_name)

    from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
    embeddings = HuggingFaceInferenceAPIEmbeddings(
        api_key=hf_key,
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    import uuid
    vectors = []
    
    for i, chunk in enumerate(chunks):
        print(f"Embedding chunk {i+1}/{len(chunks)}...")
        # Use embed_query since it's the most stable endpoint format
        try:
            vec = embeddings.embed_query(chunk)
            vector_id = str(uuid.uuid4())
            vectors.append({
                "id": vector_id,
                "values": vec,
                "metadata": {"text": chunk, "source": "college_rules.txt"}
            })
            time.sleep(1) # Be nice to rate limits
        except Exception as e:
            print(f"[ERROR] Failed chunk {i+1}: {e}")
            time.sleep(5)

    if vectors:
        print("[INFO] Pushing vectors to Pinecone...")
        index.upsert(vectors=vectors)
        print("\n[SUCCESS] Migration complete!")
    else:
        print("\n[ERROR] No vectors generated.")

if __name__ == "__main__":
    main()
