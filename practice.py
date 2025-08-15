# pip install flask spotipy
import os
from flask import Flask, redirect, request, session, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- 1) api_key.txt 로드 ---
def load_api_keys(path="api_key.txt"):
    d = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                d[k.strip()] = v.strip()
    return d

keys = load_api_keys()

# --- 2) Flask 세팅 ---
app = Flask(__name__)
app.secret_key = os.urandom(24)  # 세션용

SCOPE = "user-top-read user-follow-read"
sp_oauth = SpotifyOAuth(
    client_id=keys["client_id"],
    client_secret=keys["client_secret"],
    redirect_uri=keys["redirect_uri"],  # 반드시 ngrok https/callback 과 동일
    scope=SCOPE,
    cache_path=".cache"  # 토큰 캐시
)

# --- 3) 로그인 시작 (승인 페이지로 리다이렉트) ---
@app.route("/login")
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

# --- 4) 콜백 (토큰 교환) ---
@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error:
        return f"Spotify auth error: {error}", 400
    if not code:
        return "Missing code", 400

    # 토큰 교환
    token_info = sp_oauth.get_access_token(code, check_cache=True)
    session["token_info"] = token_info
    return redirect("/me")

# --- 5) API 호출: Top Artists 10 & Followed Artists ---
@app.route("/me")
def me():
    token_info = session.get("token_info")
    if not token_info or sp_oauth.is_token_expired(token_info):
        return redirect("/login")

    # 토큰 자동 갱신
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info

    sp = spotipy.Spotify(auth=token_info["access_token"])

    # 많이 재생한 가수 10명
    top_artists = sp.current_user_top_artists(limit=30, offset=0, time_range="long_term")
    top_list = [
        {
            "rank": i + 1,
            "name": a["name"],
            "genres": a.get("genres", []),
            "id": a["id"],
            "url": a["external_urls"]["spotify"]
        }
        for i, a in enumerate(top_artists["items"])
    ]

    # 팔로우한 아티스트 (페이지네이션)
    followed = []
    results = sp.current_user_followed_artists(limit=50)
    while True:
        for a in results["artists"]["items"]:
            followed.append({
                "name": a["name"],
                "id": a["id"],
                "url": a["external_urls"]["spotify"]
            })
        if results["artists"]["next"]:
            results = sp.next(results["artists"])
        else:
            break

    return jsonify({
        "top_artists_30": top_list,
        "followed_artists_count": len(followed),
        #"followed_artists": followed
    })

# 로컬 실행시에 main 함수
if __name__ == "__main__":
    # 로컬 콜백 서버 반드시 먼저 띄워야 함
    # ngrok은 아래 서버에 트래픽을 포워딩
    app.run(host="127.0.0.1", port=8888, debug=True)
