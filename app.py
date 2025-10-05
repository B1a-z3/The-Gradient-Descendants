from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
from mouser_search_engine import MouserSearchApp
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
CORS(app)

# Initialize the Mouser Search App
mouser_app = MouserSearchApp(
    mouser_api_key="d99c4255-03a1-495a-8a37-c317fa862ab2",
    gemini_api_key="AIzaSyDcGNx1RsNgWOC9K-7bH40fdnRqm4vqtTs"
)

@app.route('/')
def index():
    """Main search page"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Handle search requests"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        context = data.get('context', '')
        user_id = session.get('user_id', 'anonymous')
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Perform search
        results = mouser_app.search_parts(query, user_id, context)
        
        # Convert results to JSON-serializable format
        serialized_results = {
            'original_query': results['original_query'],
            'enhanced_query': results['enhanced_query'],
            'total_found': results['total_found'],
            'search_context': results['search_context'],
            'results': [],
            'recommendations': results['recommendations'],
            'personalized_recommendations': results['personalized_recommendations']
        }
        
        # Serialize parts
        for part in results['results']:
            serialized_results['results'].append({
                'part_number': part.part_number,
                'manufacturer': part.manufacturer,
                'description': part.description,
                'category': part.category,
                'price': part.price,
                'stock': part.stock,
                'datasheet_url': part.datasheet_url,
                'image_url': part.image_url,
                'specifications': part.specifications
            })
        
        return jsonify(serialized_results)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/part/<part_number>')
def get_part_details(part_number):
    """Get detailed information about a specific part"""
    try:
        part = mouser_app.get_part_details(part_number)
        if not part:
            return jsonify({'error': 'Part not found'}), 404
        
        return jsonify({
            'part_number': part.part_number,
            'manufacturer': part.manufacturer,
            'description': part.description,
            'category': part.category,
            'price': part.price,
            'stock': part.stock,
            'datasheet_url': part.datasheet_url,
            'image_url': part.image_url,
            'specifications': part.specifications
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/similar/<part_number>')
def get_similar_parts(part_number):
    """Get similar parts to a given part number"""
    try:
        similar_parts = mouser_app.find_similar_parts(part_number)
        
        serialized_parts = []
        for part in similar_parts:
            serialized_parts.append({
                'part_number': part.part_number,
                'manufacturer': part.manufacturer,
                'description': part.description,
                'category': part.category,
                'price': part.price,
                'stock': part.stock,
                'datasheet_url': part.datasheet_url,
                'image_url': part.image_url,
                'specifications': part.specifications
            })
        
        return jsonify(serialized_parts)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recommendations')
def get_recommendations():
    """Get personalized recommendations for the current user"""
    try:
        user_id = session.get('user_id', 'anonymous')
        recommendations = mouser_app.recommendation_engine.get_personalized_recommendations(user_id)
        
        return jsonify({'recommendations': recommendations})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/set-user', methods=['POST'])
def set_user():
    """Set user ID for personalization"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'anonymous')
        session['user_id'] = user_id
        return jsonify({'success': True, 'user_id': user_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
