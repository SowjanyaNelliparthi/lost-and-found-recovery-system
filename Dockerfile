FROM python:3.13-slim
WORKDIR /app
ENV HOST=0.0.0.0
ENV PORT=8000
ENV APP_ENV=production
ENV DB_PATH=/app/data/lost-found.sqlite
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py index.html styles.css app.js ./
COPY lost_found ./lost_found
RUN mkdir -p /app/data && useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app"]
