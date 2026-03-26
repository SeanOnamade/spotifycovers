import os
import time
import tempfile
import threading
import uuid
from flask import Flask, request, redirect, url_for, session, send_file, render_template_string, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from dotenv import load_dotenv
from albumgrids import generate_album_grid
from flask import send_from_directory

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")

IS_PRODUCTION = "RAILWAY_STATIC_URL" in os.environ

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "YOUR_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "YOUR_CLIENT_SECRET")

if IS_PRODUCTION:
    SPOTIFY_REDIRECT_URI = "https://spotifycovers-production.up.railway.app/callback"
else:
    SPOTIFY_REDIRECT_URI = "http://127.0.0.1:5000/callback"

SCOPE = "playlist-read-private user-top-read"

tasks = {}
TASK_TTL_SECONDS = 600

COMMON_HEAD = """
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="description" content="Generate beautiful Spotify album cover grids from your playlists or top tracks. Login with Spotify and create your unique collage now!">
    <meta name="google-site-verification" content="Bb23Njg1oKFgYtGMT3MR_MWG7-MgTFpKymCYPafltpo" />
    <link rel="icon" href="/favicon.ico" type="image/png">
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-HYRLRLLH5X"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-HYRLRLLH5X');
    </script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
      :root {
        --sp-black: #121212;
        --sp-dark: #181818;
        --sp-card: #282828;
        --sp-hover: #333333;
        --sp-green: #1DB954;
        --sp-green-light: #1ed760;
        --sp-white: #FFFFFF;
        --sp-muted: #B3B3B3;
        --sp-dim: #535353;
      }
      body {
        font-family: 'Inter', sans-serif;
        min-height: 100vh; display: flex; flex-direction: column;
        background: var(--sp-black); color: var(--sp-white);
        background-image: radial-gradient(ellipse at 50% 0%, rgba(29,185,84,0.06) 0%, transparent 60%);
      }
      main { flex: 1; }
      a { color: var(--sp-green); }
      a:hover { color: var(--sp-green-light); }

      .navbar {
        background: rgba(18,18,18,0.8) !important;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(255,255,255,0.06);
        font-weight: 600; letter-spacing: 0.02em;
      }
      .navbar-brand { font-size: 1.3rem; color: var(--sp-white) !important; }
      .navbar-brand:hover { color: var(--sp-green) !important; }
      .nav-link { color: var(--sp-muted) !important; }
      .nav-link:hover { color: var(--sp-white) !important; }

      footer { font-size: 0.85rem; color: var(--sp-dim); }

      .btn { font-weight: 500; letter-spacing: 0.01em; border-radius: 50px; }
      .btn-sp {
        background: var(--sp-green); border: none; color: var(--sp-black);
        font-weight: 700; padding: 0.7rem 2rem;
        transition: transform 0.15s, background 0.15s;
      }
      .btn-sp:hover {
        background: var(--sp-green-light); color: var(--sp-black);
        transform: scale(1.04);
      }
      .btn-sp:disabled {
        background: var(--sp-dim); color: var(--sp-muted);
        transform: none; cursor: not-allowed; opacity: 0.8;
      }
      .btn-sp-outline {
        background: transparent; border: 1px solid var(--sp-muted); color: var(--sp-white);
        font-weight: 600; padding: 0.7rem 2rem;
      }
      .btn-sp-outline:hover {
        border-color: var(--sp-white); color: var(--sp-white);
        transform: scale(1.04);
      }

      .card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
      }
      .form-select, .form-control {
        background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.1); color: var(--sp-white);
        border-radius: 8px;
      }
      .form-select:focus, .form-control:focus {
        background: rgba(255,255,255,0.1); color: var(--sp-white);
        border-color: var(--sp-green); box-shadow: 0 0 0 2px rgba(29,185,84,0.25);
      }
      .form-control::placeholder { color: var(--sp-muted); opacity: 1; }
      .form-select option { background: var(--sp-card); color: var(--sp-white); }
      .form-select {
        cursor: pointer;
        background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3e%3cpath fill='none' stroke='%23B3B3B3' stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='m2 5 6 6 6-6'/%3e%3c/svg%3e");
        background-repeat: no-repeat; background-position: right 0.75rem center; background-size: 16px 12px;
        padding-right: 2.5rem; appearance: none;
      }
      .form-label { color: var(--sp-muted); font-weight: 500; font-size: 0.9rem; margin-bottom: 0.3rem; }
      .text-muted { color: var(--sp-muted) !important; }

      .navbar-brand, .nav-link, a { cursor: pointer; }
      .btn { cursor: pointer; }
      .form-check-input:checked {
        background-color: var(--sp-green); border-color: var(--sp-green);
      }
      .form-check-input:focus {
        box-shadow: 0 0 0 2px rgba(29,185,84,0.25); border-color: var(--sp-green);
      }

      .progress {
        background: rgba(255,255,255,0.08); border-radius: 12px;
      }
      .progress-bar {
        background: var(--sp-green);
      }

      h1, h2 { color: var(--sp-white); }
    </style>
"""

