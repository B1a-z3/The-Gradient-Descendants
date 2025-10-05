import os
import requests
import json
import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from fuzzywuzzy import fuzz, process
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ElectronicPart:
    """Data class for electronic parts"""
    part_number: str
    manufacturer: str
    description: str
    category: str
    price: Optional[float] = None
    stock: Optional[int] = None
    datasheet_url: Optional[str] = None
    image_url: Optional[str] = None
    specifications: Optional[Dict] = None

class MouserAPIClient:
    """Client for Mouser Electronics API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.mouser.com/api/v1"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def search_parts(self, search_term: str, limit: int = 20) -> List[ElectronicPart]:
        """Search for electronic parts using Mouser API"""
        try:
            # Try the correct Mouser API endpoint
            url = f"{self.base_url}/search/keyword"
            
            # Updated payload structure for Mouser API
            payload = {
                "SearchByKeywordRequest": {
                    "keyword": search_term,
                    "records": limit,
                    "startingRecord": 0
                }
            }
            
            # Add API key to headers
            headers = self.headers.copy()
            headers["apiKey"] = self.api_key
            
            response = requests.post(url, headers=headers, json=payload)
            
            # Log the response for debugging
            logger.info(f"Mouser API Response Status: {response.status_code}")
            
            if response.status_code == 404:
                logger.warning("Mouser API endpoint not found. Using fallback search.")
                return self._fallback_search(search_term, limit)
            
            response.raise_for_status()
            data = response.json()
            parts = []
            
            # Parse the response based on actual Mouser API structure
            if "SearchResults" in data and "Parts" in data["SearchResults"]:
                for part_data in data["SearchResults"]["Parts"]:
                    part = ElectronicPart(
                        part_number=part_data.get("MouserPartNumber", ""),
                        manufacturer=part_data.get("Manufacturer", ""),
                        description=part_data.get("Description", ""),
                        category=part_data.get("Category", ""),
                        price=self._extract_price(part_data.get("PriceBreaks", [])),
                        stock=part_data.get("Availability", {}).get("InStock", 0),
                        datasheet_url=part_data.get("DataSheetUrl", ""),
                        image_url=part_data.get("ImagePath", ""),
                        specifications=self._extract_specifications(part_data)
                    )
                    parts.append(part)
            else:
                logger.warning("Unexpected Mouser API response structure")
                return self._fallback_search(search_term, limit)
            
            return parts
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Mouser API: {e}")
            return self._fallback_search(search_term, limit)
        except Exception as e:
            logger.error(f"Unexpected error in search_parts: {e}")
            return self._fallback_search(search_term, limit)
    
    def _fallback_search(self, search_term: str, limit: int) -> List[ElectronicPart]:
        """Fallback search with sample data when API fails"""
        logger.info("Using fallback search with sample data")
        
        # Sample electronic parts for fallback
        sample_parts = [
            ElectronicPart(
                part_number="A000066",
                manufacturer="Arduino",
                description="Arduino Uno R3 Microcontroller Board",
                category="Development Boards",
                price=25.00,
                stock=150,
                datasheet_url="https://store.arduino.cc/products/arduino-uno-rev3",
                specifications={"Voltage": "5V", "Digital Pins": "14", "Analog Pins": "6"}
            ),
            ElectronicPart(
                part_number="LM358N",
                manufacturer="Texas Instruments",
                description="LM358 Dual Operational Amplifier",
                category="Amplifiers",
                price=0.50,
                stock=5000,
                datasheet_url="https://www.ti.com/lit/ds/symlink/lm358.pdf",
                specifications={"Supply Voltage": "3V to 32V", "Input Offset": "2mV", "Package": "DIP-8"}
            ),
            ElectronicPart(
                part_number="CF14JT10K0",
                manufacturer="Stackpole Electronics",
                description="10k Ohm Resistor 1/4W 5%",
                category="Resistors",
                price=0.10,
                stock=10000,
                specifications={"Resistance": "10k Ohm", "Power": "1/4W", "Tolerance": "5%"}
            ),
            ElectronicPart(
                part_number="ESP32-WROOM-32",
                manufacturer="Espressif",
                description="ESP32 WiFi & Bluetooth Module",
                category="Wireless Modules",
                price=8.50,
                stock=200,
                specifications={"WiFi": "802.11 b/g/n", "Bluetooth": "4.2", "CPU": "Dual-core 240MHz"}
            ),
            ElectronicPart(
                part_number="2N3904",
                manufacturer="ON Semiconductor",
                description="NPN General Purpose Transistor",
                category="Transistors",
                price=0.25,
                stock=2500,
                specifications={"Type": "NPN", "Vce": "40V", "Ic": "200mA", "Package": "TO-92"}
            )
        ]
        
        # Simple keyword matching
        search_lower = search_term.lower()
        matching_parts = []
        
        for part in sample_parts:
            if (search_lower in part.part_number.lower() or 
                search_lower in part.manufacturer.lower() or 
                search_lower in part.description.lower() or
                search_lower in part.category.lower()):
                matching_parts.append(part)
        
        # If no matches, return some sample parts
        if not matching_parts:
            matching_parts = sample_parts[:min(limit, len(sample_parts))]
        
        return matching_parts[:limit]
    
    def _extract_price(self, price_breaks: List[Dict]) -> Optional[float]:
        """Extract the lowest price from price breaks"""
        if not price_breaks:
            return None
        
        try:
            prices = [float(pb.get("Price", 0)) for pb in price_breaks if pb.get("Price")]
            return min(prices) if prices else None
        except (ValueError, TypeError):
            return None
    
    def _extract_specifications(self, part_data: Dict) -> Dict:
        """Extract specifications from part data"""
        specs = {}
        if "ProductAttributes" in part_data:
            for attr in part_data["ProductAttributes"]:
                specs[attr.get("AttributeName", "")] = attr.get("AttributeValue", "")
        return specs

class GeminiAIAssistant:
    """AI assistant using Google Gemini for context-aware search and recommendations"""
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def enhance_search_query(self, user_query: str, context: str = "") -> str:
        """Enhance user search query with AI assistance"""
        prompt = f"""
        You are an expert in electronic components and engineering. A user is searching for electronic parts with this query: "{user_query}"
        
        Context: {context}
        
        Please enhance this search query to be more specific and effective for finding electronic components. Consider:
        1. Technical specifications that might be implied
        2. Common part number patterns
        3. Manufacturer names
        4. Component categories
        
        Return only the enhanced search query, nothing else.
        """
        
        try:
            response = self.model.generate_content(prompt)
            enhanced_query = response.text.strip()
            
            # Validate the response
            if enhanced_query and len(enhanced_query) > 0:
                return enhanced_query
            else:
                logger.warning("Empty response from Gemini API, using original query")
                return user_query
                
        except Exception as e:
            logger.error(f"Error enhancing search query with Gemini: {e}")
            logger.info("Falling back to original query")
            return user_query
    
    def generate_recommendations(self, search_results: List[ElectronicPart], user_query: str) -> List[str]:
        """Generate personalized recommendations based on search results"""
        if not search_results:
            return []
        
        # Create a summary of search results
        results_summary = "\n".join([
            f"- {part.part_number} ({part.manufacturer}): {part.description}"
            for part in search_results[:10]
        ])
        
        prompt = f"""
        Based on the user's search query "{user_query}" and these search results:
        
        {results_summary}
        
        Provide 3-5 personalized recommendations for the user. Consider:
        1. Alternative parts that might be better suited
        2. Complementary components
        3. Cost-effective alternatives
        4. Higher quality options
        
        Format each recommendation as a brief sentence explaining why it's recommended.
        """
        
        try:
            response = self.model.generate_content(prompt)
            recommendations_text = response.text.strip()
            
            if recommendations_text:
                recommendations = [rec.strip() for rec in recommendations_text.split('\n') if rec.strip()]
                return recommendations[:5]  # Limit to 5 recommendations
            else:
                logger.warning("Empty recommendations from Gemini API")
                return self._fallback_recommendations(search_results, user_query)
                
        except Exception as e:
            logger.error(f"Error generating recommendations with Gemini: {e}")
            return self._fallback_recommendations(search_results, user_query)
    
    def _fallback_recommendations(self, search_results: List[ElectronicPart], user_query: str) -> List[str]:
        """Generate fallback recommendations when AI fails"""
        recommendations = []
        
        if search_results:
            # Get unique manufacturers
            manufacturers = list(set([part.manufacturer for part in search_results]))
            categories = list(set([part.category for part in search_results]))
            
            if manufacturers:
                recommendations.append(f"Consider other products from {manufacturers[0]} for similar quality")
            
            if categories:
                recommendations.append(f"Explore more {categories[0]} for your project needs")
            
            recommendations.append("Check datasheets for detailed specifications and compatibility")
            recommendations.append("Consider bulk pricing for multiple units")
        
        return recommendations[:3]
    
    def analyze_part_compatibility(self, part1: ElectronicPart, part2: ElectronicPart) -> str:
        """Analyze compatibility between two electronic parts"""
        prompt = f"""
        Analyze the compatibility between these two electronic parts:
        
        Part 1: {part1.part_number} ({part1.manufacturer}) - {part1.description}
        Part 2: {part2.part_number} ({part2.manufacturer}) - {part2.description}
        
        Provide a brief analysis of their compatibility and any considerations for using them together.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error analyzing part compatibility: {e}")
            return "Unable to analyze compatibility at this time."

