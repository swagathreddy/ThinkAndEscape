#!/bin/bash
echo "Build script started..."
pip install -r requirements.txt
echo "Dependencies installed."
python manage.py collectstatic --noinput --clear
echo "Static files collected."
echo "Build complete."
