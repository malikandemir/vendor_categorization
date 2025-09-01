Instructions: Building a Vendor Categorization AI Tool
1. Project Objective
The goal of this project is to create a web application that allows a user to upload a CSV file containing vendor data. The application will then use a generative AI model (the Gemini API) to categorize each vendor into a predefined set of categories. The results, along with the original data, will be stored in a SQLite database for historical record-keeping and later retrieval.

2. Technology Stack
Backend: Python 3.9+ with the Flask framework.

AI: Google Gemini API for categorization.

Data Processing: Pandas for handling CSV data.

Database: SQLite3 for persistent storage.

Frontend: Simple HTML and JavaScript for the user interface.

3. Step-by-Step Instructions
Step 1: Backend Setup (Python & Flask)
Environment Setup: Create a new project directory and a virtual environment.

mkdir vendor_categorization
cd vendor_categorization
python3 -m venv venv
source venv/bin/activate

Install Dependencies: Install the required Python libraries.

pip install Flask pandas google-generativeai

Create the Flask App: Create a file named app.py. This will be the core of your backend.

# app.py
from flask import Flask, request, render_template
# ... other imports for pandas, sqlite3, and gemini-generativeai

app = Flask(__name__)

# Add routes for the main page, upload, and history
@app.route('/')
def index():
    return "Hello, World!" # Placeholder

# Run the app
if __name__ == '__main__':
    app.run(debug=True)

Step 2: Database Design & Initialization (SQLite)
Schema Definition: The database will have two main tables:

uploads: Stores a record for each file uploaded.

id (INTEGER PRIMARY KEY)

filename (TEXT)

upload_timestamp (TEXT)

vendor_categories: Stores the categorization results for each vendor.

id (INTEGER PRIMARY KEY)

upload_id (INTEGER, FOREIGN KEY to uploads.id)

vendor_name (TEXT)

original_category (TEXT)

ai_category (TEXT)

Initialization: In app.py, write a function to connect to the SQLite database and create the tables if they don't exist. This function should be called when the app starts.

Step 3: Frontend Interface (HTML & JavaScript)
Create an HTML file: In the templates directory, create index.html. This file will contain the user interface.

File Upload Form: The HTML should have a form with a file input field and a submit button. The form must use enctype="multipart/form-data" to handle file uploads.

Display Area: The page needs a section to display the current categorization results and a separate section to show historical data. JavaScript will be used to dynamically update these sections.

Step 4: File Upload & Processing Logic
Create an Upload Route: In app.py, create a new route (e.g., @app.route('/upload', methods=['POST'])) to handle the form submission.

Handle File Data:

Retrieve the uploaded file from request.files.

Ensure the file is a CSV by checking its extension.

Use Pandas to read the CSV file into a DataFrame.

Call the AI Categorization Function: Iterate through the DataFrame, passing relevant vendor information (e.g., name, existing category) to a dedicated function that calls the Gemini API.

Step 5: AI Integration (Gemini API)
API Key: Obtain a Gemini API key and store it securely (e.g., in an environment variable).

Prompt Engineering: The quality of the categorization depends on a clear prompt. The prompt for each vendor should be structured like this:

"You are a professional business analyst specializing in vendor and spend categorization. Your task is to analyze a vendor and assign a single category from the provided list.

Vendor Name: {vendor_name}
Vendor Description: {vendor_description}

Allowed Categories:
- Office Supplies
- Software as a Service (SaaS)
- Professional Services
- Marketing
- Travel & Entertainment
- ... (your specific list of categories)

Output only the single, best-fit category name. Do not include any other text, explanations, or formatting."

API Call: Use the google-generativeai library to make the API call with the constructed prompt. Implement a try-except block to handle potential API errors.

Step 6: Data Storage & History Retrieval
Save Results: After receiving the AI's response for a vendor, update the Pandas DataFrame with the new category. Then, save the original and new data to the vendor_categories table in the SQLite database, linking it to the corresponding upload_id.

History Route: Create a new Flask route (e.g., @app.route('/history')) that retrieves all historical data from the uploads and vendor_categories tables and returns it as JSON.

Frontend History Display: Use JavaScript to fetch data from the /history endpoint and render it on the webpage, allowing users to view past categorization jobs.

4. Important Considerations
Error Handling: Implement robust error handling for file uploads, database operations, and API calls.

Security: Sanitize all user inputs (e.g., filenames) to prevent injection attacks.

API Rate Limits: Be mindful of the Gemini API's rate limits. You may need to add a short delay between API calls if processing a very large file.

User Feedback: The UI should provide clear feedback to the user at each step (e.g., "Uploading...", "Processing...", "Done!").