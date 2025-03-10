import os
import tempfile
from flask import Flask, request, redirect, url_for, session, send_file, render_template_string
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

from albumgrids import generate_album_grid  # your existing function

app = Flask(__name__)
app.secret_key = "YOUR_FLASK_SECRET_KEY"

# Spotify credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "YOUR_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "YOUR_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:5000/callback"

# Scopes needed
SCOPE = "playlist-read-private user-top-read"


@app.route("/")
def index():
    # If user not logged in, show a "Login with Spotify" link
    if "token_info" not in session:
        return render_template_string("""
        <!DOCTYPE html>
        <html>
          <head>
            <!-- Bootstrap 5 via CDN -->
            <link rel="stylesheet" 
                  href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            <title>Welcome</title>
          </head>
          <body class="bg-light">
            <div class="container py-5">
              <div class="row justify-content-center">
                <div class="col-md-6">
                  <div class="card shadow">
                    <div class="card-body text-center">
                      <h1>Welcome to the Album Grid App</h1>
                      <p><a href="/login" class="btn btn-primary">Login with Spotify</a></p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </body>
        </html>
        """)

    # If logged in, show the form in a centered card
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <title>Generate Album Grid</title>
        <script>
          function showLoading() {
            // Show the progress bar when the form is submitted
            document.getElementById("loading").classList.remove("d-none");
          }
        </script>
      </head>
      <body class="bg-light">
        <div class="container py-5">
          <div class="row justify-content-center">
            <div class="col-md-6">
              <div class="card shadow">
                <div class="card-body">
                  <h1 class="card-title text-center">Generate Album Grid</h1>
                  <form action="/generate" method="post" onsubmit="showLoading()">
                    <div class="mb-3">
                      <label class="form-label">Mode:</label>
                      <select name="mode" class="form-select">
                        <option value="playlist">Playlist</option>
                        <option value="top">Top Tracks</option>
                      </select>
                    </div>

                    <div class="mb-3">
                      <label class="form-label">Playlist ID (if mode=playlist):</label>
                      <input type="text" name="playlist_id" class="form-control"
                             placeholder="e.g. 37i9dQZF..." />
                    </div>

                    <div class="mb-3">
                      <label class="form-label">Remove Duplicates?</label>
                      <select name="remove_dups" class="form-select">
                        <option value="no">No</option>
                        <option value="yes">Yes</option>
                      </select>
                    </div>

                    <div class="mb-3">
                      <label class="form-label">Pattern:</label>
                      <select name="pattern" class="form-select">
                        <option value="normal">Normal</option>
                        <option value="diagonal">Diagonal</option>
                        <option value="spiral">Spiral</option>
                        <option value="checkered">Checkered</option>
                      </select>
                    </div>

                    <button type="submit" class="btn btn-primary w-100">
                      Generate Grid
                    </button>
                  </form>

                  <!-- Hidden loading progress bar -->
                  <div id="loading" class="d-none text-center my-3">
                    <div class="progress" style="height: 30px;">
                      <div class="progress-bar progress-bar-striped progress-bar-animated"
                           role="progressbar"
                           style="width: 100%;"
                           aria-valuenow="100"
                           aria-valuemin="0"
                           aria-valuemax="100">
                        Generating...
                      </div>
                    </div>
                    <p class="mt-2">Please wait while we generate your grid...</p>
                  </div>

                  <hr>
                  <p><a href="/logout" class="btn btn-secondary">Logout</a></p>
                </div>
              </div>
            </div>
          </div>
        </div>
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


@app.route("/generate", methods=["POST"])
def generate():
    # Make sure we have token_info
    if "token_info" not in session:
        return redirect(url_for("index"))

    sp_oauth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    )

    # Validate or refresh
    token_info = sp_oauth.validate_token(session["token_info"])
    if not token_info:
        token_info = sp_oauth.refresh_access_token(session["token_info"]["refresh_token"])
        session["token_info"] = token_info

    # Grab form data
    mode = request.form.get("mode", "playlist")
    playlist_id = request.form.get("playlist_id", "").strip()
    remove_dups = (request.form.get("remove_dups", "no") == "yes")
    pattern = request.form.get("pattern", "normal")

    sp = spotipy.Spotify(auth=token_info["access_token"])

    # =============== RESTORE OLD NAMING SCHEME ===============
    # 1) Get playlist name or "top_tracks"
    if mode == "playlist" and playlist_id:
        playlist_info = sp.playlist(playlist_id)
        raw_name = playlist_info['name']
        playlist_name = raw_name.replace(" ", "_")
    else:
        playlist_name = "top_tracks"

    # 2) Generate the collage
    try:
        image = generate_album_grid(
            sp=sp,
            mode=mode,
            playlist_id=playlist_id if playlist_id else None,
            remove_dups=remove_dups,
            pattern=pattern
        )
    except Exception as e:
        return f"<h1>Error:</h1><p>{e}</p><p><a href='/'>Back</a></p>"

    # 3) Figure out the grid size so we can build the final filename
    #    The function 'generate_album_grid' downloads images, so let's do it again or store it.
    #    We can just do a quick approach: the final image is square with dimension = 100*grid_size
    #    So we can guess: grid_size = image.width // 100
    grid_size = image.width // 100  # each cell = 100px

    # 4) Build a filename
    final_filename = f"{playlist_name}_{grid_size}x{grid_size}_{pattern}.png"

    # Save the image to a temp file
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    image.save(tmp_file, 'PNG')
    tmp_file.close()

    # Store the path & final_filename in session
    session["generated_image_path"] = tmp_file.name
    session["generated_image_name"] = final_filename

    # Render a preview page with the image in a card
    return render_template_string("""
    <!DOCTYPE html>
    <html>
      <head>
        <link rel="stylesheet"
              href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <title>Your Grid</title>
      </head>
      <body class="bg-light">
        <div class="container py-5">
          <div class="row justify-content-center">
            <div class="col-md-8">
              <div class="card shadow">
                <div class="card-body text-center">
                  <h1>Your Grid</h1>
                  <p class="text-muted">Right-click the image to save, or use the download link below.</p>
                  <img src="/preview" alt="album grid" class="img-fluid border" />
                  <br><br>
                  <a href="/download" class="btn btn-primary"
                     download="{{ filename }}">Download PNG</a>
                  <br><br>
                  <a href="/" class="btn btn-secondary">Back to Home</a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """, filename=session["generated_image_name"])


@app.route("/preview")
def preview():
    """Route to show the image in an <img> tag."""
    if "generated_image_path" not in session:
        return redirect(url_for("index"))
    path = session["generated_image_path"]
    return send_file(path, mimetype='image/png')


@app.route("/download")
def download():
    """Route to download the image with the old naming scheme."""
    if "generated_image_path" not in session or "generated_image_name" not in session:
        return redirect(url_for("index"))

    path = session["generated_image_path"]
    name = session["generated_image_name"]
    return send_file(path, mimetype='image/png', as_attachment=True, download_name=name)


@app.route("/logout")
def logout():
    session.pop("token_info", None)
    session.pop("generated_image_path", None)
    session.pop("generated_image_name", None)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
