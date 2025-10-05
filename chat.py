# ==============================================================================
# 1. INSTALL LIBRARIES
# ==============================================================================
# !pip install -q google-generativeai python-dotenv requests  # Use: pip install -r requirements.txt

# ==============================================================================
# 2. IMPORT LIBRARIES AND LOAD SECRETS
# ==============================================================================
import os
import json
import requests
import google.generativeai as genai

# Load API keys from environment variables or direct assignment
MOUSER_API_KEY = "d99c4255-03a1-495a-8a37-c317fa862ab2"
GEMINI_API_KEY = "AIzaSyDcGNx1RsNgWOC9K-7bH40fdnRqm4vqtTs"

# Mouser API endpoint
MOUSER_API_URL = "https://api.mouser.com/api/v1.0/search/partnumber"

# ==============================================================================
# 3. MOUSER API CLIENT FUNCTION
# ==============================================================================
def search_mouser_parts(search_keyword: str, limit: int = 20):
    """
    Searches for parts on Mouser using a specific keyword.
    """
    if not MOUSER_API_KEY:
        return {"error": "Mouser API key is not set. Check Colab secrets."}

    headers = {'Content-Type': 'application/json'}
    
    # Use keyword search for broader results
    body = {
        "SearchByKeywordRequest": {
            "keyword": search_keyword,
            "records": limit,
            "startingRecord": 0
        }
    }

    try:
        # Use keyword search endpoint
        keyword_url = "https://api.mouser.com/api/v1/search/keyword"
        response = requests.post(
            f"{keyword_url}?apiKey={MOUSER_API_KEY}",
            headers=headers,
            data=json.dumps(body)
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        return {"error": f"HTTP error occurred: {http_err}"}
    except Exception as err:
        return {"error": f"An other error occurred: {err}"}

# ==============================================================================
# 4. GEMINI AI CLIENT FUNCTION
# ==============================================================================
def get_search_terms_from_query(natural_language_query: str) -> str:
    """
    Uses Gemini to convert a natural language query into specific search terms.
    """
    if not GEMINI_API_KEY:
        return "Error: Gemini API key not configured. Check Colab secrets."

    genai.configure(api_key=GEMINI_API_KEY)
    
    generation_config = {"temperature": 0.2, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    
    # --- THIS IS THE CORRECTED LINE ---
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config)

    prompt = f"""
    You are an expert electronics engineer assistant. Your task is to translate a user's natural language request for an electronic component into a precise search keyword for the Mouser Electronics API. Return ONLY the most likely search keyword (like a part number, component type, or key spec) and nothing else.

    User Request: "{natural_language_query}"
    
    Search Keyword:
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error communicating with Gemini API: {e}"

# ==============================================================================
# 5. MAIN APPLICATION LOGIC
# ==============================================================================
def run_search_engine():
    """
    Main function to run the context-aware search engine.
    """
    print("Welcome to the Smart Electronics Search Engine!")
    print("Type 'exit' to quit.")

    while True:
        user_query = input("\nDescribe the part you are looking for (e.g., 'a small bluetooth chip for a wearable'): ")
        if user_query.lower() == 'exit':
            break

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

# ==============================================================================
# 6. RUN THE APPLICATION
# ==============================================================================
run_search_engine()