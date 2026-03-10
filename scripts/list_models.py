"""List available Gemini models."""
import google.generativeai as genai
genai.configure(api_key="AIzaSyCsC-J8bxjR5XPuRA4DPWp00R4OMI-c_DU")
for m in genai.list_models():
    if "generateContent" in m.supported_generation_methods:
        print(m.name)
