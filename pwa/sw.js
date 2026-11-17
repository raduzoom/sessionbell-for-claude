// Sessionbell: the installed app's service worker.
// It caches only the page shell (GET /, which holds no session data), so the app window still opens while
// server.py is down and shows "Can't reach the dashboard server" until it's back. /status.json and
// /state.json are never cached or touched: they hold real session titles (AGENTS.md, Rules).
'use strict';

var CACHE = 'sn-shell-v2';
var SHELL = '/';

self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(CACHE).then(function (c) { return c.add(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (event) {
  var req = event.request;
  // Only opening the page itself; every other request (status, state, POST, icons) goes to the network untouched.
  if (req.mode !== 'navigate' || req.method !== 'GET' || new URL(req.url).pathname !== SHELL) return;
  event.respondWith(fetch(req).then(function (res) {
    if (res.ok) {
      var copy = res.clone();
      event.waitUntil(caches.open(CACHE).then(function (c) { return c.put(SHELL, copy); }));
    }
    return res;
  }, function () {
    return caches.match(SHELL).then(function (hit) { return hit || Response.error(); });
  }));
});
