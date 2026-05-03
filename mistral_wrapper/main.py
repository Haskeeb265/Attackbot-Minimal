import requests

class MistralClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.mistral.ai/v1/chat/completions"

    def chat(self, message, model="devstral2"):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": message}
            ]
        }

        response = requests.post(self.base_url, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(f"Error {response.status_code}: {response.text}")

        data = response.json()
        return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    API_KEY = "P2wB0QD1dzlCg01MjXxLhUtMhVyLQlot"

    client = MistralClient(API_KEY)

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        reply = client.chat(user_input)
        print("Mistral:", reply)