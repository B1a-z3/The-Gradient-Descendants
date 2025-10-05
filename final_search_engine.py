#!/usr/bin/env python3
"""
Final Working Mouser Search Engine - Interactive Version
"""

import os
import json
import requests
import google.generativeai as genai

# Load API keys
MOUSER_API_KEY = "d99c4255-03a1-495a-8a37-c317fa862ab2"
GEMINI_API_KEY = "AIzaSyDcGNx1RsNgWOC9K-7bH40fdnRqm4vqtTs"

# Mouser API endpoint
MOUSER_API_URL = "https://api.mouser.com/api/v1.0/search/partnumber"

def search_mouser_parts(search_keyword: str, limit: int = 50):
    """Searches for parts on Mouser using a specific keyword."""
    if not MOUSER_API_KEY:
        return {"error": "Mouser API key is not set."}

    headers = {'Content-Type': 'application/json'}
    
    # Try keyword search first (broader search)
    body = {
        "SearchByKeywordRequest": {
            "keyword": search_keyword,
            "records": limit,
            "startingRecord": 0
        }
    }

    try:
        # Try keyword search endpoint first
        keyword_url = "https://api.mouser.com/api/v1/search/keyword"
        response = requests.post(
            f"{keyword_url}?apiKey={MOUSER_API_KEY}",
            headers=headers,
            data=json.dumps(body)
        )
        
        if response.status_code == 200:
            return response.json()
        
        # If keyword search fails, try part number search
        print(f"Keyword search failed (status {response.status_code}), trying part number search...")
        
        part_body = {
            "SearchByPartRequest": {
                "mouserPartNumber": search_keyword,
                "partSearchOptions": "string"
            }
        }
        
        response = requests.post(
            f"{MOUSER_API_URL}?apiKey={MOUSER_API_KEY}",
            headers=headers,
            data=json.dumps(part_body)
        )
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.HTTPError as http_err:
        return {"error": f"HTTP error occurred: {http_err}"}
    except Exception as err:
        return {"error": f"An other error occurred: {err}"}

def get_search_terms_from_query(natural_language_query: str) -> str:
    """Uses Gemini to convert a natural language query into specific search terms."""
    if not GEMINI_API_KEY:
        return simple_search_enhancement(natural_language_query)

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Try different model names
        model_names = ["gemini-1.5-flash", "gemini-1.0-pro", "gemini-pro"]
        
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name=model_name)
                prompt = f"""
                You are an expert electronics engineer assistant. Your task is to translate a user's natural language request for an electronic component into a precise search keyword for the Mouser Electronics API. Return ONLY the most likely search keyword (like a part number, component type, or key spec) and nothing else.

                User Request: "{natural_language_query}"
                
                Search Keyword:
                """
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                continue
        
        # If all models fail, use fallback
        return simple_search_enhancement(natural_language_query)
        
    except Exception as e:
        return simple_search_enhancement(natural_language_query)

def simple_search_enhancement(query: str) -> str:
    """Simple search term enhancement without AI"""
    # Basic keyword mapping for common electronic components
    enhancements = {
        "arduino uno": "Arduino Uno",
        "lm358": "LM358",
        "esp32": "ESP32",
        "resistor": "resistor",
        "capacitor": "capacitor",
        "transistor": "transistor",
        "microcontroller": "microcontroller",
        "amplifier": "amplifier",
        "wifi": "WiFi",
        "bluetooth": "Bluetooth",
        "10k": "10k",
        "ohm": "ohm"
    }
    
    query_lower = query.lower()
    for key, enhancement in enhancements.items():
        if key in query_lower:
            return enhancement
    
    return query

def run_search_engine():
    """Main function to run the context-aware search engine."""
    print("Welcome to the Smart Electronics Search Engine!")
    print("Type 'exit' to quit.")
    print("Type 'demo' to see example searches.")

    while True:
        try:
            user_query = input("\nDescribe the part you are looking for: ")
            
            if user_query.lower() == 'exit':
                break
            elif user_query.lower() == 'demo':
                show_demo()
                continue

            print("\nAsking AI assistant to find the best search term...")
            search_keyword = get_search_terms_from_query(user_query)
            
            if "Error" in search_keyword:
                print(f"Error from AI model: {search_keyword}")
                continue
                
            print(f"[OK] AI suggested search term: '{search_keyword}'")

            print(f"\nSearching Mouser for '{search_keyword}'...")
            results = search_mouser_parts(search_keyword)

            if "error" in results:
                print(f"API Error: {results['error']}")
            elif results.get("Errors") and len(results["Errors"]) > 0:
                 print(f"Mouser API returned an error: {results['Errors'][0]['Message']}")
            elif results.get("SearchResults") is None or results["SearchResults"]["NumberOfResult"] == 0:
                print("No parts found for this search term.")
            else:
                num_results = results['SearchResults']['NumberOfResult']
                parts = results['SearchResults']['Parts']
                print(f"[SUCCESS] Found {num_results} parts!")
                
                # Show top 5 results instead of just 1
                print(f"\n--- Top {min(5, len(parts))} Results ---")
                for i, part in enumerate(parts[:5], 1):
                    print(f"{i}. Mouser Part #: {part.get('MouserPartNumber', 'N/A')}")
                    print(f"   Manufacturer: {part.get('Manufacturer', 'N/A')}")
                    print(f"   Description: {part.get('Description', 'N/A')}")
                    print()
                print("------------------\n")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def show_demo():
    """Show example searches"""
    print("\nExample searches you can try:")
    print("- 'Arduino Uno microcontroller'")
    print("- 'LM358 operational amplifier'")
    print("- 'ESP32 WiFi module'")
    print("- 'small bluetooth chip for wearable'")
    print("- '10k ohm resistor'")

if __name__ == "__main__":
    run_search_engine()
