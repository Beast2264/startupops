"""Local dev launcher — loopback only.

Usage:
    python run.py            # serves http://127.0.0.1:8000  (127.0.0.1 ONLY)

This binds to the loopback interface only. It does not expose the app to the
LAN or the internet. Authentication/hardening is handled later at the GCP
layer (Cloud Run + IAP/IAM); this is a local development server.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
