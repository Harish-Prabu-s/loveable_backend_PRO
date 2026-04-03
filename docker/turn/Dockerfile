FROM coturn/coturn:latest

# Ensure configuration is copied
COPY turnserver.conf /etc/turnserver.conf

# Use the config file
CMD ["--config-file=/etc/turnserver.conf"]
