# Prompt for AI Code Generation: Generation and Interface (Milestone 5)

## Context & Architecture

You are building the final stage of a **Retrieval-Augmented Generation (RAG)** system for course and professor reviews.

### Pipeline Overview
```
User Query 
  ↓
Retrieval (Semantic Search via ChromaDB)
  ↓ 
Retrieved Context Chunks (with source metadata)
  ↓
LLM Generation (Groq API)
  ↓
Final Answer + Source Attribution
```

### Completed Components You Will Integrate
- **Retrieval function** (`scripts/embedding_and_retrieval.py`):
  ```python
  retrieve(query: str, chroma_db_path: str, top_k: int = 5) -> List[Dict]
  ```
  Returns: `[{"text": "...", "source": "README.md", "chunk_index": 0, "distance": 0.65, "start": 0, "end": 1363}, ...]`

- **LLM API**: Groq (`groq==0.15.0`) with `mistral-7b-instant` or `mixtral-8x7b-32768`
- **Environment**: `.env` file with `GROQ_API_KEY`

---

## Generation Requirements: GROUNDING & SOURCE ATTRIBUTION

**Critical constraint**: Your system must answer ONLY from retrieved context. No hallucinations, no external knowledge.

### System Prompt (Enforce, Don't Suggest)

Generate a **strict system prompt** that:
1. **Forbids external knowledge**: "You must only answer based on the provided context chunks. Do NOT use your training data or external knowledge."
2. **Requires citation**: "For every claim, cite the source document and chunk index in [brackets]."
3. **Handles missing context**: "If the context does NOT contain relevant information, respond with: 'I cannot find this information in the student reviews.'"
4. **Format specification**: Include exact output format (see below).

Example (fill in your domain specifics):
```
You are an expert guide for [course/professor reviews]. 
Answer questions ONLY using the provided student review excerpts.
You MUST NOT use information outside the provided chunks.
For every statement, cite the source: [source_filename, chunk_index].
If the reviews do NOT contain relevant information, say: "I cannot find this in the student reviews."
```

### Programmatic Source Attribution (Not LLM-Reliant)

Do NOT trust the LLM to cite sources correctly. Instead:
1. **Extract citations from LLM response** using regex: `\[(.+?)\]`
2. **Validate citations**: Match against your actual retrieved chunks
3. **Append guaranteed source list** at the end of the response, constructed from the chunks you passed in

Example output format:
```
ANSWER:
Students report that Professor Smith's Math 242 exams changed this semester. 
According to reviews, he shifted from historical practice exams to entirely new, 
conceptually abstract problems [README.md, chunk 2]. 
Students recommend focusing on challenge problems at the end of each textbook chapter 
rather than old test banks [README.md, chunk 2].

SOURCES:
1. README.md (chunk 2) — Chars 523-890: "Professor Smith suddenly shifted..."
2. README.md (chunk 5) — Chars 1245-1687: "Students warn about the shift..."
```

---

## Output Format

Generate code that produces responses like:

```
Question: "What advice do students give for Math 242?"

STUDENT REVIEWS SAY:
[LLM-generated answer grounded in retrieved chunks]

SOURCES CITED:
1. source_filename (chunk_index)
   Text: "[First 100 chars of chunk]..."

2. source_filename (chunk_index)
   Text: "[First 100 chars of chunk]..."
```

---

## Interface: Gradio

Use **Gradio** for a simple web interface with:

### Layout:
```
┌─────────────────────────────────────┐
│  COURSE & PROFESSOR REVIEW GUIDE    │
├─────────────────────────────────────┤
│  Ask a question about courses or    │
│  professors:                        │
│                                     │
│  [Text input field for query]       │
│                                     │
│  [Submit button]                    │
├─────────────────────────────────────┤
│  RESPONSE:                          │
│  ─────────────────────────────────  │
│  [Markdown output showing answer]   │
│  [Source list below]                │
│                                     │
│  SOURCES:                           │
│  ─────────────────────────────────  │
│  [Formatted source citations]       │
└─────────────────────────────────────┘
```

### Key Features:
- **Input**: Single text field for user query
- **Output**: Two sections:
  1. Answer (Markdown formatted, grounded in retrieved context)
  2. Sources (Structured list with source filename, chunk index, text preview)
- **Error handling**: Display "I cannot find this information..." if retrieval returns empty or all chunks have high distance scores
- **Status messages**: Show "Retrieving context..." and "Generating response..." during processing

---

## Code Organization

Generate TWO files:

