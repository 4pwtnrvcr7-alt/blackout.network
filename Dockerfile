# blackout.network public web node (Render free web service). Data arrives from the box via /internal/sync (render_sync.py).
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000 TZ=America/New_York
RUN useradd --create-home --uid 10001 bn
WORKDIR /workspace/blackout
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY app/ /workspace/blackout/
RUN mkdir -p logs snapshots static/vsubs video_subs newsletter_outbox && chown -R bn:bn /workspace
USER bn
EXPOSE 10000
CMD ["python3", "render_app.py"]
