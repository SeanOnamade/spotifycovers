# albumgrids.py

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PIL import Image
import requests
from io import BytesIO
import os
import colorsys
import numpy as np
import math

def create_spotify_client(client_id, client_secret, redirect_uri, token_info):
    """
    Given Spotify credentials and an existing token_info dictionary,
    return an authenticated Spotipy client.
    """
    # Create a Spotipy client from the token info
    sp = spotipy.Spotify(
        auth=token_info["access_token"]
    )
    return sp

def calculate_grid_size(num_images):
    return int(math.floor(math.sqrt(num_images)))

def fetch_playlist_tracks(sp, playlist_id):
    tracks = []
    offset = 0
    limit = 100
    while True:
        results = sp.playlist_items(playlist_id, offset=offset, limit=limit)
        tracks.extend(results['items'])
        if len(results['items']) < limit:
            break
        offset += limit
    return tracks

def fetch_top_tracks(sp):
    tracks = []
    offset = 0
    limit = 50
    while True:
        results = sp.current_user_top_tracks(limit=limit, offset=offset, time_range="medium_term")
        tracks.extend(results['items'])
        if len(results['items']) < limit:
            break
        offset += limit
    return tracks

def get_album_art_from_tracks(tracks):
    album_urls = []
    for item in tracks:
        try:
            # If playlist track, item['track']...
            album_url = item['track']['album']['images'][0]['url'] if 'track' in item else item['album']['images'][0]['url']
            album_urls.append(album_url)
        except (TypeError, KeyError, IndexError):
            continue
    return album_urls

def remove_duplicates(album_urls):
    unique_urls = list(dict.fromkeys(album_urls))
    return unique_urls

def get_dominant_color(image):
    image = image.convert("RGB").resize((1, 1))
    dominant_color = image.getpixel((0, 0))
    return colorsys.rgb_to_hsv(*[x / 255.0 for x in dominant_color])

def download_image(url):
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def create_normal_grid(images, grid_size):
    cell_size = 100
    grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))
    for idx, img in enumerate(images):
        row = idx // grid_size
        col = idx % grid_size
        img_resized = img.resize((cell_size, cell_size))
        grid_img.paste(img_resized, (col * cell_size, row * cell_size))
    return grid_img

def create_diagonal_grid(images, grid_size):
    cell_size = 100
    grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))
    idx = 0
    for diag in range(2 * grid_size - 1):
        for row in range(grid_size):
            col = diag - row
            if 0 <= col < grid_size and idx < len(images):
                img_resized = images[idx].resize((cell_size, cell_size))
                grid_img.paste(img_resized, (col * cell_size, row * cell_size))
                idx += 1
    return grid_img

def create_checkered_grid(images, grid_size):
    cell_size = 100
    grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))
    for idx, img in enumerate(images):
        row = idx // grid_size
        col = idx % grid_size
        if (row + col) % 2 == 0:
            img_resized = img.resize((cell_size, cell_size))
            grid_img.paste(img_resized, (col * cell_size, row * cell_size))
    return grid_img

def create_spiral_grid(images, grid_size):
    cell_size = 100
    grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    direction_idx = 0
    x, y = 0, 0
    boundaries = [0, grid_size - 1, grid_size - 1, 0]
    for idx, img in enumerate(images):
        img_resized = img.resize((cell_size, cell_size))
        grid_img.paste(img_resized, (y * cell_size, x * cell_size))
        dx, dy = directions[direction_idx]
        nx, ny = x + dx, y + dy
        if not (boundaries[3] <= ny <= boundaries[1] and boundaries[0] <= nx <= boundaries[2]):
            if direction_idx == 0: boundaries[0] += 1
            elif direction_idx == 1: boundaries[1] -= 1
            elif direction_idx == 2: boundaries[2] -= 1
            elif direction_idx == 3: boundaries[3] += 1
            direction_idx = (direction_idx + 1) % 4
            dx, dy = directions[direction_idx]
        x, y = x + dx, y + dy
    return grid_img

