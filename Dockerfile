# blackout.network public web node (Render free web service). Data arrives from the box via /internal/sync (render_sync.py).
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000 TZ=America/New_York
# t353: one malloc arena pair instead of 8 per CPU; the threaded server otherwise fragments memory past the free plan's 512 MB
ENV MALLOC_ARENA_MAX=2
RUN useradd --create-home --uid 10001 bn
WORKDIR /workspace/blackout
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
COPY app/ /workspace/blackout/
# Global Sources directory: build the SQLite/FTS index from the committed gzipped NDJSON shards (no network needed at build time)
RUN cd /workspace/blackout && python3 sources_directory.py --build
RUN mkdir -p logs snapshots static/vsubs video_subs newsletter_outbox && chown -R bn:bn /workspace
# Location-accuracy guard (Matt, Nov 23 2026): fail the image build so a bad pin change never deploys.
RUN cd /workspace/blackout && BN_PLACES_DB=/tmp/story_places_test.db python3 -m unittest tests.test_location_guard tests.test_map_pins
USER bn
EXPOSE 10000
CMD ["python3", "render_app.py"]
