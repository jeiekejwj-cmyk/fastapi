import flask
from flask import Flask, request, jsonify
import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.errors import FloodWait, UserChannelsTooMuch, UserDeactivated, PeerIdInvalid, InviteHashInvalid

app = Flask(__name__)

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_string = os.getenv("SESSION_STRING")
default_chat_id = os.getenv("CHAT_ID")

CONCURRENCY = 20

async def approve_user(app, chat_id, user):
    try:
        await app.approve_chat_join_request(chat_id, user.id)
        print(f"✅ Approved: {user.first_name} (@{user.username})")
        return "approved"
    except (UserChannelsTooMuch, UserDeactivated, PeerIdInvalid):
        print(f"⚠️ Skipped: {user.first_name} (@{user.username})")
        return "skipped"
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await approve_user(app, chat_id, user)
    except Exception as e:
        print(f"❌ Error with {user.id}: {e}")
        return "skipped"

async def main():
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            chat = await app.get_chat(chat_ref)
            chat_id = chat.id
            join_requests = [req async for req in app.get_chat_join_requests(chat_id)]
            approved = 0
            skipped = 0
            for i in range(0, len(join_requests), CONCURRENCY):
                batch = join_requests[i:i+CONCURRENCY]
                tasks = [approve_user(app, chat.id, req.user) for req in batch]
                results = await asyncio.gather(*tasks)
                approved += results.count("approved")
                skipped += results.count("skipped")
            return f"Approved {approved}, Skipped {skipped}"
        except Exception as e:
            return str(e)

async def process_username(username):
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            join_requests = [req async for req in app.get_chat_join_requests(username)]
            approved = 0
            skipped = 0
            for i in range(0, len(join_requests), CONCURRENCY):
                batch = join_requests[i:i+CONCURRENCY]
                tasks = [approve_user(app, username, req.user) for req in batch]
                results = await asyncio.gather(*tasks)
                approved += results.count("approved")
                skipped += results.count("skipped")
            return {"status": "success", "approved": approved, "skipped": skipped}
        except InviteHashInvalid:
            return {"status": "error", "message": "Invalid invite or username"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.route('/', methods=['GET'])
def index():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(main())
    return jsonify({"status": "done", "result": result})

async def join_only(invite_link):
    async with Client("fast_approver", api_id=api_id, api_hash=api_hash, session_string=session_string) as app:
        try:
            chat = await app.join_chat(invite_link)
            return {"status": "joined", "title": chat.title, "id": chat.id}
        except InviteHashInvalid:
            return {"status": "error", "message": "Invalid invite link"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.route('/receive', methods=['POST'])
def receive():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"status": "error", "message": "Missing 'username'"}), 400
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(join_only(username))
    return jsonify(result)

@app.route('/accept', methods=['POST'])
def accept():
    data = request.get_json()
    raw = data.get("username")
    if not raw:
        return jsonify({"status": "error", "message": "Missing 'username'"}), 400

    if isinstance(raw, str) and raw.lstrip('-').isdigit():
        try:
            chat_ref = int(raw)
        except ValueError:
            return jsonify({"status": "error", "message": "Invalid chat ID format"}), 400
    else:
        chat_ref = raw

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(process_username(chat_ref))
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
