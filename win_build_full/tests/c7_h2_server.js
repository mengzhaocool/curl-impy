const http2 = require('http2');
const fs = require('fs');
const { execSync } = require('child_process');
const crypto = require('crypto');

// Generate self-signed cert
const certDir = require('os').tmpdir() + '/h2test_' + Date.now();
fs.mkdirSync(certDir, {recursive: true});
const certFile = certDir + '/cert.pem';
const keyFile = certDir + '/key.pem';
try {
  execSync(`openssl req -x509 -newkey rsa:2048 -keyout "${keyFile}" -out "${certFile}" -days 1 -nodes -subj /CN=localhost`, {stdio: 'pipe'});
} catch(e) { console.error('openssl failed:', e.message); process.exit(1); }

const cert = fs.readFileSync(certFile);
const key = fs.readFileSync(keyFile);

function createServer(port, mode, largeData) {
  const server = http2.createSecureServer({cert, key, allowHTTP1: true});

  server.on('stream', (stream, headers) => {
    const path = headers[':path'];
    const method = headers[':method'];

    if (mode === 'rst') {
      // Send partial then RST_STREAM
      stream.respond({':status': 200, 'content-type': 'text/plain'});
      stream.write('partial');
      stream.close(http2.constants.NGHTTP2_STREAM_ERROR);
      return;
    }

    if (mode === 'goaway') {
      // Send GOAWAY
      stream.session.goaway(http2.constants.NGHTTP2_NO_ERROR);
      return;
    }

    if (largeData) {
      // Large response with MD5
      stream.respond({':status': 200, 'content-type': 'application/octet-stream', 'content-length': largeData.length, 'x-md5': crypto.createHash('md5').update(largeData).digest('hex')});
      stream.end(largeData);
      return;
    }

    // Normal response
    const respHeaders = {':status': 200, 'content-type': 'application/json'};
    // Collect all headers
    const sentHeaders = {};
    for (const [k, v] of Object.entries(headers)) {
      if (!k.startsWith(':') && k !== 'host') sentHeaders[k] = v;
    }
    const body = JSON.stringify({path, method, headers: sentHeaders, h2: true});
    stream.respond(respHeaders);
    stream.end(body);
  });

  server.on('error', (err) => { /* ignore */ });
  server.listen(port, '127.0.0.1');
  return server;
}

// Create servers for different test modes
const servers = {
  basic: createServer(19601, 'normal'),
  multi: createServer(19602, 'normal'),
  large: createServer(19603, 'normal', Buffer.alloc(10*1024*1024, 0x42)),
  bigheader: createServer(19604, 'normal'),
  rst: createServer(19605, 'rst'),
  goaway: createServer(19606, 'goaway'),
};

// Compute expected MD5 for large data
const expectedMd5 = crypto.createHash('md5').update(Buffer.alloc(10*1024*1024, 0x42)).digest('hex');
console.log('Large data MD5:', expectedMd5);
console.log('Servers started on ports 19601-19606');
console.log('READY');
