#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

# Create application instance
application = create_app()

if __name__ == "__main__":
    # For development testing with gunicorn
    application.run()
