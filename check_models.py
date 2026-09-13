import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQAI_API_KEY")

if not GROQ_KEY:
    print("❌ Error: GROQ_API_KEY is missing from environment or .env file.")
    exit(1)

client = OpenAI(
    api_key=GROQ_KEY,
    base_url="https://api.groq.com/openai/v1"
)

try:
    print("Fetching active models from Groq...\n")
    models = client.models.list()
    active_models = sorted([m.id for m in models.data])
    
    print(f"✅ Found {len(active_models)} available models:")
    for model_id in active_models:
        print(f"  • {model_id}")

except Exception as e:
    print(f"❌ Failed to fetch models: {e}")