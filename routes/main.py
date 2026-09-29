import os
import re
import requests
import isodate
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)
API_KEY = os.getenv("YOUTUBE_API_KEY")

def convert_youtube_url(url: str) -> str:
    base_mobile = "https://m.youtube.com/watch?v="
    base_pc = "https://www.youtube.com/watch?v="
    base_short = "https://youtu.be/"
    base_sh = "https://m.youtube.com/shorts/"

    if url.startswith(base_short):
        return url
    if url.startswith(base_mobile):
        video_id = url[len(base_mobile):]
        return f"https://youtu.be/{video_id}"
    if url.startswith(base_pc):
        video_id = url[len(base_pc):]
        return f"https://youtu.be/{video_id}"
    if url.startswith(base_sh):
        video_id = url[len(base_sh):]
        return f"https://youtu.be/{video_id}"

    raise ValueError("対応していないURL形式です")

def extract_playlist_id(url: str) -> str:
    match = re.search(r"list=([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    raise ValueError("プレイリストIDが見つかりません")

def get_playlist_video_ids(playlist_id):
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "contentDetails",
        "playlistId": playlist_id,
        "maxResults": 50,
        "key": API_KEY
    }
    res = requests.get(url, params=params).json()
    video_ids = []
    for item in res.get("items", []):
        video_ids.append(item["contentDetails"]["videoId"])
    return video_ids

def get_video_duration(video_id):
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "contentDetails",
        "id": video_id,
        "key": API_KEY
    }
    res = requests.get(url, params=params).json()
    duration = res["items"][0]["contentDetails"]["duration"]
    seconds = isodate.parse_duration(duration).total_seconds()
    return seconds

@main_bp.route("/")
def index():
    return render_template("index.html")

@main_bp.route("/convert", methods=["POST"])
def convert():
    data = request.json
    url = data.get("url")
    try:
        result = convert_youtube_url(url)
        return jsonify({"success": True, "converted": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

@main_bp.route("/playlist_auto", methods=["POST"])
def playlist_auto():
    data = request.json
    url = data.get("url")
    try:
        playlist_id = extract_playlist_id(url)
        video_ids = get_playlist_video_ids(playlist_id)
        result = []
        for vid in video_ids:
            duration = get_video_duration(vid)
            result.append({"videoId": vid, "duration": duration})
        return jsonify({"success": True, "videos": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@main_bp.route("/games")
@login_required
def games():
    return render_template("games.html")
