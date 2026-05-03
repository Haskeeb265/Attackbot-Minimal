import os
from mistralai import Mistral

# Initialize the client with your free API key
api_key = "YOUR_FREE_API_KEY"
model = "codestral-latest" # or "devstral-medium-latest" for Devstral 2 2512
client = Mistral(api_key=api_key)

# Send a chat completion request
chat_response = client.chat.complete(
    model=model,
    messages=[
        {"role": "user", "content": "Write a Python function to calculate fibonacci numbers."},
    ]
)

print(chat_response.choices[0].message.content)
