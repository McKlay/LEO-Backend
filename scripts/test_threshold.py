"""Quick test to verify vector search works with threshold=0.5"""
import asyncio
from supabase import create_client
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

async def test():
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Generate embedding
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input="What is 13th month pay?",
        dimensions=1536
    )
    query_embedding = response.data[0].embedding
    
    # Search with threshold=0.5
    result = client.rpc('match_documents', {
        'query_embedding': query_embedding,
        'match_threshold': 0.5,
        'match_count': 5
    }).execute()
    
    print(f"Results with threshold=0.5: {len(result.data)}")
    for i, doc in enumerate(result.data):
        print(f"{i+1}. {doc['id']}: similarity={doc['similarity']:.3f}")

asyncio.run(test())
