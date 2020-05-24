import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ip = sys.argv[1]
port = int(sys.argv[2])
direc = sys.argv[3]

server = ThreadingHTTPServer((ip,port),SimpleHTTPRequestHandler)
server.serve_forever()