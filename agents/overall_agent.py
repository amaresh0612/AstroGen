from openai import OpenAI

client = OpenAI()

def overall_agent(chat_history):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=chat_history,
        max_tokens=500,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()
