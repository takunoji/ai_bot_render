from fastapi import FastAPI, Request
import requests

app = FastAPI()

OPENAI_API_KEY = "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"
CHATWORK_API_TOKEN = "d884411846999c80c15e63bef1be44c3"


@app.post("/webhook")
async def chatwork_webhook(request: Request):
    data = await request.json()
    room_id = data["room_id"]
    message_body = data["message_body"]

    # GPTにリクエストを送信
    gpt_response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4-custom-abc123xyz",
            "messages": [{"role": "user", "content": message_body}]
        }
    ).json()

    response_text = gpt_response["choices"][0]["message"]["content"]

    # Chatworkに応答を送信
    requests.post(
        f"https://api.chatwork.com/v2/rooms/{room_id}/messages",
        headers={"X-ChatWorkToken": CHATWORK_API_TOKEN},
        data={"body": response_text}
    )

    return {"status": "success"}
