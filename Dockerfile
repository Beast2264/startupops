# StartupOps container image. OPTIONAL — only needed if you choose to deploy
# this somewhere beyond your own machine (e.g. Cloud Run, or any container
# host). Running locally with `python run.py` needs none of this.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code only (tests/venv excluded via .gcloudignore).
COPY app ./app

# Most container platforms inject $PORT; defaults to 8080 if unset. Bind all
# interfaces inside the container — this template has NO built-in
# authentication, so do not expose it publicly without adding your own
# (see README-JARRAD.md). The data backend defaults to the seeded in-memory
# repository unless STARTUPOPS_DATA_BACKEND=firestore is set with your own
# STARTUPOPS_FIRESTORE_PROJECT.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
