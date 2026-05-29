FROM python:3.12-slim

# Добавь DNS сервер
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf

WORKDIR /app

# Установи зависимости
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libjpeg-dev zlib1g-dev libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/instance /app/static/uploads
EXPOSE 5000
CMD ["python", "app.py"]