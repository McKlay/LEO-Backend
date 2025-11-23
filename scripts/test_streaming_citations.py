"""
Test streaming and citation functionality - Step 5 diagnostics
Run this to verify backend SSE streaming and citation format
"""
import asyncio
import httpx
import json
import time
from typing import AsyncIterator
from datetime import datetime, timedelta
from jose import jwt

# Import settings to get JWT secret
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings

def generate_test_token():
    """Generate a valid JWT token for testing"""
    expires_at = datetime.utcnow() + timedelta(hours=1)
    payload = {
        "sub": "test-user-123",
        "session_id": "test-session-123",
        "language": "en",
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "type": "anonymous"
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

async def test_streaming_endpoint():
    """Test SSE streaming from /v1/chat/message/stream endpoint"""
    print("=" * 60)
    print("TEST 1: SSE Streaming Functionality")
    print("=" * 60)
    
    token = generate_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = "http://localhost:8000/api/v1/chat/message/stream"
    payload = {
        "message": "What is overtime pay?",
        "conversation_id": "test-streaming-123"
    }
    
    print(f"\n📤 Sending request to: {url}")
    print(f"🔑 Auth: Bearer {token[:10]}...")
    print(f"📝 Query: {payload['message']}\n")
    
    tokens = []
    citations = []
    first_token_time = None
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                print(f"✅ Response status: {response.status_code}")
                print(f"📋 Content-Type: {response.headers.get('content-type')}\n")
                
                if response.status_code != 200:
                    print(f"❌ ERROR: Expected 200, got {response.status_code}")
                    body = await response.aread()
                    print(f"Response body: {body.decode()}")
                    return
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                if 'text/event-stream' not in content_type:
                    print(f"⚠️  WARNING: Content-Type is not 'text/event-stream'")
                    print(f"   Got: {content_type}")
                    print("   Frontend may not recognize as streaming response!\n")
                
                import time
                start_time = time.time()
                
                print("🔄 Streaming response:\n")
                event_type = None
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    # Parse SSE format: "event: type" and "data: json"
                    if line.startswith("event: "):
                        event_type = line[7:]
                    
                    elif line.startswith("data: "):
                        data_str = line[6:]
                        
                        # Record first token time
                        if first_token_time is None and event_type == "content_chunk":
                            first_token_time = time.time() - start_time
                        
                        try:
                            data = json.loads(data_str)
                            
                            if event_type == "metadata":
                                print(f"📊 Metadata: {data}")
                            
                            elif event_type == "status":
                                print(f"ℹ️  Status: {data.get('message')} ({data.get('step')})")
                            
                            elif event_type == "content_chunk":
                                chunk = data.get("chunk", "")
                                tokens.append(chunk)
                                print(chunk, end="", flush=True)
                            
                            elif event_type == "citations":
                                citations = data.get("citations", [])
                                print("\n\n📚 Citations received:")
                                for i, cite in enumerate(citations, 1):
                                    print(f"\n  [{i}] {cite.get('title', 'No title')}")
                                    print(f"      Article: {cite.get('article_id', 'N/A')}")
                                    print(f"      Source: {cite.get('source', 'N/A')}")
                                    excerpt = cite.get('excerpt', '')
                                    if excerpt:
                                        preview = excerpt[:80] + "..." if len(excerpt) > 80 else excerpt
                                        print(f"      Excerpt: {preview}")
                            
                            elif event_type == "complete":
                                print("\n\n✅ Stream completed")
                        
                        except json.JSONDecodeError as e:
                            print(f"\n⚠️  Failed to parse SSE data: {data_str}")
                            print(f"   Error: {e}")
        
        # Summary
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("STREAMING SUMMARY")
        print("=" * 60)
        print(f"✅ Total tokens received: {len(tokens)}")
        print(f"✅ Citations received: {len(citations)}")
        print(f"⏱️  Time to first token: {first_token_time:.2f}s")
        print(f"⏱️  Total response time: {total_time:.2f}s")
        
        # Validation
        print("\n" + "=" * 60)
        print("VALIDATION")
        print("=" * 60)
        
        if len(tokens) > 0:
            print("✅ Streaming working: YES")
        else:
            print("❌ Streaming working: NO (no tokens received)")
        
        if first_token_time and first_token_time < 3.5:
            print(f"✅ First token < 3.5s: YES ({first_token_time:.2f}s)")
        elif first_token_time:
            print(f"⚠️  First token < 3.5s: NO ({first_token_time:.2f}s)")
        else:
            print("⚠️  First token < 3.5s: NO (N/A)")
        
        if len(citations) >= 3:
            print(f"✅ Citations >= 3: YES ({len(citations)} citations)")
        else:
            print(f"⚠️  Citations >= 3: NO ({len(citations)} citations)")
        
        # Check citation format
        if citations:
            print("\n" + "=" * 60)
            print("CITATION FORMAT CHECK")
            print("=" * 60)
            
            required_fields = ['article_id', 'title', 'excerpt', 'source']
            for i, cite in enumerate(citations, 1):
                print(f"\nCitation {i}:")
                for field in required_fields:
                    if field in cite:
                        print(f"  ✅ {field}: present")
                    else:
                        print(f"  ❌ {field}: MISSING")
    
    except httpx.TimeoutException:
        print("❌ Request timed out (>30s)")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def test_clarification():
    """Test vague query clarification"""
    print("\n\n" + "=" * 60)
    print("TEST 2: Clarification Flow")
    print("=" * 60)
    
    token = generate_test_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    url = "http://localhost:8000/api/v1/chat/message/stream"
    payload = {
        "message": "Tell me about leave",
        "conversation_id": "test-clarify-456"
    }
    
    print(f"\n📤 Sending vague query: {payload['message']}\n")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                import time
                start_time = time.time()
                
                full_response = []
                event_type = None
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        event_type = line[7:]
                    elif line.startswith("data: "):
                        data = json.loads(line[6:])
                        if event_type == "content_chunk":
                            full_response.append(data["chunk"])
                        elif event_type == "complete" and not full_response:
                            # Capture content from complete event if no chunks were received (e.g. clarification)
                            full_response.append(data.get("content", ""))
                
                response_time = time.time() - start_time
                complete_text = "".join(full_response)
                
                print("📝 Response:")
                print(complete_text)
                print(f"\n⏱️  Response time: {response_time:.2f}s")
                
                # Check for clarification keywords
                clarification_keywords = ['clarify', 'specific', 'which type', 'could you', 'mean']
                has_clarification = any(kw in complete_text.lower() for kw in clarification_keywords)
                
                print("\n" + "=" * 60)
                print("VALIDATION")
                print("=" * 60)
                
                if has_clarification:
                    print("✅ Clarification triggered: YES")
                else:
                    print("⚠️  Clarification triggered: MAYBE (check response above)")
                
                if response_time < 1.5:
                    print(f"✅ Response < 1.5s: YES ({response_time:.2f}s)")
                else:
                    print(f"⚠️  Response < 1.5s: NO ({response_time:.2f}s)")
    
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_health():
    """Quick health check"""
    print("\n" + "=" * 60)
    print("HEALTH CHECK")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/api/v1/healthz")
            print(f"✅ Backend reachable: {response.status_code == 200}")
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        print("   Make sure backend is running on port 8000")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("STEP 5: STREAMING & CITATION DIAGNOSTICS")
    print("=" * 60)
    print("This script tests backend functionality before frontend integration\n")
    
    # Health check first
    await test_health()
    
    # Main tests
    await test_streaming_endpoint()
    await test_clarification()
    
    print("\n\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review validation results above")
    print("2. Fix any critical issues (streaming, citations)")
    print("3. Test with actual frontend")
    print("4. Document issues in STEP_5_FRONTEND_TESTING_GUIDE.md")


if __name__ == "__main__":
    asyncio.run(main())
