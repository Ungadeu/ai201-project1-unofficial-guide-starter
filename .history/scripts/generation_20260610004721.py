#!/usr/bin/env python3
"""
Generation module for the course review RAG system.
Generates answers grounded in retrieved context chunks from Groq LLM.
Enforces grounding: answers only use retrieved context, not external knowledge.
"""

import os
import re
import sys
from typing import List, Dict
from groq import Groq

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.embedding_and_retrieval import retrieve

PROMPT_TEMPLATE = """
You are a helpful assistant.

Context:
{context}

Question:
{question}

Answer the question using only the information in the provided documents.
If the documents don't contain enough information to answer, say "I don't have enough information on that."

For any answer you provide, include source citations in the form [source, chunk].
If you use multiple documents, cite each one.
"""

MODEL_NAME = "llama-3.3-70b-versatile"


def _filter_low_relevance_chunks(chunks: List[Dict], max_distance: float = 0.7) -> List[Dict]:
    """
    Filter out chunks with weak semantic signal (distance > threshold).
    High distance = low relevance to query.
    
    Args:
        chunks: List of retrieved chunks with distance scores
        max_distance: Threshold above which to exclude chunks (default 0.7)
    
    Returns:
        Filtered list of high-relevance chunks
    """
    filtered = [c for c in chunks if c['distance'] < max_distance]
    return filtered


def _format_context_for_llm(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks into context string for LLM.
    Includes source attribution so LLM knows where to cite from.
    
    Args:
        chunks: List of retrieved chunks
    
    Returns:
        Formatted context string with source labels
    """
    if not chunks:
        return "[No relevant context found]"
    
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk['source']
        chunk_idx = chunk['chunk_index']
        text = chunk['text']
        context_parts.append(f"[Context {i}]\nSource: {source}, Chunk Index: {chunk_idx}\n{text}\n")
    
    return "\n---\n".join(context_parts)


def _extract_and_validate_citations(response: str, chunks: List[Dict]) -> Dict:
    """
    Extract citations from LLM response and validate they match retrieved chunks.
    
    Args:
        response: LLM-generated answer text
        chunks: List of retrieved chunks (source of truth for valid citations)
    
    Returns:
        Dict with keys:
            - "valid_citations": List of citations found in chunks
            - "invalid_citations": List of citations NOT in chunks (hallucinated)
            - "missing_sources": Sources that should have been cited but weren't
    """
    # Extract [source, chunk] patterns from response
    citation_pattern = r'\[([^,\]]+),\s*chunk\s*(\d+)\]'
    found_citations = re.findall(citation_pattern, response)
    
    # Build map of valid citations from retrieved chunks
    valid_citations_set = {(c['source'], str(c['chunk_index'])) for c in chunks}
    
    extracted = {
        'valid_citations': [],
        'invalid_citations': [],
        'missing_sources': list(valid_citations_set - {(s, idx) for s, idx in found_citations})
    }
    
    for source, chunk_idx in found_citations:
        if (source, chunk_idx) in valid_citations_set:
            extracted['valid_citations'].append((source, chunk_idx))
        else:
            extracted['invalid_citations'].append((source, chunk_idx))
    
    return extracted


def _format_source_list(chunks: List[Dict]) -> str:
    """
    Format retrieved chunks as a structured source list.
    Programmatically constructed from actual chunks, not extracted from LLM.
    
    Args:
        chunks: List of retrieved chunks
    
    Returns:
        Formatted source list string
    """
    if not chunks:
        return "No sources retrieved."
    
    source_lines = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk['source']
        chunk_idx = chunk['chunk_index']
        text_preview = chunk['text'][:120].replace('\n', ' ')
        distance = chunk['distance']
        
        source_lines.append(
            f"{i}. **{source}** (chunk {chunk_idx})\n"
            f"   Relevance: {distance:.2f} (0=perfect, 1=weak)\n"
            f"   Text: \"{text_preview}...\"\n"
        )
    
    return "\n".join(source_lines)


def _format_source_names(chunks: List[Dict]) -> str:
    """
    Build a short text listing the unique source documents used for the answer.
    """
    unique_sources = []
    for chunk in chunks:
        if chunk['source'] not in unique_sources:
            unique_sources.append(chunk['source'])
    return ", ".join(unique_sources) if unique_sources else "No sources retrieved."


def generate(query: str, chroma_db_path: str = "data/chroma_db", top_k: int = 5) -> Dict[str, str]:
    """
    Generate a grounded answer to a user query using Groq LLM and retrieved context.
    
    The answer is guaranteed to be based only on retrieved context chunks.
    Source attribution is programmatically constructed and verified.
    
    Args:
        query: User's question about courses/professors
        chroma_db_path: Path to ChromaDB vector store
        top_k: Number of chunks to retrieve (default 5)
    
    Returns:
        Dict with keys:
            - "answer": LLM-generated response grounded in context
            - "sources": Formatted source list
            - "citations": Dict with valid/invalid/missing citations
            - "error": Error message (if any)
    
    Raises:
        ValueError: If GROQ_API_KEY not in environment
    """
    # Check for API key
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError(
            "GROQ_API_KEY not found in environment. "
            "Add it to .env file or set as environment variable."
        )
    
    # Validate input
    if not query or not query.strip():
        return {
            "answer": "Please enter a question about courses, professors, workloads, or grading policies.",
            "sources": "",
            "citations": {},
            "error": None
        }
    
    # Retrieve relevant chunks
    retrieved_chunks = retrieve(query, chroma_db_path, top_k=top_k)
    
    # Filter low-relevance chunks (distance > 0.8 = weak signal)
    high_relevance_chunks = _filter_low_relevance_chunks(retrieved_chunks, max_distance=0.8)
    
    if not high_relevance_chunks:
        return {
            "answer": (
                "I cannot find this information in the student reviews. "
                "Try asking about specific professors, courses, workloads, exam formats, "
                "grading policies, or lecture attendance requirements."
            ),
            "sources": "",
            "citations": {},
            "error": "No high-relevance chunks retrieved (all distances > 0.8)"
        }
    
    # Fill in the retrieved chunk texts
    retrieved_chunks_list = [chunk['text'] for chunk in high_relevance_chunks]
    retrieved_chunks = "\n\n".join(retrieved_chunks_list)
    prompt = PROMPT_TEMPLATE.format(context=retrieved_chunks, question=query)

    # Call Groq LLM
    try:
        client = Groq(api_key=groq_api_key)
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {
            "answer": "Error contacting the LLM. Please try again.",
            "sources": "",
            "citations": {},
            "error": f"Groq API error: {str(e)}"
        }
    
    # Validate citations (catch hallucinations)
    citations = _extract_and_validate_citations(answer, high_relevance_chunks)
    
    # Format source list (programmatically constructed, not from LLM)
    sources = _format_source_list(high_relevance_chunks)
    source_names = _format_source_names(high_relevance_chunks)
    if source_names:
        answer = f"{answer}\n\nSources used: {source_names}"
    
    return {
        "answer": answer,
        "sources": sources,
        "citations": citations,
        "error": None
    }


if __name__ == "__main__":
    # Example usage
    test_query = "What do students say about exam difficulty?"
    result = generate(test_query)
    
    print("=" * 80)
    print("GENERATION TEST")
    print("=" * 80)
    print(f"\nQuery: {test_query}\n")
    print("ANSWER:")
    print(result['answer'])
    print("\nSOURCES:")
    print(result['sources'])
    if result['citations']['invalid_citations']:
        print(f"\n⚠️  Invalid citations (hallucinations): {result['citations']['invalid_citations']}")
    if result['error']:
        print(f"\nError: {result['error']}")
