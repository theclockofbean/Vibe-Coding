class DeepSeekLLMClient:
    def __init__(self, client):
        self.client = client

    def generate(self, *, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content
