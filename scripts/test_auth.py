"""
Quick test script to verify authentication setup.
"""
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.containers import get_session_service


async def test_auth():
    """Test authentication setup."""
    print("Testing authentication setup...")
    
    try:
        # Get session service
        session_service = get_session_service()
        print("✓ Session service initialized")
        
        # Create anonymous session
        session = await session_service.create_anonymous_session(
            language="en",
            metadata={"test": True}
        )
        
        print(f"✓ Session created: {session['sessionId']}")
        print(f"  Language: {session['language']}")
        print(f"  Expires: {session['expiresAt']}")
        print(f"  Token (first 20 chars): {session['token'][:20]}...")
        
        # Validate the token
        payload = await session_service.validate_token(session['token'])
        print(f"✓ Token validated successfully")
        print(f"  User ID: {payload['sub']}")
        print(f"  Type: {payload['type']}")
        
        print("\n✅ All authentication tests passed!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_auth())
