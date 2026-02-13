"""
Vercel serverless entry point.

Imports the Flask app from crossword_server.py and exposes it
as the WSGI application that Vercel's Python runtime expects.
"""

import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crossword_server import app
