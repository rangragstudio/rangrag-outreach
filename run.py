"""
Single-command launcher for Rangrag Archviz Studio CRM.
Starts the FastAPI server with Uvicorn.
"""

import uvicorn
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=" * 70)
    print("   RANGRAG ARCHVIZ STUDIO — OUTREACH CRM & PARTNERSHIP HUB")
    print("   Founder: Raj Shekhada | 3D Architectural Visualization")
    print("=" * 70)
    print(">> Starting local server on http://127.0.0.1:8000")
    print(">> Dashboard UI: http://127.0.0.1:8000")
    print(">> API Documentation: http://127.0.0.1:8000/docs")
    print("=" * 70)
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
