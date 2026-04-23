import os
import io
import json
import base64
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pdf2image import convert_from_path

# Load environment variables
load_dotenv()

def analyze_pdf(file_path):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env")
        return

    client = genai.Client(api_key=api_key)
    
    try:
        # Note: This requires Poppler installed and in PATH on Windows
        print(f"Converting PDF {file_path} to images...")
        images = convert_from_path(file_path, dpi=200)
    except Exception as e:
        print(f"Error rendering PDF: {e}")
        print("\nNote for User: If you're on Windows, you must install Poppler and add its 'bin' folder to your System PATH for the vision engine to work.")
        return

    prompt = """
You are an expert architectural and interior design analyzer.
I am providing an image of a construction/interior drawing (e.g., kitchen, wardrobe).
Extract every identifiable component or room from the drawing.
For each item, provide:
1. name: The name of the component (e.g., "Wall Cabinet", "Base Unit", "Wardrobe Section A").
2. dimension: The dimensions as written (e.g., "600 x 720 mm").
3. area: Calculate or extract the area if possible (e.g., "0.43 sqm").
4. circumference: Calculate or extract the circumference/perimeter if possible (e.g., "2.64 m").

Return the result as a STRICT JSON object with a key "items" which is a list of these objects.
"""

    all_results = []
    
    for i, img in enumerate(images):
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_data = buffered.getvalue()
        
        image = types.Part.from_bytes(
            data=img_data,
            mime_type="image/png"
        )
        
        try:
            print(f"Analyzing Page {i+1}...")
            response = client.models.generate_content(
                model='gemini-1.5-pro',
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                )
            )
            result = json.loads(response.text)
            all_results.append({"page": i+1, "items": result.get("items", [])})
        except Exception as e:
            print(f"Error analyzing page {i+1}: {e}")

    print("\nFINAL EXTRACTION RESULTS:")
    print(json.dumps(all_results, indent=2))

if __name__ == "__main__":
    analyze_pdf("Space_Craft_ Ramachandra_quote 1.pdf")
