"""Third body (P6): the public web, read-only. ATANOR's sensor/actuator for information.

Allowed: HTTP(S) GET of public pages, and two search services whose rules admit automated clients
(the Wikimedia Action API, Wiby). Not allowed and not implemented: forms, POST, login, cookies,
downloads of executables, running anything fetched. General-purpose search engines that answer bots
with a CAPTCHA or forbid them in robots.txt are not used (bypassing them is not acceptable).

Etiquette: robots.txt is honoured for every page fetch, at most one request per host per
`min_interval` seconds, an identifying User-Agent, size and content-type limits.
Reproducibility: every fetch is logged (time, URL, status, content type, bytes, sha256) and the
extracted text is archived (gzip) so a run can be re-examined in replay mode. Page text is data:
nothing in it is executed or obeyed.
"""
from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from pathlib import Path

UA = 'ATANOR-research-bot/0.1 (read-only research agent; https://github.com/Cozystone/ATANOR_THE-LAST)'
TEXT_TYPES = ('text/html', 'text/plain', 'application/xhtml+xml', 'application/json')
SERVICES = ('wikipedia', 'wiby')
MAX_BYTES = 3_000_000


class _Text(HTMLParser):
    SKIP = {'script', 'style', 'noscript', 'svg', 'head'}

    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base, self.parts, self.links, self.skip, self.href, self.anchor = base, [], [], 0, None, []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in ('p', 'br', 'tr', 'li', 'div', 'h1', 'h2', 'h3', 'h4', 'table', 'th', 'td', 'dd', 'dt'):
            self.parts.append('\n')
        if tag == 'a':
            href = dict(attrs).get('href')
            if href and not href.startswith(('javascript:', 'mailto:', '#')):
                self.href, self.anchor = urllib.parse.urljoin(self.base, href).split('#')[0], []

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == 'a' and self.href:
            self.links.append((self.href, ' '.join(''.join(self.anchor).split())))
            self.href = None
        if tag in ('td', 'th'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.href:
                self.anchor.append(data)


def page_text(raw, base):
    p = _Text(base)
    try:
        p.feed(raw)
    except Exception:                                          # malformed HTML: keep what was parsed
        pass
    text = re.sub(r'[ \t\r\f\v]+', ' ', ''.join(p.parts))
    text = '\n'.join(l.strip() for l in text.split('\n') if l.strip())
    return text, p.links


class WebSession:
    """One agent's view of the web. mode='live' fetches; mode='replay' answers only from an archive."""

    def __init__(self, archive, mode='live', min_interval=1.0, timeout=20, max_pages=None, blocked_hosts=()):
        self.archive = Path(archive)
        (self.archive / 'pages').mkdir(parents=True, exist_ok=True)
        self.mode, self.min_interval, self.timeout = mode, min_interval, timeout
        self.max_pages, self.blocked_hosts = max_pages, set(blocked_hosts)
        self.log_path = self.archive / 'fetch_log.jsonl'
        self.robots, self.last_hit, self.pages_fetched = {}, {}, 0
        self.cache = {}                                    # same key again in this session: no second request
        self.index = {}
        if mode == 'replay':
            for l in self.log_path.read_text(encoding='utf-8').splitlines():
                r = json.loads(l)
                if r.get('ok'):
                    self.index[r['key']] = r

    # --- low level ---
    def _log(self, rec):
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec) + '\n')

    def _wait(self, host):
        dt = time.monotonic() - self.last_hit.get(host, -1e9)
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self.last_hit[host] = time.monotonic()

    def _allowed(self, url):
        u = urllib.parse.urlparse(url)
        if u.scheme not in ('http', 'https') or not u.netloc:
            return False, 'scheme'
        if u.hostname in self.blocked_hosts:
            return False, 'blocked_host'
        root = f'{u.scheme}://{u.netloc}'
        if root not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(u.netloc)
                req = urllib.request.Request(root + '/robots.txt', headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    rp.parse(r.read(500_000).decode('utf-8', 'replace').splitlines())
            except urllib.error.HTTPError as e:
                rp.parse([] if e.code in (404, 410) else ['User-agent: *', 'Disallow: /'])
            except Exception:
                rp.parse(['User-agent: *', 'Disallow: /'])     # unknown robots: do not crawl
            self.robots[root] = rp
        return self.robots[root].can_fetch(UA, url), 'robots'

    def _get(self, url, kind, key, via_service=False):
        """kind: 'page' | 'search'. Returns {'ok', 'url', 'text', 'links', 'status', ...}."""
        t0 = time.time()
        rec = {'at': t0, 'kind': kind, 'key': key, 'url': url}
        if self.mode == 'replay':
            hit = self.index.get(key)
            if hit is None:
                return {'ok': False, 'url': url, 'error': 'not_in_archive'}
            data = json.loads(gzip.decompress((self.archive / 'pages' / f"{hit['sha256']}.json.gz").read_bytes()))
            return {'ok': True, 'url': hit['final_url'], 'text': data['text'], 'links': [tuple(l) for l in data['links']],
                    'status': hit['status'], 'sha256': hit['sha256'], 'replayed': True}
        if key in self.cache:
            return self.cache[key]
        if self.max_pages is not None and self.pages_fetched >= self.max_pages:
            rec.update(ok=False, error='page_budget')
            self._log(rec)
            return rec
        if not via_service:
            ok, why = self._allowed(url)
            if not ok:
                rec.update(ok=False, error=f'refused:{why}')
                self._log(rec)
                return rec
        host = urllib.parse.urlparse(url).netloc
        self._wait(host)
        self.pages_fetched += 1
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/json;q=0.9,text/plain;q=0.8'})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                ctype = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
                status, final = r.status, r.geturl()
                if ctype and ctype not in TEXT_TYPES:
                    rec.update(ok=False, status=status, ctype=ctype, error='content_type')
                    self._log(rec)
                    return rec
                raw = r.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            rec.update(ok=False, status=e.code, error='http')
            self._log(rec)
            return rec
        except Exception as e:
            rec.update(ok=False, error=type(e).__name__)
            self._log(rec)
            return rec
        body = raw[:MAX_BYTES].decode('utf-8', 'replace')
        if ctype == 'application/json':
            text, links = body, []
        else:
            text, links = page_text(body, final)
        payload = json.dumps({'text': text, 'links': links}).encode('utf-8')
        sha = hashlib.sha256(payload).hexdigest()
        (self.archive / 'pages' / f'{sha}.json.gz').write_bytes(gzip.compress(payload))
        rec.update(ok=True, status=status, final_url=final, ctype=ctype, bytes=len(raw), sha256=sha,
                   truncated=len(raw) > MAX_BYTES, seconds=time.time() - t0)
        self._log(rec)
        out = {'ok': True, 'url': final, 'text': text, 'links': links, 'status': status, 'sha256': sha}
        self.cache[key] = out
        return out

    # --- the agent's web actions ---
    def open(self, url):
        return self._get(url, 'page', 'page:' + url)

    def search(self, service, query, limit=6):
        """Returns {'ok', 'results': [url, ...]} — the agent then decides which pages to open."""
        if service == 'wikipedia':
            api = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode(
                {'action': 'query', 'list': 'search', 'srsearch': query, 'format': 'json', 'srlimit': limit, 'maxlag': 5})
            r = self._get(api, 'search', f'search:wikipedia:{query}', via_service=True)
            if not r.get('ok'):
                return {'ok': False, 'results': [], 'error': r.get('error')}
            try:
                titles = [x['title'] for x in json.loads(r['text'])['query']['search']]
            except Exception:
                return {'ok': False, 'results': [], 'error': 'parse'}
            return {'ok': True, 'results': ['https://en.wikipedia.org/wiki/' + urllib.parse.quote(t.replace(' ', '_')) for t in titles]}
        if service == 'wiby':
            r = self._get('https://wiby.me/?q=' + urllib.parse.quote(query), 'search', f'search:wiby:{query}')
            if not r.get('ok'):
                return {'ok': False, 'results': [], 'error': r.get('error')}
            out = [u for u, _ in r['links'] if u.startswith('http') and 'wiby.me' not in urllib.parse.urlparse(u).netloc]
            return {'ok': True, 'results': list(dict.fromkeys(out))[:limit]}
        raise ValueError(service)

    def stats(self):
        if not self.log_path.exists():
            return {'requests': 0}
        rows = [json.loads(l) for l in self.log_path.read_text(encoding='utf-8').splitlines()]
        return {'requests': len(rows), 'ok': sum(r.get('ok', False) for r in rows),
                'refused': sum(str(r.get('error', '')).startswith('refused') for r in rows),
                'failed': sum((not r.get('ok')) and not str(r.get('error', '')).startswith('refused') for r in rows),
                'bytes': sum(r.get('bytes', 0) for r in rows),
                'hosts': len({urllib.parse.urlparse(r['url']).netloc for r in rows})}
