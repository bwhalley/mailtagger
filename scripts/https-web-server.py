#!/usr/bin/env python3
"""
Simple HTTPS server for serving the web UI
Only needed if you want to serve on port 8080 with HTTPS directly
(Not needed if using nginx - which is recommended)
"""
import http.server
import ssl
import sys
import os
from pathlib import Path

# Configuration
DEFAULT_PORT = 8080
SSL_CERT = os.getenv('SSL_CERT', './ssl/fullchain.pem')
SSL_KEY = os.getenv('SSL_KEY', './ssl/privkey.pem')

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    
    # Check if certificate files exist
    if not Path(SSL_CERT).exists():
        print(f"❌ Error: Certificate not found at {SSL_CERT}")
        print(f"   Run: ./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl")
        sys.exit(1)
    
    if not Path(SSL_KEY).exists():
        print(f"❌ Error: Private key not found at {SSL_KEY}")
        print(f"   Run: ./scripts/generate-ssl-cert.sh hanweir.146sharon.com ./ssl")
        sys.exit(1)
    
    # Create server
    server_address = ('0.0.0.0', port)
    httpd = http.server.HTTPServer(server_address, http.server.SimpleHTTPRequestHandler)
    
    # Wrap with SSL
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=SSL_CERT, keyfile=SSL_KEY)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    print(f"🔒 Serving HTTPS on https://0.0.0.0:{port}/")
    print(f"   Certificate: {SSL_CERT}")
    print(f"   Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        sys.exit(0)

if __name__ == '__main__':
    main()

