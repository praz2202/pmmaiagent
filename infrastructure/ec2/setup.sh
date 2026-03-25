#!/bin/bash
# EC2 setup script — run once on a fresh Ubuntu 22.04 instance
# Usage: ssh into EC2, then: bash setup.sh

set -e

echo "=== Installing Docker ==="
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git nginx certbot python3-certbot-nginx

sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

echo "=== Cloning repo ==="
cd /home/ubuntu
git clone https://github.com/praz2202/pmmaiagent.git
cd pmmaiagent

echo "=== Create .env.prod ==="
echo "Create .env.prod with your production keys:"
echo "cp .env.prod.example .env.prod && nano .env.prod"

echo "=== Setup Nginx ==="
sudo tee /etc/nginx/sites-available/pmm-agent << 'NGINX'
server {
    listen 80;
    server_name api.controlflows.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
NGINX

sudo ln -sf /etc/nginx/sites-available/pmm-agent /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo "=== Done ==="
echo ""
echo "Next steps:"
echo "1. Point api.controlflows.com A record to this EC2's public IP"
echo "2. Run: sudo certbot --nginx -d api.controlflows.com"
echo "3. Create .env.prod and fill in keys"
echo "4. Run: cd infrastructure/ec2 && docker compose -f docker-compose.prod.yml up -d"
echo "5. Test: curl https://api.controlflows.com/health"
