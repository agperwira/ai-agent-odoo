FROM python:3.11-slim

WORKDIR /app

# Install dependencies dulu (layer terpisah agar cache efisien)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Buat folder sessions agar tidak error saat runtime
RUN mkdir -p sessions

CMD ["python", "main_telegram.py"]
