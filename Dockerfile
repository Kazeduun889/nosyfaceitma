FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY start.sh .
RUN chmod +x start.sh

# Initialize DB (if needed, though app does it on startup)
# RUN python db.py

EXPOSE 5000

# Run both Web App and Bot
CMD ["./start.sh"]
