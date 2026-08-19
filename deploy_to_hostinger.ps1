$ServerIP = "200.234.32.207"
$Username = "u123456789" # Replace with your hostinger username
$Port = 65002

Write-Host "Connecting to Hostinger to deploy latest code..." -ForegroundColor Cyan

# SSH into the server, pull code, fix Nginx, and restart Gunicorn + Nginx
$sshCommand = @"
cd /var/www/loveable_backend_PRO &&
echo 'Pulling latest code from GitHub...' &&
git pull origin main &&

echo 'Fixing Nginx duplicate client_max_body_size...' &&
sudo sed -i '/client_max_body_size/d' /etc/nginx/nginx.conf &&
sudo sed -i '/http {/a \    client_max_body_size 150M;' /etc/nginx/nginx.conf &&

echo 'Restarting Nginx...' &&
sudo systemctl restart nginx &&

echo 'Restarting Gunicorn Backend Process...' &&
pkill gunicorn
sleep 2
nohup /var/www/loveable_backend_PRO/venv/bin/gunicorn vibely_backend.wsgi:application --bind 127.0.0.1:8000 --workers 3 > gunicorn.log 2>&1 &

echo 'Restarting Celery Worker and Beat...' &&
pkill -f 'celery'
sleep 2
nohup /var/www/loveable_backend_PRO/venv/bin/celery -A vibely_backend worker -l info --concurrency=4 > celery_worker.log 2>&1 &
nohup /var/www/loveable_backend_PRO/venv/bin/celery -A vibely_backend beat -l info > celery_beat.log 2>&1 &

echo 'Deployment Successful!'
"@

ssh -p $Port $Username@$ServerIP $sshCommand

Write-Host "Done!" -ForegroundColor Green