def generate_album_grid(sp, mode="playlist", playlist_id=None, remove_dups=False, pattern="normal"):
    """
    Main function to generate the album grid image (as a PIL Image object).
    :param sp: Spotipy client
    :param mode: 'playlist' or 'top'
    :param playlist_id: if 'playlist' mode, pass a valid playlist_id
    :param remove_dups: bool to remove duplicate covers
    :param pattern: one of ['normal','diagonal','spiral','checkered']
    :return: A PIL Image object with the final collage
    """
    if mode == 'playlist':
        tracks = fetch_playlist_tracks(sp, playlist_id)
    else:  # 'top'
        tracks = fetch_top_tracks(sp)

    album_urls = get_album_art_from_tracks(tracks)
    MAX_COVERS = 300
    album_urls = album_urls[:MAX_COVERS]
    if not album_urls:
        raise ValueError("No album art found.")

    if remove_dups:
        album_urls = remove_duplicates(album_urls)

    num_images = len(album_urls)
    grid_size = calculate_grid_size(num_images)

    # Download images and compute dominant colors
    images = []
    colors = []
    for url in album_urls[:grid_size * grid_size]:  # limit to fill the grid exactly
        try:
            img = download_image(url)
            images.append(img)
            colors.append(get_dominant_color(img))
        except Exception as e:
            print(f"Error downloading {url}: {e}")

    # Sort by hue
    sorted_indices = np.argsort([c[0] for c in colors])
    images = [images[i] for i in sorted_indices]

    if pattern == 'diagonal':
        grid_image = create_diagonal_grid(images, grid_size)
    elif pattern == 'spiral':
        grid_image = create_spiral_grid(images, grid_size)
    elif pattern == 'checkered':
        grid_image = create_checkered_grid(images, grid_size)
    else:
        grid_image = create_normal_grid(images, grid_size)

    return grid_image


# import spotipy
# from spotipy.oauth2 import SpotifyOAuth
# from PIL import Image
# import requests
# from io import BytesIO
# import os
# import colorsys
# import numpy as np
# import math

# # Spotify API credentials (replace with your own)
# SPOTIFY_CLIENT_ID = "3de10d249c544bf88721bb997c9d62af"
# SPOTIFY_CLIENT_SECRET = "b1a762f831e5458bb9b1cf538c3fb4b3"
# SPOTIFY_REDIRECT_URI = "http://localhost:8080"

# # Parameters
# OUTPUT_FILE = "album_grid.png"

# # Authenticate with Spotify
# sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
#     client_id=SPOTIFY_CLIENT_ID,
#     client_secret=SPOTIFY_CLIENT_SECRET,
#     redirect_uri=SPOTIFY_REDIRECT_URI,
#     scope="playlist-read-private user-top-read"
# ))

# # Function to calculate the largest square grid size
# def calculate_grid_size(num_images):
#     return int(math.floor(math.sqrt(num_images)))

# # Fetch playlist tracks
# def fetch_playlist_tracks(playlist_id):
#     print(f"Fetching tracks from playlist {playlist_id}...")
#     tracks = []
#     offset = 0
#     limit = 100  # Maximum allowed by Spotify API

#     while True:
#         results = sp.playlist_items(playlist_id, offset=offset, limit=limit)
#         tracks.extend(results['items'])
#         if len(results['items']) < limit:
#             break
#         offset += limit

#     return tracks

# # Fetch top tracks
# def fetch_top_tracks():
#     print("Fetching top tracks...")
#     tracks = []
#     offset = 0
#     limit = 50  # Maximum allowed by Spotify API

#     while True:
#         results = sp.current_user_top_tracks(limit=limit, offset=offset, time_range="medium_term")
#         tracks.extend(results['items'])
#         if len(results['items']) < limit:
#             break
#         offset += limit

#     return tracks

# # Get album art from tracks
# def get_album_art_from_tracks(tracks):
#     album_urls = []

#     for item in tracks:
#         try:
#             album_url = item['track']['album']['images'][0]['url'] if 'track' in item else item['album']['images'][0]['url']
#             album_urls.append(album_url)
#         except (TypeError, KeyError, IndexError):
#             continue

#     return album_urls

# # Remove duplicate album URLs
# def remove_duplicates(album_urls):
#     print("Checking for duplicates...")
#     unique_urls = list(dict.fromkeys(album_urls))
#     print(f"Removed {len(album_urls) - len(unique_urls)} duplicates.")
#     return unique_urls

# # Download album art and calculate dominant color
# def get_dominant_color(image):
#     image = image.convert("RGB").resize((1, 1))  # Convert to RGB and resize
#     dominant_color = image.getpixel((0, 0))  # Get the single pixel's color
#     return colorsys.rgb_to_hsv(*[x / 255.0 for x in dominant_color])

# def download_image(url):
#     response = requests.get(url)
#     return Image.open(BytesIO(response.content))

# # Create the grid in normal pattern
# def create_normal_grid(images, grid_size):
#     cell_size = 100  # Size of each cell in the grid
#     grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))

#     for idx, img in enumerate(images):
#         row = idx // grid_size
#         col = idx % grid_size
#         img_resized = img.resize((cell_size, cell_size))
#         grid_img.paste(img_resized, (col * cell_size, row * cell_size))

#     return grid_img

# # Create the grid in diagonal pattern
# def create_diagonal_grid(images, grid_size):
#     cell_size = 100  # Size of each cell in the grid
#     grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))

#     idx = 0
#     for diag in range(2 * grid_size - 1):
#         for row in range(grid_size):
#             col = diag - row
#             if 0 <= col < grid_size and idx < len(images):
#                 img_resized = images[idx].resize((cell_size, cell_size))
#                 grid_img.paste(img_resized, (col * cell_size, row * cell_size))
#                 idx += 1

