"""
Test script to verify citation URLs are now coming from labor_law_sources table.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

async def main():
    print("🧪 Testing Citation URLs...")
    print("-" * 60)
    
    url = "http://localhost:8000/api/v1/chat/message/stream"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6IkF0"
    }
    payload = {
        "message": "What is overtime pay?",
        "conversation_id": "test-citation-urls",
        "language": "en"
    }
    
    print(f"📤 Sending query: '{payload['message']}'")
    print()
    
    citations = []
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    print(f"❌ Error: HTTP {response.status_code}")
                    text = await response.aread()
                    print(text.decode())
                    return
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    if line.startswith("event: "):
                        event_type = line.split("event: ")[1].strip()
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line.split("data: ", 1)[1]
                        try:
                            data = json.loads(data_str)
                            
                            if event_type == "citations":
                                citations = data
                                print("📚 Citations received!")
                                break
                        except json.JSONDecodeError:
                            continue
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return
    
    # Analyze citations
    print("\n" + "=" * 60)
    print("📊 CITATION URL ANALYSIS")
    print("=" * 60)
    
    if not citations:
        print("⚠️  No citations found in response!")
        return
    
    print(f"\n✅ Found {len(citations)} citation(s):\n")
    
    generic_count = 0
    specific_count = 0
    
    for idx, citation in enumerate(citations, 1):
        url = citation.get("url", "N/A")
        article = citation.get("article", "N/A")
        source = citation.get("source", "N/A")
        
        # Check if URL is generic or specific
        is_generic = "dole.gov.ph/labor-code" in url
        if is_generic:
            generic_count += 1
            status = "❌ GENERIC"
        else:
            specific_count += 1
            status = "✅ SPECIFIC"
        
        print(f"{status} Citation {idx}:")
        print(f"   Article: {article}")
        print(f"   Source: {source}")
        print(f"   URL: {url}")
        print()
    
    print("-" * 60)
    print(f"📈 Summary:")
    print(f"   Specific URLs: {specific_count}/{len(citations)}")
    print(f"   Generic URLs: {generic_count}/{len(citations)}")
    
    if specific_count == len(citations):
        print("\n🎉 SUCCESS! All citations have specific source URLs!")
    elif specific_count > 0:
        print(f"\n⚠️  PARTIAL: {specific_count} citations have specific URLs, {generic_count} are still generic")
    else:
        print("\n❌ FAILED: All citations still using generic URLs")
    
    print("\n✅ Test complete!")

if __name__ == "__main__":
    asyncio.run(main())
