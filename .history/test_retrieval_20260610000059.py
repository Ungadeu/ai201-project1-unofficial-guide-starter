#!/usr/bin/env python3
"""
Test script demonstrating retrieval with multiple queries.
Run this after embedding_and_retrieval.py has created the vector store.
"""

from scripts.embedding_and_retrieval import retrieve

def test_retrieval():
    """Test the retrieval function with various queries."""
    
    CHROMA_PATH = "data/chroma_db"
    
    # Test queries covering different aspects of the corpus
    test_queries = [
        "What is the workload for CS core classes?",
        "Which professors are recommended for electives?",
        "How difficult is Math 242?",
        "What do students say about exam formats?",
        "Are lectures mandatory?",
    ]
    
    print("=" * 80)
    print("RETRIEVAL TEST: Multi-Query Demonstration")
    print("=" * 80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Query {i}] {query}")
        print("-" * 80)
        
        results = retrieve(query, CHROMA_PATH, top_k=2)
        
        if not results:
            print("No results found.")
            continue
        
        for j, result in enumerate(results, 1):
            print(f"\nResult {j}:")
            print(f"  Source: {result['source']} (chunk {result['chunk_index']})")
            print(f"  Distance: {result['distance']:.4f} (lower = more relevant)")
            print(f"  Location: chars {result['start']}-{result['end']}")
            print(f"  Text preview: {result['text'][:150]}...")
    
    print("\n" + "=" * 80)
    print("Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_retrieval()
