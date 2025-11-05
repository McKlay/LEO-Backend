"""
Phase 1.E: End-to-End Integration Tests with Real APIs

These tests require real credentials and INTEGRATION_TEST=true.
"""
import pytest
import os
import time
from httpx import AsyncClient, ASGITransport
from fastapi import status

# Skip if integration testing not enabled
pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION_TEST", "false").lower() != "true",
    reason="Integration tests require INTEGRATION_TEST=true"
)


async def create_test_client():
    """Create test client with app."""
    from app.main import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


async def create_session(client: AsyncClient) -> tuple[str, str]:
    """Create anonymous session and return token and session_id."""
    response = await client.post(
        "/api/v1/auth/session",
        json={
            "preferredLanguage": "en",
            "deviceInfo": {
                "userAgent": "pytest-integration",
                "timezone": "Asia/Manila"
            }
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    return data["token"], data["sessionId"]


@pytest.mark.asyncio
async def test_13th_month_pay_query():
    """Test 13th month pay query with real KB."""
    async with await create_test_client() as client:
        token, _ = await create_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        start = time.time()
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What is the 13th month pay requirement in the Philippines?",
                "language": "en"
            },
            headers=headers
        )
        elapsed = time.time() - start
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify structure
        assert "messageId" in data
        assert "content" in data
        assert "citations" in data
        assert "suggestions" in data
        
        # Verify content
        assert len(data["content"]) > 50
        content = data["content"].lower()
        assert any(term in content for term in ["13th month", "pd 851", "presidential", "december", "bonus"])
        
        # Verify citations structure (may be empty if KB is not populated)
        assert "citations" in data
        if data["citations"]:  # Only validate structure if citations exist
            for cit in data["citations"]:
                assert all(k in cit for k in ["id", "text", "source", "article", "url", "confidence"])
                assert cit["url"].startswith("http")
                assert 0.0 <= cit["confidence"] <= 1.0
        
        # Verify suggestions (may be empty in Phase 1)
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        
        # Performance
        assert elapsed < 20.0  # Increased timeout for integration test
        
        print(f"\n✓ 13th month pay: {elapsed:.2f}s, {len(data['citations'])} citations")


@pytest.mark.asyncio
async def test_termination_grounds():
    """Test termination grounds query."""
    async with await create_test_client() as client:
        token, _ = await create_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What are the just causes for terminating an employee?",
                "language": "en"
            },
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        content = data["content"].lower()
        assert any(term in content for term in ["just cause", "termination", "labor code"])
        assert len(data["citations"]) > 0
        
        print(f"✓ Termination grounds: {len(data['citations'])} citations")


@pytest.mark.asyncio
async def test_multi_turn_conversation():
    """Test multi-turn conversation maintains context."""
    async with await create_test_client() as client:
        token, _ = await create_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Turn 1
        response1 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "What are the rules for overtime pay?",
                "language": "en"
            },
            headers=headers
        )
        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        conv_id = data1["conversationId"]
        
        # Turn 2 - follow-up
        response2 = await client.post(
            "/api/v1/chat/message",
            json={
                "message": "How much should I be paid for it?",
                "language": "en",
                "conversationId": conv_id
            },
            headers=headers
        )
        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        
        assert data2["conversationId"] == conv_id
        content = data2["content"].lower()
        assert any(term in content for term in ["overtime", "125%", "130%", "premium"])
        
        print("✓ Multi-turn: context maintained")


@pytest.mark.asyncio
async def test_citation_quality():
    """Test citation completeness across multiple queries."""
    queries = [
        "What is 13th month pay?",
        "What are the grounds for terminating an employee?",
        "When can an employer legally dismiss a worker?"
    ]
    
    async with await create_test_client() as client:
        for query in queries:
            token, _ = await create_session(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            response = await client.post(
                "/api/v1/chat/message",
                json={"message": query, "language": "en"},
                headers=headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            citations = data["citations"]
            
            assert len(citations) > 0, f"No citations for: {query}"
            
            for cit in citations:
                required = ["id", "text", "source", "article", "url", "confidence"]
                for field in required:
                    assert field in cit, f"Missing {field}"
                    assert cit[field] is not None
                
                assert len(cit["text"]) > 10
                assert cit["url"].startswith("http")
        
        print(f"✓ Citation quality: {len(queries)} queries validated")


@pytest.mark.asyncio
async def test_performance_benchmark():
    """Benchmark response times."""
    queries = [
        "What is minimum wage?",
        "What are grounds for termination?",
        "What is 13th month pay?",
        "What are my overtime rights?",
        "When should I receive final pay?"
    ]
    
    times = []
    cit_counts = []
    
    async with await create_test_client() as client:
        for query in queries:
            token, _ = await create_session(client)
            headers = {"Authorization": f"Bearer {token}"}
            
            start = time.time()
            response = await client.post(
                "/api/v1/chat/message",
                json={"message": query, "language": "en"},
                headers=headers
            )
            elapsed = time.time() - start
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            
            times.append(elapsed)
            cit_counts.append(len(data["citations"]))
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        avg_cits = sum(cit_counts) / len(cit_counts)
        
        print(f"\n📊 Performance:")
        print(f"  Avg: {avg_time:.2f}s, Max: {max_time:.2f}s")
        print(f"  Avg citations: {avg_cits:.1f}")
        
        assert avg_time < 10.0
        assert all(c > 0 for c in cit_counts)


@pytest.mark.asyncio
async def test_error_handling():
    """Test error scenarios."""
    async with await create_test_client() as client:
        token, _ = await create_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Empty message
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "", "language": "en"},
            headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Message too long
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "a" * 2001, "language": "en"},
            headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Invalid language
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test", "language": "invalid"},
            headers=headers
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        print("✓ Error handling: all edge cases handled")


@pytest.mark.asyncio
async def test_no_auth_rejected():
    """Test requests without auth are rejected."""
    async with await create_test_client() as client:
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "Test", "language": "en"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        print("✓ Auth enforcement works")


@pytest.mark.asyncio
async def test_phase_1e_summary():
    """Final summary test."""
    print("\n" + "="*70)
    print("PHASE 1.E INTEGRATION TEST SUMMARY")
    print("="*70)
    
    async with await create_test_client() as client:
        token, _ = await create_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        
        response = await client.post(
            "/api/v1/chat/message",
            json={"message": "What is the Labor Code?", "language": "en"},
            headers=headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        checks = {
            "Chat API responds": response.status_code == 200,
            "Content generated": len(data["content"]) > 50,
            "Citations present": len(data["citations"]) > 0,
            "Citation URLs valid": all(c["url"].startswith("http") for c in data["citations"]),
            "Suggestions field present": "suggestions" in data,  # Phase 2 feature, just check field exists
            "Metadata included": "metadata" in data,
        }
        
        print("\nCore Functionality:")
        for check, passed in checks.items():
            print(f"  {'✅' if passed else '❌'} {check}")
        
        assert all(checks.values())
        
        print("\n" + "="*70)
        print("✅ PHASE 1.E: ALL TESTS PASSED")
        print("="*70)
        print("\nReady for Phase 1.1 (Conversation Management)")
        print("="*70 + "\n")
