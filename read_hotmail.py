from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_url_path="", static_folder="static")

# ---- LOAD ACCOUNTS.TXT ----
ACCOUNTS = {}
with open("accounts_dmt.txt", "r", encoding="utf8") as f:
    for line in f:
        if "|" in line:
            email, password, refresh_token, client_id = line.strip().split("|")
            ACCOUNTS[email.lower()] = {
                "refresh_token": refresh_token,
                "client_id": client_id
            }

TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
NUM_MAILS = 5
GRAPH_URL_TEMPLATE = "https://graph.microsoft.com/v1.0/me/messages?$top={top}&$orderby=receivedDateTime desc"

# ---- Hàm chuẩn hóa email để lookup ----
def normalize_email(email: str):
    """Bỏ phần + để lookup, dùng cho dict ACCOUNTS"""
    email = email.strip().lower()
    if "+" in email:
        local, domain = email.split("@", 1)
        local = local.split("+", 1)[0]
        email = f"{local}@{domain}"
    return email

# ---- Lấy mail ----
def get_messages(email):
    """Trả danh sách mail hoặc dict error"""
    if email not in ACCOUNTS:
        return {"error": "Email không có trong danh sách!"}

    refresh_token = ACCOUNTS[email]["refresh_token"]
    client_id = ACCOUNTS[email]["client_id"]

    try:
        data = {
            "client_id": client_id,
            "scope": "https://graph.microsoft.com/.default",
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        token_resp = requests.post(TOKEN_URL, data=data, timeout=10)
        if token_resp.status_code != 200:
            return {"error": "Refresh token invalid!", "detail": token_resp.text}

        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        graph_url = GRAPH_URL_TEMPLATE.format(top=NUM_MAILS)
        mails_resp = requests.get(graph_url, headers=headers, timeout=10)
        if mails_resp.status_code != 200:
            return {"error": "Không đọc được mail!", "detail": mails_resp.text}

        mails_json = mails_resp.json()
        return mails_json.get("value", [])

    except requests.exceptions.RequestException as e:
        return {"error": "Lỗi khi gọi API", "detail": str(e)}
    except Exception as e:
        return {"error": "Lỗi nội bộ", "detail": str(e)}

# ---- Endpoint cũ cho web ----
@app.post("/read-email")
def read_email_post():
    data = request.json
    user_input_email = data.get("email", "").strip()
    if not user_input_email:
        return jsonify({"input_email": user_input_email, "mails": [], "error": "Chưa nhập email!"})

    lookup_email = normalize_email(user_input_email)
    mails = get_messages(lookup_email)

    if isinstance(mails, dict) and "error" in mails:
        return jsonify({"input_email": user_input_email, "mails": [], **mails})

    return jsonify({"input_email": user_input_email, "mails": mails, "error": None})

# ---- Endpoint mới GET API ----
@app.get("/api/read-email")
def read_email_get():
    user_input_email = request.args.get("hotmail", "").strip()
    if not user_input_email:
        return jsonify({"input_email": user_input_email, "mails": [], "error": "Chưa nhập email!"})

    # ----- Xử lý dấu + bị decode thành space -----
    user_input_email = user_input_email.replace(" ", "+")  # thay space thành +

    lookup_email = normalize_email(user_input_email)
    mails = get_messages(lookup_email)

    if isinstance(mails, dict) and "error" in mails:
        return jsonify({"input_email": user_input_email, "mails": [], **mails})

    return jsonify({"input_email": user_input_email, "mails": mails, "error": None})

# ---- Trang web frontend ----
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
