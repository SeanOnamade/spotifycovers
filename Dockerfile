# Use an official lightweight Python image
FROM python:3.11-slim

# Set a working directory inside the container
WORKDIR /app

# Copy your requirements.txt first, so Docker can cache the pip install layer
COPY requirements.txt .

# Upgrade pip, install wheel/setuptools, then install your dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy the rest of your code into the container
COPY . .

# Expose the port (optional, but good practice)
EXPOSE 8000

# The command to run your Flask app. 
# Railway will set PORT as an environment variable. We default to 8000 if not set.
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=${PORT:-8000}"]
