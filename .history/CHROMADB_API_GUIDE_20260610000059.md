# ChromaDB API Guide: Embedding and Retrieval

This document explains the ChromaDB API patterns used in `embedding_and_retrieval.py` so you understand what each call does.

## Overview

ChromaDB is a vector database that stores embeddings and their metadata. The pipeline has three main steps:
1. **Initialize**: Create a persistent client and collection
2. **Add**: Embed chunks and store them with metadata
3. **Query**: Retrieve the most relevant chunks for a user query

---

## API Patterns Explained

### 1. **`chromadb.PersistentClient(path=chroma_db_path)`**

**What it does:** Creates a ChromaDB client that automatically saves data to disk.

```python
client = chromadb.PersistentClient(path=chroma_db_path)
```

- `path`: Directory where all vector data and metadata will be stored
- The data persists even after the program exits (unlike ephemeral/in-memory clients)
- The directory is created automatically if it doesn't exist

**Why this matters:** You can restart your program and reload the same vector store without re-embedding everything.

---

### 2. **`client.get_or_create_collection(name, metadata)`**

**What it does:** Gets an existing collection by name, or creates it if it doesn't exist.

```python
collection = client.get_or_create_collection(
    name="course_reviews",
    metadata={"hnsw:space": "cosine"}
)
```

- **`name`**: A unique identifier for this collection (like a table in SQL)
- **`metadata={"hnsw:space": "cosine"}`**: 
  - `hnsw:space` specifies the distance metric
  - `cosine` = cosine similarity (best for semantic search; values 0-2, where 0 = identical)
  - Other options: `l2` (Euclidean), `ip` (inner product)

**Why this matters:** You can have multiple collections in one ChromaDB instance (e.g., "course_reviews" and "dining_hall_reviews"). The distance metric affects how similarity is computed.

---

### 3. **`collection.add(ids, embeddings, documents, metadatas)`**

**What it does:** Stores vectors and their associated data in the collection.

```python
collection.add(
    ids=["README.md_0", "README.md_1", ...],
    embeddings=[[0.12, -0.45, ...], [0.01, 0.99, ...], ...],
    documents=["This is chunk text...", "Another chunk...", ...],
    metadatas=[
        {"source": "README.md", "chunk_index": 0, "start": 0, "end": 1363},
        {"source": "README.md", "chunk_index": 1, "start": 1363, "end": 2500},
        ...
    ]
)
```

**Parameters:**

| Parameter | Type | Purpose |
|-----------|------|---------|
| `ids` | `List[str]` | Unique identifier for each chunk (e.g., `"README.md_0"`) |
| `embeddings` | `List[List[float]]` | The 384-dimensional vectors from `SentenceTransformer` |
| `documents` | `List[str]` | The original chunk text (ChromaDB stores this for retrieval) |
| `metadatas` | `List[Dict]` | Structured data about each chunk (source, position, etc.) |

**Why this matters:** 
- The ID must be unique; Chrome uses it to update/delete specific chunks
- Embeddings are the core data; ChromaDB uses these for similarity search
- Documents are stored as-is; you get them back in search results
- Metadata is searchable; you can filter results by source or other fields

---

### 4. **`collection.query(query_embeddings, n_results)`**

**What it does:** Finds the top-k nearest neighbors to your query embedding using vector similarity.

```python
results = collection.query(
    query_embeddings=[query_vector],  # A single embedding as a list
    n_results=3
)
```

**Return value** (a dict):

```python
{
    'ids': [['README.md_0']],  # Note: nested list (queries can be batched)
    'distances': [[0.8029]],    # Cosine distance (0=perfect match, 2=opposite)
    'documents': [['This is chunk text...']],
    'metadatas': [[{'source': 'README.md', 'chunk_index': 0, ...}]]
}
```

**Why the nested structure?** ChromaDB supports batch queries (multiple embeddings at once). Since we pass 1 query, the outer list has 1 element `[0]`, which contains the results for that query.

**Distance scores with cosine similarity:**
- `0.0` = identical vectors (perfect match)
- `0.5` = moderately similar
- `1.0` = orthogonal (no similarity)
- `2.0` = opposite vectors (rare for text)

---

## Full Example: What Happens Step-by-Step

### During `embed_and_store()`:

```python
# 1. Load the embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")
# → Creates a ~90MB model in memory; used to convert text → 384-dim vectors

# 2. Initialize persistence
client = chromadb.PersistentClient(path="data/chroma_db")
# → Prepares to save data to disk

# 3. Get/create collection
collection = client.get_or_create_collection(name="course_reviews", ...)
# → Creates a searchable index ready to store vectors

# 4. For each chunk:
for chunk in chunks:
    embedding = model.encode(chunk['text']).tolist()
    # → Converts "What do students say about..." → [0.12, -0.45, ..., 0.01]

# 5. Batch add to ChromaDB
collection.add(ids=[...], embeddings=[...], documents=[...], metadatas=[...])
# → Stores all vectors + metadata; ChromaDB indexes them automatically
```

### During `retrieve()`:

```python
# 1. Get the same model
model = SentenceTransformer("all-MiniLM-L6-v2")

# 2. Reload the client and collection
client = chromadb.PersistentClient(path="data/chroma_db")
collection = client.get_collection(name="course_reviews")

# 3. Embed the user's query
query_embedding = model.encode("What is the workload for CS core classes?").tolist()
# → "What is the workload..." → [0.02, 0.56, ..., -0.1]

# 4. Search for similar embeddings
results = collection.query(query_embeddings=[query_embedding], n_results=3)
# → Finds the 3 vectors closest to the query vector

# 5. Extract and return
for chunk_text, metadata in zip(results['documents'][0], results['metadatas'][0]):
    # → Returns the original chunk text + all metadata for the user
```

---

## Key Takeaways

1. **Embeddings are the core**: Everything is based on converting text to vectors and finding similar vectors.
2. **ChromaDB handles the hard part**: It indexes vectors for fast similarity search using HNSW (a graph-based algorithm).
3. **Metadata is preserved**: You can track which source each result came from.
4. **Distance matters**: Lower cosine distance = more relevant. Use this to filter noisy results if needed.
5. **Batch operations**: ChromaDB's API supports batching for efficiency (add/query multiple at once).

---

## Common Gotchas

### Problem: "Collection does not exist"
**Cause:** You called `collection.get_collection()` before calling `embed_and_store()`.  
**Solution:** Always call `embed_and_store()` first, or use `get_or_create_collection()`.

### Problem: Results are not relevant
**Cause:** The embedding model sees the query/chunks differently than you expected.  
**Solution:** Try a different embedding model (e.g., `all-MiniLM-L12-v2` for longer texts).

### Problem: Slow retrieval with millions of chunks
**Cause:** HNSW still needs to search all vectors.  
**Solution:** Add metadata filtering: `collection.query(..., where={"source": "reddit"})`

---

## Next Steps

Your retrieval function now returns relevant chunks. The next stage is **Generation**: passing these chunks to an LLM (via Groq or your chosen provider) to synthesize an answer grounded in the retrieved documents.

See `planning.md` → **Milestone 5** for how to integrate this with an LLM response.
