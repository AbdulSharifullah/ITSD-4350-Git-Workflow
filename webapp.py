"""Small calculator web application using Python's standard library."""
import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from calculator import add


PAGE = b'''<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CI Calculator</title>
<style>body{font:18px system-ui;max-width:650px;margin:10vh auto;
padding:24px;background:#eff4fb;color:#152740}input,button{font:inherit;
padding:12px;margin:8px 0}button{background:#244dcc;color:white;border:0}
output{display:block;padding:20px;font-size:28px}</style>
<h1>CI Calculator</h1><p>A small application with a repeatable build.</p>
<form id="calculator"><label>First number <input name="a" type="number"
step="any" required></label><br><label>Second number <input name="b"
type="number" step="any" required></label><br><button>Add numbers</button>
</form><output id="result" aria-live="polite">Ready to calculate.</output>
<script>document.querySelector('form').addEventListener('submit',async e=>{
e.preventDefault();const out=document.querySelector('output');try{
const r=await fetch('/api/add?'+new URLSearchParams(new FormData(e.target)));
const data=await r.json();
out.textContent=r.ok?'Result: '+data.result:data.error;
}catch{out.textContent='Unable to connect. Please try again.'}});</script>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlparse(self.path)
        if request.path == '/':
            self.respond(200, PAGE, 'text/html; charset=utf-8')
        elif request.path == '/api/add':
            try:
                query = parse_qs(request.query)
                a, b = float(query['a'][0]), float(query['b'][0])
                result = add(a, b)
                if not all(map(math.isfinite, (a, b, result))):
                    raise ValueError('Numbers must be finite')
                self.respond(200, json.dumps({'result': result}).encode())
            except (KeyError, ValueError, IndexError):
                self.respond(400, b'{"error":"Enter two finite numbers."}')
        else:
            self.respond(404, b'{"error":"Not found"}')

    def respond(self, status, body, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    print('Calculator: http://127.0.0.1:8000')
    HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
