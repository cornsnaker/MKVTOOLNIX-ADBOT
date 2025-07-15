FROM python:3.10-slim

WORKDIR /app

# Install MKVToolNix and dependencies
RUN apt-get update && apt-get install -y \
    mkvtoolnix \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
