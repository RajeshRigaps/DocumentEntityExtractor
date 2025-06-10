##apiKey = "AIzaSyCX-9XgCBS9GS9WGOp0_3tVjryAn3Koj3Y"
import os
import io
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from docx import Document
import openpyxl
import pandas as pd
from PyPDF2 import PdfReader # Updated for newer PyPDF2 versions

app = Flask(__name__)

# Configure your Gemini API key
# It's recommended to set this as an environment variable for security
# For development, you can directly paste it here, but remove it for production
# genai.configure(api_key="YOUR_GEMINI_API_KEY")
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
#genai.configure(api_key=apiKey)
# Initialize the Gemini model
generation_config = {
    "temperature": 0.2, # Lower temperature for more focused and less random output
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    safety_settings=safety_settings
)

def extract_text_from_pdf(file_stream):
    """Extracts text from a PDF file."""
    text = ""
    try:
        reader = PdfReader(file_stream)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
    return text

def extract_text_from_docx(file_stream):
    """Extracts text from a DOCX file."""
    text = ""
    try:
        document = Document(file_stream)
        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        print(f"Error extracting text from DOCX: {e}")
    return text

def extract_text_from_xlsx(file_stream):
    """Extracts text from an XLSX file."""
    text = ""
    try:
        workbook = openpyxl.load_workbook(file_stream)
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value:
                        text += str(cell.value) + " "
                text += "\n"
    except Exception as e:
        print(f"Error extracting text from XLSX: {e}")
    return text

def extract_text_from_csv(file_stream):
    """Extracts text from a CSV file."""
    try:
        df = pd.read_csv(file_stream)
        return df.to_string(index=False)
    except Exception as e:
        print(f"Error extracting text from CSV: {e}")
        return ""

@app.route('/')
def index():
    """Renders the upload form."""
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_entities():
    """Handles file upload and entity extraction."""
    if 'document' not in request.files:
        return jsonify({"error": "No document part in the request"}), 400

    file = request.files['document']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        file_extension = file.filename.split('.')[-1].lower()
        file_stream = io.BytesIO(file.read())
        extracted_text = ""

        if file_extension == 'pdf':
            extracted_text = extract_text_from_pdf(file_stream)
        elif file_extension == 'docx':
            extracted_text = extract_text_from_docx(file_stream)
        elif file_extension == 'xlsx':
            extracted_text = extract_text_from_xlsx(file_stream)
        elif file_extension == 'csv':
            extracted_text = extract_text_from_csv(file_stream)
        else:
            return jsonify({"error": "Unsupported file type"}), 400

        if not extracted_text.strip():
            return jsonify({"error": "Could not extract text from the document. The document might be empty or in an unsupported format."}), 400

        print(f"extracted text : {extracted_text}")
        # Construct the prompt for the Gemini model
        prompt = f"""
        Analyze the following document text and extract all relevant entities.
        Represent each entity as a key-value pair.
        Focus on identifying names, organizations, dates, locations, products, prices, contact information (emails, phone numbers), invoice numbers, and any other significant factual information.
        If a value is a list (e.g., multiple products mentioned), represent it as a JSON array.
        If an entity is clearly associated with a type (e.g., "Company Name", "Invoice Number"), use that as the key.
        
        Document Text:
        ---
        {extracted_text}
        ---

        Provide the output as a JSON object, where keys are entity types or names, and values are the extracted entities.
        Example format:
        {{
        "Name": "John Doe",
        "Organization": "Acme Corp",
        "Date": "2023-10-26",
        "Invoice Number": "INV-2023-001",
        "Items": ["Product A", "Service B"],
        "Total Amount": "$150.00"
        }}
        """

        try:
            # Send the prompt to the Gemini model
            response = model.generate_content(prompt)
            # The model might return extra text before/after the JSON.
            # We need to find the actual JSON string.
            response_text = response.text.strip()
            print(f"model_response: {response_text}")
            # Attempt to parse the JSON, sometimes the model might add markdown ```json around it
            if response_text.startswith("```json") and response_text.endswith("```"):
                json_string = response_text[7:-3].strip()
            else:
                json_string = response_text

            import json
            entities = json.loads(json_string)
            return jsonify(entities)
        except Exception as e:
            print(f"Error calling Gemini API or parsing JSON: {e}")
            return jsonify({"error": "Failed to extract entities. Please check the document content or try again later.", "details": str(e)}), 500

    return jsonify({"error": "An unknown error occurred"}), 500

if __name__ == '__main__':
    # Ensure your API key is set as an environment variable
    # For example: export GEMINI_API_KEY="YOUR_API_KEY_HERE"
    # or set it directly in your system's environment variables.
    if not os.environ.get("GEMINI_API_KEY"):
        print("WARNING: GEMINI_API_KEY environment variable not set.")
        print("Please set it before running the application.")
        print("Example: export GEMINI_API_KEY='your_api_key_here'")
        # For demonstration, you might temporarily hardcode it here, but DO NOT do this in production.
        # genai.configure(api_key="YOUR_ACTUAL_GEMINI_API_KEY") # Only for quick testing
    app.run(debug=True)

