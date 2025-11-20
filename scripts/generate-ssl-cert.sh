#!/bin/bash
# Generate self-signed SSL certificate for local VPN use
# This script creates a certificate valid for 365 days

set -e

DOMAIN="${1:-hanweir.146sharon.com}"
CERT_DIR="${2:-./ssl}"
DAYS_VALID=365

echo "================================================"
echo "Generating Self-Signed SSL Certificate"
echo "================================================"
echo "Domain: $DOMAIN"
echo "Certificate directory: $CERT_DIR"
echo "Valid for: $DAYS_VALID days"
echo "================================================"

# Create certificate directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate private key and certificate in one command
openssl req -x509 -nodes -days $DAYS_VALID \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"

# Set appropriate permissions
chmod 600 "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"

echo ""
echo "✅ Certificate generated successfully!"
echo ""
echo "Files created:"
echo "  Private key: $CERT_DIR/privkey.pem"
echo "  Certificate: $CERT_DIR/fullchain.pem"
echo ""
echo "Next steps:"
echo "  1. Copy certificate to your server:"
echo "     scp -r $CERT_DIR user@hanweir.146sharon.com:/path/to/mailtagger/"
echo ""
echo "  2. Configure nginx or your web server to use these certificates"
echo ""
echo "  3. In your browser, you'll need to accept the self-signed certificate"
echo "     (This is safe for local VPN use)"
echo ""