NAVBAR_LOGGED_OUT = """
    <nav class="navbar navbar-expand-lg navbar-dark">
      <div class="container">
        <a class="navbar-brand" href="/">Spotify Covers</a>
      </div>
    </nav>
"""

NAVBAR_LOGGED_IN = """
    <nav class="navbar navbar-expand-lg navbar-dark">
      <div class="container">
        <a class="navbar-brand" href="/">Spotify Covers</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
          <ul class="navbar-nav ms-auto">
            <li class="nav-item"><a class="nav-link" href="/logout">Logout</a></li>
          </ul>
        </div>
      </div>
    </nav>
"""

FOOTER = """
    <footer class="text-center py-3 mt-auto">
      <p class="mb-0">&copy; 2026 Spotify Covers</p>
    </footer>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
"""


def cleanup_old_temp_file():
    old_path = session.get("generated_image_path")
    if old_path:
        try:
            os.unlink(old_path)
        except OSError:
            pass
        session.pop("generated_image_path", None)
        session.pop("generated_image_name", None)


def prune_stale_tasks():
    now = time.time()
    stale = [tid for tid, t in tasks.items() if now - t.get("created_at", 0) > TASK_TTL_SECONDS]
    for tid in stale:
        task = tasks.pop(tid, None)
        if task and "image_path" in task:
            try:
                os.unlink(task["image_path"])
            except OSError:
                pass