#     return grid_img

# # Create the grid in checkered pattern
# def create_checkered_grid(images, grid_size):
#     cell_size = 100  # Size of each cell in the grid
#     grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))

#     for idx, img in enumerate(images):
#         row = idx // grid_size
#         col = idx % grid_size
#         if (row + col) % 2 == 0:  # Alternate cells
#             img_resized = img.resize((cell_size, cell_size))
#             grid_img.paste(img_resized, (col * cell_size, row * cell_size))

#     return grid_img

# def create_spiral_grid(images, grid_size):
#     cell_size = 100  # Size of each cell in the grid
#     grid_img = Image.new('RGB', (cell_size * grid_size, cell_size * grid_size))

#     # Directions: right, down, left, up
#     directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
#     direction_idx = 0  # Start moving to the right

#     x, y = 0, 0  # Start at the top-left corner
#     boundaries = [0, grid_size - 1, grid_size - 1, 0]  # Top, right, bottom, left

#     for idx, img in enumerate(images):
#         img_resized = img.resize((cell_size, cell_size))
#         grid_img.paste(img_resized, (y * cell_size, x * cell_size))

#         # Move in the current direction
#         dx, dy = directions[direction_idx]
#         nx, ny = x + dx, y + dy

#         # Check if we need to change direction
#         if not (boundaries[3] <= ny <= boundaries[1] and boundaries[0] <= nx <= boundaries[2]):
#             # Update boundaries after a direction change
#             if direction_idx == 0: boundaries[0] += 1  # Top boundary moves down
#             elif direction_idx == 1: boundaries[1] -= 1  # Right boundary moves left
#             elif direction_idx == 2: boundaries[2] -= 1  # Bottom boundary moves up
#             elif direction_idx == 3: boundaries[3] += 1  # Left boundary moves right

#             direction_idx = (direction_idx + 1) % 4  # Change direction
#             dx, dy = directions[direction_idx]

#         # Update position
#         x, y = x + dx, y + dy

#     return grid_img

# # Main program
# mode = input("Enter 'playlist' to use a playlist or 'top' to use your top tracks: ").strip().lower()
# if mode == 'playlist':
#     playlist_id = input("Enter Spotify playlist ID: ").strip()
#     playlist_name = None
# elif mode == 'top':
#     playlist_name = "top_tracks"
# else:
#     print("Invalid input. Exiting.")
#     exit()

# remove_duplicates_option = input("Do you want to remove duplicate album covers? (yes/no): ").strip().lower()
# pattern = input("Enter 'diagonal' for diagonal grid, 'normal' for normal grid, 'spiral' for spiral, or 'checkered' for checkered grid: ").strip().lower()

# if mode == 'playlist':
#     playlist_info = sp.playlist(playlist_id)
#     playlist_name = playlist_info['name'].replace(" ", "_")
#     tracks = fetch_playlist_tracks(playlist_id)
# elif mode == 'top':
#     tracks = fetch_top_tracks()

# album_urls = get_album_art_from_tracks(tracks)

# if not album_urls:
#     print("No album art found.")
#     exit()

# if remove_duplicates_option == 'yes':
#     album_urls = remove_duplicates(album_urls)

# # Calculate grid size
# num_images = len(album_urls)
# grid_size = calculate_grid_size(num_images)
# print(f"Number of images: {num_images}, Grid size: {grid_size}x{grid_size}")

# # Download and analyze album art
# print("Downloading and analyzing album art...")
# album_images = []
# album_colors = []

# for url in album_urls[:grid_size * grid_size]:  # Limit to fit the grid
#     try:
#         img = download_image(url)
#         album_images.append(img)
#         album_colors.append(get_dominant_color(img))
#     except Exception as e:
#         print(f"Error downloading {url}: {e}")

# # Sort albums by dominant color (hue, saturation, value)
# print("Sorting albums by color...")
# sorted_indices = np.argsort([color[0] for color in album_colors])  # Sort by hue (first element of HSV)
# sorted_images = [album_images[i] for i in sorted_indices]

# # Create the grid
# if pattern == 'diagonal':
#     print("Creating diagonal album grid...")
#     grid_image = create_diagonal_grid(sorted_images, grid_size)
# elif pattern == 'checkered':
#     print("Creating checkered album grid...")
#     grid_image = create_checkered_grid(sorted_images, grid_size)
# elif pattern == 'spiral':
#     print("Creating spiral album grid...")
#     grid_image = create_spiral_grid(sorted_images, grid_size)
# else:
#     print("Creating normal album grid...")
#     grid_image = create_normal_grid(sorted_images, grid_size)

# OUTPUT_FILE = f"{playlist_name}_{grid_size}x{grid_size}_{pattern}.png"
# grid_image.save(OUTPUT_FILE)
# print(f"Album grid saved as {OUTPUT_FILE}")