class IntelligentSearchEngine:
    """Sophisticated search engine with fuzzy matching and context awareness"""
    
    def __init__(self, mouser_client: MouserAPIClient, gemini_assistant: GeminiAIAssistant):
        self.mouser_client = mouser_client
        self.gemini_assistant = gemini_assistant
        self.search_history = []
        self.user_preferences = {}
    
    def search(self, query: str, user_context: str = "", fuzzy_threshold: int = 80) -> Dict:
        """Perform intelligent search with fuzzy matching and AI enhancement"""
        
        # Store search in history
        self.search_history.append({
            "query": query,
            "context": user_context,
            "timestamp": pd.Timestamp.now()
        })
        
        # Enhance query with AI
        enhanced_query = self.gemini_assistant.enhance_search_query(query, user_context)
        
        # Search Mouser API
        raw_results = self.mouser_client.search_parts(enhanced_query)
        
        # Apply fuzzy matching for better results
        filtered_results = self._apply_fuzzy_matching(raw_results, query, fuzzy_threshold)
        
        # Generate AI recommendations
        recommendations = self.gemini_assistant.generate_recommendations(filtered_results, query)
        
        return {
            "original_query": query,
            "enhanced_query": enhanced_query,
            "results": filtered_results,
            "recommendations": recommendations,
            "total_found": len(filtered_results),
            "search_context": user_context
        }
    
    def _apply_fuzzy_matching(self, results: List[ElectronicPart], query: str, threshold: int) -> List[ElectronicPart]:
        """Apply fuzzy matching to filter and rank results"""
        if not results:
            return results
        
        # Create searchable text for each part
        searchable_texts = []
        for part in results:
            text = f"{part.part_number} {part.manufacturer} {part.description} {part.category}"
            searchable_texts.append(text)
        
        # Calculate fuzzy match scores
        scores = []
        for text in searchable_texts:
            score = fuzz.partial_ratio(query.lower(), text.lower())
            scores.append(score)
        
        # Filter and sort by score
        filtered_results = []
        for part, score in zip(results, scores):
            if score >= threshold:
                filtered_results.append((part, score))
        
        # Sort by score (highest first)
        filtered_results.sort(key=lambda x: x[1], reverse=True)
        
        return [part for part, score in filtered_results]
    
    def get_similar_parts(self, part_number: str, limit: int = 5) -> List[ElectronicPart]:
        """Find similar parts based on a reference part"""
        # First, search for the exact part
        exact_results = self.mouser_client.search_parts(part_number, limit=1)
        
        if not exact_results:
            return []
        
        reference_part = exact_results[0]
        
        # Search for similar parts using manufacturer and category
        similar_query = f"{reference_part.manufacturer} {reference_part.category}"
        similar_results = self.mouser_client.search_parts(similar_query, limit=limit * 2)
        
        # Filter out the exact match and apply similarity scoring
        filtered_results = []
        for part in similar_results:
            if part.part_number != reference_part.part_number:
                # Calculate similarity based on description and specifications
                similarity = fuzz.ratio(reference_part.description, part.description)
                if similarity > 60:  # Threshold for similarity
                    filtered_results.append((part, similarity))
        
        # Sort by similarity and return top results
        filtered_results.sort(key=lambda x: x[1], reverse=True)
        return [part for part, score in filtered_results[:limit]]

