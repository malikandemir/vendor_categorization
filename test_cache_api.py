import requests
import json

def test_cache_api():
    """Test the cache API endpoint"""
    try:
        # Make a request to the cache API
        response = requests.get('http://localhost:5001/cache')
        
        # Print the response status code
        print(f"Response status code: {response.status_code}")
        
        # Print the response headers
        print(f"Response headers: {response.headers}")
        
        # Print the response content
        print(f"Response content: {response.content.decode('utf-8')}")
        
        # Parse the JSON response
        data = response.json()
        
        # Print the parsed data
        print(f"Parsed data: {json.dumps(data, indent=2)}")
        
        # Print the data type and length
        print(f"Data type: {type(data)}")
        print(f"Is list: {isinstance(data, list)}")
        print(f"Data length: {len(data)}")
        
        # If there are items, print the first one
        if data and len(data) > 0:
            print(f"First item: {data[0]}")
            print(f"First item type: {type(data[0])}")
            print(f"First item keys: {data[0].keys()}")
        
        return True
    except Exception as e:
        print(f"Error testing cache API: {str(e)}")
        return False

if __name__ == "__main__":
    test_cache_api()
