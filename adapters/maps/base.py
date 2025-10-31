"""
Base interface for maps/location service adapters.

Defines the contract for location-based services,
enabling easy swapping between providers (Google Maps, etc.).
"""
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel


class PlaceResult(BaseModel):
    """Place search result."""
    
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    distance_meters: Optional[float] = None
    place_type: str  # e.g., "legal_aid", "lawyer", "government_office"


class BaseMaps(ABC):
    """
    Base maps/location service adapter interface.
    
    All maps implementations (Google Places, OpenStreetMap, etc.)
    should implement this interface.
    """
    
    @abstractmethod
    async def nearby_places(
        self,
        latitude: float,
        longitude: float,
        place_types: list[str],
        radius_meters: int = 5000,
        limit: int = 10
    ) -> list[PlaceResult]:
        """
        Find nearby places of specified types.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            place_types: Types of places to search for
            radius_meters: Search radius in meters
            limit: Maximum number of results
            
        Returns:
            List of nearby places
            
        Raises:
            ExternalServiceError: If search fails
        """
        pass
    
    @abstractmethod
    async def get_place_details(self, place_id: str) -> Optional[PlaceResult]:
        """
        Get detailed information about a place.
        
        Args:
            place_id: Place identifier
            
        Returns:
            Place details if found, None otherwise
            
        Raises:
            ExternalServiceError: If retrieval fails
        """
        pass
