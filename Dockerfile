FROM python:3.12-slim
WORKDIR /app
COPY app.py ./
COPY static ./static
ENV HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1 STUDIO_DATA_DIR=/var/lib/studio
EXPOSE 8000
CMD ["python", "app.py"]
