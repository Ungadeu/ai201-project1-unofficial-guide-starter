#!/usr/bin/env python3
"""
Embedding and retrieval module for the course review RAG system.
Loads chunks from JSONL, embeds them with all-MiniLM-L6-v2, and stores in ChromaDB.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
import chromadb


def embed_and_store(chunks_jsonl_path: str, chroma_db_path: str) -> None:
    """
    Load chunks from JSONL, embed with all-MiniLM-L6-v2, and store in ChromaDB.
    
    Args:
        chunks_jsonl_path: Path to the JSONL file containing chunks from the chunking pipeline.
        chroma_db_path: Directory path where ChromaDB will persist the vector store.
    
    Example chunk format:
        {"source": "README.md", "doc_index": 1, "chunk_index": 0, "start": 0, "end": 1363, "text": "..."}
    """
    # Ensure the output directory exists
    Path(chroma_db_path).mkdir(parents=True, exist_ok=True)
    
    # Initialize the embedding model
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Initialize ChromaDB client with persistent storage using the new API
    # PersistentClient automatically persists data to disk at the given path
    client = chromadb.PersistentClient(path=chroma_db_path)
    
    # Get or create a collection for storing embeddings
    # The collection will automatically be created if it doesn't exist
    collection = client.get_or_create_collection(
        name="course_reviews",
        metadata={"hnsw:space": "cosine"}  # Use cosine similarity
    )
    
    # Load chunks and embed them
    print(f"Reading chunks from {chunks_jsonl_path}...")
    chunks = []
    with open(chunks_jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    
    print(f"Loaded {len(chunks)} chunks. Embedding...")
    
    # Prepare batch data for ChromaDB
    ids = []
    embeddings = []
    documents = []
    metadatas = []
    
    for chunk in chunks:
        # Create unique ID from source and chunk index
        chunk_id = f"{chunk['source']}_{chunk['chunk_index']}"
        ids.append(chunk_id)
        
        # Get the embedding for this chunk
        embedding = model.encode(chunk['text']).tolist()
        embeddings.append(embedding)
        
        # Store the chunk text
        documents.append(chunk['text'])
        
        # Store metadata: source, chunk index, and character span
        metadatas.append({
            'source': chunk['source'],
            'chunk_index': chunk['chunk_index'],
            'start': chunk['start'],
            'end': chunk['end'],
        })
    
    # Add all embeddings to ChromaDB in one batch
    # Using add() with all parameters: IDs, embeddings, documents, and metadata
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    
    # ChromaDB automatically persists with PersistentClient
    print(f"✓ Successfully stored {len(ids)} embedded chunks in ChromaDB at {chroma_db_path}")


def retrieve(query: str, chroma_db_path: str, top_k: int = 3) -> List[Dict]:
    """
    Retrieve the top-k most relevant chunks for a query using semantic search.
    
    Args:
        query: The user's question or search query.
        chroma_db_path: Path to the ChromaDB persistent storage directory.
        top_k: Number of chunks to retrieve (default: 3).
    
    Returns:
        A list of dicts, each containing:
            - "text": The chunk text
            - "source": The source document name
            - "chunk_index": The chunk index in that document
            - "distance": The distance score (0-2, where 0 is identical, cosine distance)
            - "start": Character start position in the original document
            - "end": Character end position in the original document
    
    Example:
        results = retrieve("What is the workload for CS core classes?", "/path/to/chroma_db", top_k=3)
        for result in results:
            print(f"Source: {result['source']}, Relevance: {result['distance']}")
    """
    # Initialize the embedding model (same model as embed_and_store)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Initialize ChromaDB client pointing to the persistent storage using the new API
    client = chromadb.PersistentClient(path=chroma_db_path)
    
    # Get the collection we created earlier
    collection = client.get_collection(name="course_reviews")
    
    # Embed the query using the same model
    query_embedding = model.encode(query).tolist()
    
    # Query the collection using the embedding
    # query() returns the top_k nearest neighbors based on cosine similarity
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    
    # Parse and format the results
    retrieved_chunks = []
    
    # results is a dict with keys: 'ids', 'distances', 'documents', 'metadatas'
    # All are lists (since we passed one query_embedding, they have length 1 for the query)
    if results['ids'] and len(results['ids']) > 0:
        for i, chunk_id in enumerate(results['ids'][0]):  # [0] because we only queried with one embedding
            chunk = {
                'text': results['documents'][0][i],
                'source': results['metadatas'][0][i]['source'],
                'chunk_index': results['metadatas'][0][i]['chunk_index'],
                'distance': results['distances'][0][i],
                'start': results['metadatas'][0][i]['start'],
                'end': results['metadatas'][0][i]['end'],
            }
            retrieved_chunks.append(chunk)
    
    return retrieved_chunks


if __name__ == "__main__":
    # Example usage
    CHUNKS_PATH = "data/chunks.jsonl"
    CHROMA_PATH = "data/chroma_db"
    
    # Step 1: Embed and store chunks (run once to build the vector store)
    if not os.path.exists(CHROMA_PATH):
        embed_and_store(CHUNKS_PATH, CHROMA_PATH)
    
    # Step 2: Retrieve relevant chunks for a sample query
    query = "What is the workload for CS core classes?"
    results = retrieve(query, CHROMA_PATH, top_k=3)
    
    print(f"\nQuery: {query}\n")
    print(f"Retrieved {len(results)} relevant chunks:\n")
    for i, result in enumerate(results, 1):
        print(f"--- Result {i} ---")
        print(f"Source: {result['source']} (chunk {result['chunk_index']})")
        print(f"Relevance distance: {result['distance']:.4f}")
        print(f"Text: {result['text'][:200]}...")
        print()