@app.route("/")
def index():
    if "token_info" not in session:
        return render_template_string("""
        <!DOCTYPE html>
        <html lang="en">
          <head>
            <title>Spotify Covers - Album Grid Generator</title>
            """ + COMMON_HEAD + """
            <style>
              .hero-section {
                display: flex; align-items: center; justify-content: center;
                min-height: calc(100vh - 120px); padding: 2rem 0;
              }
              .hero-content { text-align: center; max-width: 480px; z-index: 2; }
              .hero-content h1 {
                font-size: 3rem; font-weight: 800; letter-spacing: -0.02em;
                margin-bottom: 1rem;
              }
              .hero-content .lead {
                font-size: 1.1rem; color: var(--sp-muted); margin-bottom: 2rem;
                line-height: 1.6;
              }
              .hero-content .btn-sp { font-size: 1.1rem; padding: 0.85rem 3rem; }

              .example-grid {
                width: 300px; border-radius: 14px; overflow: hidden;
                background: rgba(255,255,255,0.04);
                backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255,255,255,0.06);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                padding: 8px;
                transition: transform 0.3s ease;
              }
              .example-grid:hover { transform: scale(1.04); }
              .example-grid img {
                width: 100%; border-radius: 8px; display: block;
              }
              .hero-stack {
                display: flex; flex-direction: column; gap: 1rem;
              }

              .hero-side { display: none; }
              @media (min-width: 992px) {
                .hero-section { gap: 3rem; }
                .hero-side { display: flex; }
                .hero-content { text-align: left; }
              }
            </style>
          </head>
          <body>
            """ + NAVBAR_LOGGED_OUT + """
            <main>
              <div class="container">
                <div class="hero-section">
                  <div class="hero-side hero-stack">
                    <div class="example-grid">
                      <img src="/static/Party_Songs_13x13_spiral.png" alt="Spiral pattern grid" loading="lazy" />
                    </div>
                    <div class="example-grid">
                      <img src="/static/Bestest_Songs_40_6x6_diagonal.png" alt="Diagonal pattern grid" loading="lazy" />
                    </div>
                  </div>
                  <div class="hero-content">
                    <h1>Album Grid Generator</h1>
                    <p class="lead">Turn your Spotify playlists and top tracks into stunning album cover collages.</p>
                    <a href="/login" class="btn btn-sp">Login with Spotify</a>
                  </div>
                  <div class="hero-side hero-stack">
                    <div class="example-grid">
                      <img src="/static/Studying_(instrumentals)_10x10_diagonal.png" alt="Diagonal pattern grid" loading="lazy" />
                    </div>
                    <div class="example-grid">
                      <img src="/static/Good_Songs_2024!_24x24_normal.png" alt="Normal pattern grid" loading="lazy" />
                    </div>
                  </div>
                </div>
              </div>
            </main>
            """ + FOOTER + """
          </body>
        </html>
        """)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <title>Spotify Covers - Generate Grid</title>
        """ + COMMON_HEAD + """
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "WebApplication",
          "name": "Spotify Covers",
          "url": "https://spotifycovers-production.up.railway.app/",
          "description": "Generate stunning Spotify album cover grids from your playlists or top tracks.",
          "applicationCategory": "Music"
        }
        </script>
        <style>
          #progress-section { display: none; }
          #progress-bar-inner {
            transition: width 0.3s ease;
            background: linear-gradient(90deg, var(--sp-green), var(--sp-green-light), var(--sp-green));
            background-size: 200% 100%;
            animation: shimmer 1.5s ease-in-out infinite;
          }
          @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
          #progress-message { font-size: 0.9rem; color: var(--sp-white); }
        </style>
      </head>
      <body>
        """ + NAVBAR_LOGGED_IN + """
        <main>
          <div class="container py-4">
            <div class="row justify-content-center">
              <div class="col-md-5 col-lg-4">
                <h2 class="text-center mb-4" style="font-weight:700;">Generate Grid</h2>
                <div class="card shadow-sm">
                  <div class="card-body p-4">
                    <form id="grid-form">
                      <div class="mb-3">
                        <label class="form-label">Mode</label>
                        <select name="mode" id="mode-select" class="form-select">
                          <option value="playlist">Playlist</option>
                          <option value="top">Top Tracks</option>
                        </select>
                      </div>

                      <div class="mb-3" id="playlist-field">
                        <label class="form-label">Playlist URL or ID</label>
                        <input type="text" name="playlist_id" class="form-control"
                               placeholder="https://open.spotify.com/playlist/..." />
                      </div>

                      <div class="mb-3" id="time-range-field" style="display:none;">
                        <label class="form-label">Time Range</label>
                        <select name="time_range" class="form-select">
                          <option value="short_term">Last 4 Weeks</option>
                          <option value="medium_term" selected>Last 6 Months</option>
                          <option value="long_term">All Time</option>
                        </select>
                      </div>

                      <div class="mb-3">
                        <label class="form-label">Remove Duplicates</label>
                        <select name="remove_dups" class="form-select">
                          <option value="yes" selected>Yes</option>
                          <option value="no">No</option>
                        </select>
                      </div>

                      <div class="mb-3">
                        <label class="form-label">Pattern</label>
                        <select name="pattern" class="form-select">
                          <option value="normal">Normal</option>
                          <option value="diagonal">Diagonal</option>
                          <option value="spiral">Spiral</option>
                          <option value="checkered">Checkered</option>
                        </select>
                      </div>

                      <div class="mb-3">
                        <label class="form-label">Resolution</label>
                        <select name="cell_size" class="form-select">
                          <option value="100" selected>Standard (100px)</option>
                          <option value="200">High (200px)</option>
                          <option value="300">Ultra (300px)</option>
                        </select>
                      </div>

                      <div class="mb-2 form-check">
                        <input type="checkbox" name="rounded" value="yes" class="form-check-input" id="rounded-check"
                               style="cursor:pointer; background-color:rgba(255,255,255,0.07); border-color:rgba(255,255,255,0.2);">
                        <label class="form-check-label" for="rounded-check" style="cursor:pointer; color:var(--sp-muted); font-weight:500; font-size:0.9rem;">
                          Rounded corners
                        </label>
                      </div>

                      <div class="mb-3 form-check">
                        <input type="checkbox" name="framed" value="yes" class="form-check-input" id="framed-check"
                               style="cursor:pointer; background-color:rgba(255,255,255,0.07); border-color:rgba(255,255,255,0.2);">
                        <label class="form-check-label" for="framed-check" style="cursor:pointer; color:var(--sp-muted); font-weight:500; font-size:0.9rem;">
                          Dark frame border
                        </label>
                      </div>

                      <button type="submit" id="submit-btn" class="btn btn-sp w-100 py-2" style="border-radius:8px;">
                        Generate Grid
                      </button>
                    </form>

                    <div id="progress-section" class="mt-4">
                      <div class="progress" style="height: 24px;">
                        <div id="progress-bar-inner" class="progress-bar progress-bar-striped progress-bar-animated"
                             role="progressbar" style="width: 0%;">
                        </div>
                      </div>
                      <p id="progress-message" class="text-muted text-center mt-2">Starting...</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
        """ + FOOTER + """
        <script>
          const modeSelect = document.getElementById('mode-select');
          const playlistField = document.getElementById('playlist-field');
          const timeRangeField = document.getElementById('time-range-field');

          function updateModeFields() {
            const isTop = modeSelect.value === 'top';
            playlistField.style.display = isTop ? 'none' : '';
            timeRangeField.style.display = isTop ? '' : 'none';
          }
          modeSelect.addEventListener('change', updateModeFields);
          updateModeFields();

          document.getElementById('grid-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const form = e.target;
            const btn = document.getElementById('submit-btn');
            const progressSection = document.getElementById('progress-section');
            const progressBar = document.getElementById('progress-bar-inner');
            const progressMsg = document.getElementById('progress-message');

            btn.disabled = true;
            btn.textContent = 'Starting...';
            progressSection.style.display = 'block';
            progressBar.style.width = '2%';
            progressMsg.textContent = 'Submitting...';

            const formData = new FormData(form);
            let taskId;

            try {
              const res = await fetch('/generate', { method: 'POST', body: formData });
              const data = await res.json();
              if (data.error) {
                if (data.expired) { window.location.href = '/login'; return; }
                throw new Error(data.error);
              }
              taskId = data.task_id;
            } catch (err) {
              progressMsg.textContent = 'Error: ' + err.message;
              btn.disabled = false;
              btn.textContent = 'Generate Grid';
              return;
            }

            const poll = setInterval(async () => {
              try {
                const res = await fetch('/progress/' + taskId);
                const data = await res.json();
                const pct = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
                progressBar.style.width = Math.max(pct, 2) + '%';
                progressMsg.textContent = data.message;

                if (data.status === 'done') {
                  clearInterval(poll);
                  progressBar.style.width = '100%';
                  progressMsg.textContent = 'Redirecting...';
                  window.location.href = '/result';
                } else if (data.status === 'expired') {
                  clearInterval(poll);
                  window.location.href = '/login';
                } else if (data.status === 'error') {
                  clearInterval(poll);
                  progressMsg.textContent = 'Error: ' + data.message;
                  btn.disabled = false;
                  btn.textContent = 'Generate Grid';
                }
              } catch (err) {
                clearInterval(poll);
                progressMsg.textContent = 'Connection lost. Please try again.';
                btn.disabled = false;
                btn.textContent = 'Generate Grid';
              }
            }, 500);
          });
        </script>
      </body>
    </html>
    """)


@app.route("/login")
def login():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    )
    return redirect(sp_oauth.get_authorize_url())


@app.route("/callback")
def callback():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    )
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code, as_dict=True)

    if token_info:
        session["token_info"] = token_info
        return redirect(url_for("index"))
    else:
        return "Could not get token"


def extract_playlist_id(user_input: str) -> str:
    user_input = user_input.strip()
    if "playlist/" in user_input:
        parts = user_input.split("playlist/")[1]
        if "?" in parts:
            parts = parts.split("?")[0]
        return parts
    return user_input


@app.route("/generate", methods=["POST"])
def generate():
    if "token_info" not in session:
        return jsonify({"error": "Not logged in", "expired": True}), 401

    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    )

    try:
        token_info = sp_oauth.validate_token(session["token_info"])
        if not token_info:
            token_info = sp_oauth.refresh_access_token(session["token_info"]["refresh_token"])
            session["token_info"] = token_info
    except Exception:
        session.pop("token_info", None)
        return jsonify({"error": "Session expired. Please log in again.", "expired": True}), 401

    mode = request.form.get("mode", "playlist")
    playlist_id = request.form.get("playlist_id", "").strip()
    remove_dups = (request.form.get("remove_dups", "yes") == "yes")
    pattern = request.form.get("pattern", "normal")
    time_range = request.form.get("time_range", "medium_term")
    cell_size = int(request.form.get("cell_size", "100"))
    if cell_size not in (100, 200, 300):
        cell_size = 100
    rounded = (request.form.get("rounded", "no") == "yes")
    framed = (request.form.get("framed", "no") == "yes")

    sp = spotipy.Spotify(auth=token_info["access_token"])

    real_id = None
    if mode == "playlist" and playlist_id:
        real_id = extract_playlist_id(playlist_id)
        try:
            playlist_info = sp.playlist(real_id)
            playlist_name = playlist_info['name'].replace(" ", "_")
        except SpotifyException as e:
            if e.http_status == 401:
                session.pop("token_info", None)
                return jsonify({"error": "Session expired. Please log in again.", "expired": True}), 401
            return jsonify({"error": "Could not find that playlist. Check the URL/ID."}), 400
        except Exception:
            return jsonify({"error": "Could not find that playlist. Check the URL/ID."}), 400
    else:
        playlist_name = "top_tracks"

    cleanup_old_temp_file()
    prune_stale_tasks()

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "running",
        "current": 0,
        "total": 1,
        "message": "Starting...",
        "created_at": time.time(),
    }

    session["current_task_id"] = task_id
    session["playlist_name"] = playlist_name
    session["pattern"] = pattern
    session["cell_size"] = cell_size

    def run_generation():
        def on_progress(current, total, message):
            tasks[task_id]["current"] = current
            tasks[task_id]["total"] = total
            tasks[task_id]["message"] = message

        try:
            image = generate_album_grid(
                sp=sp,
                mode=mode,
                playlist_id=real_id,
                remove_dups=remove_dups,
                pattern=pattern,
                time_range=time_range,
                cell_size=cell_size,
                rounded=rounded,
                framed=framed,
                progress_callback=on_progress,
            )

            if framed:
                grid_size = round(image.width / (cell_size * 1.08))
            else:
                grid_size = image.width // cell_size
            final_filename = f"{playlist_name}_{grid_size}x{grid_size}_{pattern}.png"

            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            image.save(tmp_file, 'PNG')
            tmp_file.close()

            tasks[task_id]["image_path"] = tmp_file.name
            tasks[task_id]["image_name"] = final_filename
            tasks[task_id]["status"] = "done"
            tasks[task_id]["message"] = "Done!"
        except SpotifyException as e:
            if e.http_status == 401:
                tasks[task_id]["status"] = "expired"
                tasks[task_id]["message"] = "Session expired. Please log in again."
            else:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["message"] = str(e)
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["message"] = str(e)

    thread = threading.Thread(target=run_generation, daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/progress/<task_id>")
def progress(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"status": "error", "message": "Task not found", "current": 0, "total": 1})
    return jsonify({
        "status": task["status"],
        "current": task["current"],
        "total": task["total"],
        "message": task["message"],
    })


@app.route("/result")
def result():
    task_id = session.get("current_task_id")
    if not task_id or task_id not in tasks:
        return redirect(url_for("index"))

    task = tasks[task_id]
    if task["status"] != "done":
        return redirect(url_for("index"))

    session["generated_image_path"] = task["image_path"]
    session["generated_image_name"] = task["image_name"]

    del tasks[task_id]

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <title>Your Grid - Spotify Covers</title>
        """ + COMMON_HEAD + """
        <style>
          .result-card {
            background: none;
            border: none; border-radius: 20px;
            overflow: visible;
          }
          .result-img {
            border-radius: 0;
            box-shadow: 0 4px 24px rgba(0,0,0,0.5);
            transition: transform 0.2s;
            background: transparent;
          }
          .result-img:hover { transform: scale(1.01); }
        </style>
      </head>
      <body>
        """ + NAVBAR_LOGGED_IN + """
        <main>
          <div class="container py-4">
            <div class="row justify-content-center">
              <div class="col-lg-9">
                <div class="result-card text-center p-4 p-md-5">
                  <h2 style="font-weight:800; color:var(--sp-white); font-size:1.8rem;" class="mb-2">Your Grid</h2>
                  <p style="color:var(--sp-muted); font-size:0.95rem;" class="mb-4">Right-click the image to save, or use the button below.</p>
                  <img src="/preview" alt="album grid" class="result-img img-fluid" style="max-height:75vh;" />
                  <div class="mt-4 d-flex justify-content-center gap-3 flex-wrap">
                    <a href="/download" class="btn btn-sp px-4" style="border-radius:8px;" download="{{ filename }}">Download PNG</a>
                    <a href="/" class="btn btn-sp-outline px-4" style="border-radius:8px;">New Grid</a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </main>
        """ + FOOTER + """
      </body>
    </html>
    """, filename=session["generated_image_name"])


@app.route("/preview")
def preview():
    if "generated_image_path" not in session:
        return redirect(url_for("index"))
    return send_file(session["generated_image_path"], mimetype='image/png')


@app.route("/download")
def download():
    if "generated_image_path" not in session or "generated_image_name" not in session:
        return redirect(url_for("index"))
    return send_file(
        session["generated_image_path"],
        mimetype='image/png',
        as_attachment=True,
        download_name=session["generated_image_name"],
    )


@app.route("/logout")
def logout():
    cleanup_old_temp_file()
    session.pop("token_info", None)
    session.pop("current_task_id", None)
    session.pop("playlist_name", None)
    session.pop("pattern", None)
    session.pop("cell_size", None)
    return redirect(url_for("index"))


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(
        os.path.abspath(os.path.dirname(__file__)),
        "sitemap.xml",
        mimetype="application/xml",
    )


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'spotify.png',
        mimetype='image/png',
    )


if __name__ == "__main__":
    app.run(debug=True)