class RecommendationEngine:
    """Personalized recommendation system"""
    
    def __init__(self, search_engine: IntelligentSearchEngine):
        self.search_engine = search_engine
        self.user_profiles = {}
        self.part_interactions = {}
    
    def update_user_profile(self, user_id: str, search_history: List[Dict], preferences: Dict):
        """Update user profile based on search history and preferences"""
        self.user_profiles[user_id] = {
            "search_history": search_history,
            "preferences": preferences,
            "favorite_categories": self._extract_favorite_categories(search_history),
            "preferred_manufacturers": self._extract_preferred_manufacturers(search_history)
        }
    
    def get_personalized_recommendations(self, user_id: str, current_query: str = "") -> List[str]:
        """Generate personalized recommendations for a user"""
        if user_id not in self.user_profiles:
            return []
        
        profile = self.user_profiles[user_id]
        
        # Analyze user's search patterns
        recent_searches = profile["search_history"][-10:]  # Last 10 searches
        
        recommendations = []
        
        # Category-based recommendations
        if profile["favorite_categories"]:
            for category in profile["favorite_categories"][:3]:
                search_results = self.search_engine.search(category)
                if search_results["results"]:
                    top_part = search_results["results"][0]
                    recommendations.append(f"Popular in {category}: {top_part.part_number} - {top_part.description}")
        
        # Manufacturer-based recommendations
        if profile["preferred_manufacturers"]:
            for manufacturer in profile["preferred_manufacturers"][:2]:
                search_results = self.search_engine.search(manufacturer)
                if search_results["results"]:
                    top_part = search_results["results"][0]
                    recommendations.append(f"From {manufacturer}: {top_part.part_number} - {top_part.description}")
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def _extract_favorite_categories(self, search_history: List[Dict]) -> List[str]:
        """Extract favorite categories from search history"""
        categories = []
        for search in search_history:
            # This would need to be enhanced with actual category extraction
            # For now, we'll use a simple approach
            query = search["query"].lower()
            if "resistor" in query:
                categories.append("Resistors")
            elif "capacitor" in query:
                categories.append("Capacitors")
            elif "transistor" in query:
                categories.append("Transistors")
            elif "ic" in query or "integrated circuit" in query:
                categories.append("Integrated Circuits")
        
        # Count frequency and return most common
        from collections import Counter
        category_counts = Counter(categories)
        return [cat for cat, count in category_counts.most_common(5)]
    
    def _extract_preferred_manufacturers(self, search_history: List[Dict]) -> List[str]:
        """Extract preferred manufacturers from search history"""
        manufacturers = []
        for search in search_history:
            # This would need to be enhanced with actual manufacturer extraction
            # For now, we'll use common manufacturer names
            query = search["query"].lower()
            common_manufacturers = ["ti", "texas instruments", "analog devices", "maxim", "linear", "stmicroelectronics", "infineon", "nxp"]
            for mfg in common_manufacturers:
                if mfg in query:
                    manufacturers.append(mfg.title())
        
        # Count frequency and return most common
        from collections import Counter
        mfg_counts = Counter(manufacturers)
        return [mfg for mfg, count in mfg_counts.most_common(5)]

