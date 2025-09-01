# Vendor Categorization AI Tool

This application allows users to upload CSV files containing vendor data and uses the Google Gemini API to categorize each vendor into predefined categories.

## Features

- Upload CSV files with vendor data
- AI-powered vendor categorization using Google Gemini API
- Store categorization results in a SQLite database
- View historical categorization results
- Modern web interface

## Requirements

- Docker and Docker Compose

## Getting Started

1. Clone this repository
2. Obtain a Google Gemini API key from https://ai.google.dev/
3. Set your API key as an environment variable:

```bash
export GEMINI_API_KEY=your_api_key_here
```

4. Build and run the Docker container:

```bash
docker-compose up --build
```

5. Access the application at http://localhost:5000

## CSV File Format

Your CSV file should contain at least a `vendor_name` column. For better results, include a `description` column with details about each vendor.

Example CSV format:

```
vendor_name,category,description
Acme Inc,Office Supplies,Office supplies provider
TechCorp,Software,Enterprise software solutions
```

## Categories

The application uses the following predefined categories:

- Office Supplies
- Software as a Service (SaaS)
- Professional Services
- Marketing
- Travel & Entertainment
- Hardware & Equipment
- Utilities
- Rent & Facilities
- Insurance
- Financial Services
