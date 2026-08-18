#!/bin/bash
# Deployment script for Loveable Backend

echo "====================================="
echo " Starting Deployment Process..."
echo "====================================="

# Navigate to the project directory
cd /var/www/loveable_backend_PRO || { echo "Directory not found!"; exit 1; }

echo "1. Pulling latest code from main branch..."
git fetch origin
git reset --hard origin/main
git pull origin main

echo "2. Activating virtual environment..."
source venv/bin/activate

echo "3. Installing dependencies..."
pip install -r requirements.txt

echo "4. Running database migrations..."
python manage.py makemigrations
python manage.py migrate

echo "5. Collecting static files..."
python manage.py collectstatic --noinput

echo "6. Restarting Gunicorn/Systemd Service..."
sudo systemctl restart loveable-backend.service

echo "7. Restarting Celery Services..."
sudo systemctl restart loveable-celery.service
sudo systemctl restart loveable-celery-beat.service

echo "====================================="
echo " Deployment Completed Successfully!"
echo "====================================="