# Main application class
class MouserSearchApp:
    """Main application class that orchestrates all components"""
    
    def __init__(self, mouser_api_key: str, gemini_api_key: str):
        self.mouser_client = MouserAPIClient(mouser_api_key)
        self.gemini_assistant = GeminiAIAssistant(gemini_api_key)
        self.search_engine = IntelligentSearchEngine(self.mouser_client, self.gemini_assistant)
        self.recommendation_engine = RecommendationEngine(self.search_engine)
    
    def search_parts(self, query: str, user_id: str = "default", context: str = "") -> Dict:
        """Main search function"""
        # Perform intelligent search
        search_results = self.search_engine.search(query, context)
        
        # Get personalized recommendations
        personalized_recs = self.recommendation_engine.get_personalized_recommendations(user_id, query)
        
        # Update user profile
        self.recommendation_engine.update_user_profile(
            user_id, 
            self.search_engine.search_history, 
            {}
        )
        
        return {
            **search_results,
            "personalized_recommendations": personalized_recs
        }
    
    def get_part_details(self, part_number: str) -> Optional[ElectronicPart]:
        """Get detailed information about a specific part"""
        results = self.mouser_client.search_parts(part_number, limit=1)
        return results[0] if results else None
    
    def find_similar_parts(self, part_number: str) -> List[ElectronicPart]:
        """Find similar parts to a given part number"""
        return self.search_engine.get_similar_parts(part_number)

# Example usage
if __name__ == "__main__":
    # Initialize the application
    app = MouserSearchApp(
        mouser_api_key="d99c4255-03a1-495a-8a37-c317fa862ab2",
        gemini_api_key="AIzaSyDcGNx1RsNgWOC9K-7bH40fdnRqm4vqtTs"
    )
    
    # Example search
    print("Searching for 'Arduino Uno'...")
    results = app.search_parts("Arduino Uno", user_id="user1", context="prototyping project")
    
    print(f"\nFound {results['total_found']} results")
    print(f"Enhanced query: {results['enhanced_query']}")
    
    print("\nTop 3 results:")
    for i, part in enumerate(results['results'][:3], 1):
        print(f"{i}. {part.part_number} - {part.manufacturer}")
        print(f"   {part.description}")
        print(f"   Price: ${part.price}" if part.price else "   Price: N/A")
        print()
    
    print("AI Recommendations:")
    for rec in results['recommendations']:
        print(f"- {rec}")
    
    print("\nPersonalized Recommendations:")
    for rec in results['personalized_recommendations']:
        print(f"- {rec}")