### File 1: `scripts/generation.py`
Contains:
- `generate(query: str, chroma_db_path: str, groq_api_key: str) -> Dict[str, str]`
  - Returns: `{"answer": "...", "sources": [...]}`
- Helper functions:
  - `_filter_low_relevance_chunks(chunks: List[Dict], max_distance: float = 0.7) -> List[Dict]`
    (Remove chunks with distance > threshold; weak signal)
  - `_format_sources(chunks: List[Dict]) -> str`
    (Return formatted source list)
  - `_validate_citations(response: str, chunks: List[Dict]) -> Dict`
    (Extract & validate citations; return {"valid": [...], "missing": [...]})

### File 2: `app.py`
Contains:
- Gradio interface using `gr.Interface()`
- Calls `generate()` from `scripts/generation.py`
- Handles environment variables (GROQ_API_KEY, CHROMA_PATH)
- Error handling for API failures, empty queries, etc.
- **Launch**: `gr.launch()` with `share=False` (local only)

---

## Specific Implementation Details

### System Prompt Structure
```python
SYSTEM_PROMPT = """
You are an expert guide for course and professor reviews. 
Your role is to help students make informed decisions about their academic path 
by synthesizing student opinions from actual course reviews.

CRITICAL RULES:
1. Answer ONLY using the provided review excerpts. Do NOT use your training data.
2. If the reviews do NOT contain information about the query, respond: 
   "I cannot find this information in the student reviews. Try asking about specific 
    professors, courses, workloads, or grading policies."
3. For every claim, include a citation in [brackets]: [source_file, chunk_index]
4. Be specific: reference professors by name, courses by code, and cite actual 
   student language when possible.

FORMAT YOUR RESPONSE AS:
[Direct answer to the question, grounded in retrieved context, with citations]
"""
```

### Groq API Call
```python
from groq import Groq

client = Groq(api_key=groq_api_key)
response = client.chat.completions.create(
    model="mistral-7b-instant",  # or "mixtral-8x7b-32768"
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    ],
    temperature=0.3,  # Low temp for factual, grounded responses
    max_tokens=500
)
answer = response.choices[0].message.content
```

### Context Formatting
Pass retrieved chunks to LLM as:
```
Context:
[Chunk 1]
Source: README.md, Chunk Index: 0
---
[Chunk 2]
Source: README.md, Chunk Index: 1
---
[Chunk 3]
Source: README.md, Chunk Index: 2
---

Question: {user_query}
```

### Low-Relevance Filtering
```python
def _filter_low_relevance_chunks(chunks, max_distance=0.7):
    """Remove chunks with weak semantic signal (distance > threshold)"""
    return [c for c in chunks if c['distance'] < max_distance]
```

---

## Error Handling

Handle these cases:
1. **Empty query**: "Please enter a question about courses or professors."
2. **No relevant chunks**: "I cannot find this information in the student reviews."
3. **API failure**: "Error contacting LLM. Please try again."
4. **Missing .env**: Raise clear error: "GROQ_API_KEY not found in .env"

---

## Validation Checklist (Read Generated Code Before Running)

- [ ] System prompt **forbids external knowledge** explicitly
- [ ] System prompt **requires citations in [brackets]**
- [ ] System prompt handles "I cannot find" case
- [ ] Source list is **programmatically constructed** from retrieved chunks (not extracted from LLM)
- [ ] Source list includes: source filename, chunk index, text preview (first 100 chars)
- [ ] Low-relevance filtering is applied (distance > 0.7 removed)
- [ ] Gradio interface has clear input/output sections
- [ ] Error messages guide user (empty query, no results, API failure)
- [ ] `.env` loading is robust (clear error if key missing)
- [ ] `app.py` imports work: `from scripts.generation import generate`

---

## Test Your Code Before Submission

```python
# Test 1: Grounding enforcement
query = "What is the weather like?"
# Expected: "I cannot find this in the student reviews."

# Test 2: Citation format
query = "What do students say about Professor Smith?"
# Expected: Answer with [source_file, chunk_index] format

# Test 3: Source list accuracy
# Expected: Sources match chunks passed to LLM, not fabricated

# Test 4: Low-relevance filtering
# Expected: Chunks with distance > 0.7 are excluded from context
```

---

## Go ahead and generate the code now.

Produce complete, runnable Python code for `scripts/generation.py` and `app.py`.
Include docstrings. Include error handling. Do NOT leave TODOs.

Once generated, I will:
1. Review the system prompt for grounding enforcement
2. Verify source attribution is programmatic
3. Test the Gradio interface
4. Validate outputs before submission
