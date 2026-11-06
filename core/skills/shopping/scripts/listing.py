#!/usr/bin/env python3
"""Read product prices from PUBLIC store pages (stdlib only, plain python3).

Read-only: sends no cookies, logins or personal data, at low volume (at least
5 s between requests to one host). One desktop-Chrome User-Agent is used.

Subcommands:
  page      extract products/prices from URLs or a saved HTML file (JSON Lines)
  shopify   read /products/<handle>.js of a Shopify product URL
  kaspi     list Kaspi.kz merchant offers for a product id (undocumented API)
  rate      National Bank of Kazakhstan exchange rates (KZT per unit)
  selftest  offline assertions against embedded fixtures
"""
import argparse, datetime, gzip, html as htmllib, json, re, sys, time
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
LANG = "ru-KZ,ru;q=0.9,en;q=0.8"
TIMEOUT, MAX_BYTES, MIN_GAP = 20, 6 * 1024 * 1024, 5.0
BLOCK_STATUS = {403, 429, 498, 503}
_last = {}  # host -> time of last request


class Blocked(Exception):
    pass


# Read-only guard: never request, or follow a redirect to, a cart, checkout,
# login, account, order or payment page. A GET to some cart URLs (e.g.
# WooCommerce ?add-to-cart=) changes state, and account pages show personal data.
FORBIDDEN_SEGMENTS = {
    "cart", "basket", "checkout", "login", "logon", "signin", "sign-in", "signup",
    "sign-up", "register", "auth", "account", "accounts", "my-account", "myaccount",
    "profile", "order", "orders", "wishlist", "payment", "pay",
}


def forbidden(url):
    p = urllib.parse.urlsplit(url)
    segs = {s.lower() for s in p.path.split("/") if s}
    q = p.query.lower()
    return bool(segs & FORBIDDEN_SEGMENTS) or "add-to-cart" in q or "add_to_cart" in q


class _GuardRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if forbidden(newurl):
            raise Blocked("refused redirect to cart/account/login page " + urllib.parse.urlsplit(newurl).path)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_GuardRedirects)


def http(url, data=None, headers=None):
    """Return (status, body_text, final_url). Raises Blocked on 429 we can't retry
    and on any cart/checkout/login/account URL, given or redirected to."""
    if forbidden(url):
        raise Blocked("refused cart/account/login URL " + urllib.parse.urlsplit(url).path)
    host = urllib.parse.urlsplit(url).netloc
    h = {"User-Agent": UA, "Accept-Language": LANG, "Accept-Encoding": "gzip"}
    h.update(headers or {})
    for attempt in (0, 1):
        wait = MIN_GAP - (time.time() - _last.get(host, 0))
        if wait > 0 and host in _last:
            time.sleep(wait)
        _last[host] = time.time()
        req = urllib.request.Request(url, data=data, headers=h)
        try:
            r = _opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            r = e
            if e.code == 429 and attempt == 0:
                ra = e.headers.get("Retry-After", "")
                if ra.isdigit() and int(ra) <= 120:
                    time.sleep(int(ra))
                    continue
        except urllib.error.URLError as e:
            if "redirect" in str(e).lower():
                raise Blocked("redirect loop")
            raise
        raw = r.read(MAX_BYTES)
        if r.headers.get("Content-Encoding") == "gzip":
            try:
                raw = gzip.decompress(raw)
            except (OSError, EOFError):
                pass
        enc = r.headers.get_content_charset() or "utf-8"
        return r.status if hasattr(r, "status") else r.code, raw.decode(enc, "replace"), r.geturl()
    raise Blocked("429 rate limited")


def num(v):
    """Normalise a price-like value to int/float, or None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v).strip().replace(",", ".").replace("\xa0", "").replace(" ", ""))
    except InvalidOperation:
        return None
    f = float(d)
    return int(f) if f == int(f) else f


def detect_block(status, body, final_url, loop=False):
    if loop:
        return "redirect loop"
    if status in BLOCK_STATUS:
        return "HTTP %d" % status
    if "_____tmd_____/punish" in final_url or "_____tmd_____/punish" in body[:20000]:
        return "AliExpress punish page"
    if len(body) < 20000:
        low = body.lower()
        for m in ("just a moment...", "cf-chl", "x5secdata", "captcha"):
            if m in low:
                return "marker: " + m
    return None


# ---------- product extraction ----------
def _brand(b):
    if isinstance(b, dict):
        b = b.get("name")
    return str(b) if b else None


def _s(v):
    return None if v is None or v == "" else str(v)


def _nodes(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _nodes(x)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _nodes(obj["@graph"])
        yield obj


def _is_product(n):
    t = n.get("@type")
    return "Product" in (t if isinstance(t, list) else [t])


def _product(n, base_url):
    offers = n.get("offers") or {}
    offers = offers if isinstance(offers, list) else [offers]
    offers = [o for o in offers if isinstance(o, dict)]
    o = offers[0] if offers else {}
    if "lowPrice" in o:
        price, high = num(o.get("lowPrice")), num(o.get("highPrice"))
    else:
        price, high = num(o.get("price")), None
        if price is None and isinstance(o.get("priceSpecification"), dict):
            price = num(o["priceSpecification"].get("price"))
    av = _s(o.get("availability"))
    if av:
        av = re.sub(r"^https?://schema\.org/", "", av)
    return {"title": _s(n.get("name")), "price": price, "price_high": high,
            "currency": _s(o.get("priceCurrency")), "availability": av,
            "sku": _s(n.get("sku")), "mpn": _s(n.get("mpn")),
            "gtin": _s(n.get("gtin") or n.get("gtin13") or n.get("gtin12") or n.get("gtin14") or n.get("gtin8")),
            "brand": _brand(n.get("brand")),
            "url": _s(n.get("url") or o.get("url")) or base_url}


def _meta(page, prop):
    for m in re.finditer(r"<meta\b[^>]*>", page, re.I):
        tag = m.group(0)
        if re.search(r"""(?:property|name)\s*=\s*["']%s["']""" % re.escape(prop), tag, re.I):
            c = re.search(r"""content\s*=\s*["']([^"']*)["']""", tag, re.I)
            if c:
                return htmllib.unescape(c.group(1))
    return None


def extract(page, url=None):
    """Return (source, products) for an HTML page."""
    prods = []
    pat = r"<script\b[^>]*type\s*=\s*[\"']?application/ld\+json[\"']?[^>]*>(.*?)</script>"
    for m in re.finditer(pat, page, re.I | re.S):
        try:
            data = json.loads(htmllib.unescape(m.group(1)).strip())
        except ValueError:
            continue
        prods += [_product(n, url) for n in _nodes(data) if _is_product(n)]
    if prods:
        return "jsonld", prods
    amount = _meta(page, "product:price:amount")
    if amount and num(amount) is not None:
        return "og", [{"title": _meta(page, "og:title"), "price": num(amount), "price_high": None,
                       "currency": _meta(page, "product:price:currency"), "availability": None,
                       "sku": None, "mpn": None, "gtin": None, "brand": None, "url": url}]
    m = re.search(r'"price"\s*:\s*"?([0-9][0-9.,]*)"?.{0,300}?"currency(?:Code)?"\s*:\s*"([A-Z]{3})"', page, re.S)
    if m and num(m.group(1)) is not None:
        return "inline", [{"title": _meta(page, "og:title"), "price": num(m.group(1)), "price_high": None,
                           "currency": m.group(2), "availability": None, "sku": None, "mpn": None,
                           "gtin": None, "brand": None, "url": url}]
    return "none", []


def page_record(url, status, body, final_url, loop=False):
    reason = detect_block(status, body, final_url, loop)
    src, prods = ("none", []) if reason else extract(body, url)
    return {"url": url, "final_url": final_url, "status": status, "blocked": bool(reason),
            "block_reason": reason, "source": src, "products": prods}


def cmd_page(a):
    if a.file:
        body = open(a.file, encoding="utf-8", errors="replace").read()
        u = a.url or a.file
        print(json.dumps(page_record(u, 200, body, u), ensure_ascii=False))
        return
    if not a.urls:
        die("page: give URL(s) or --file PATH")
    for u in a.urls:
        try:
            st, body, fu = http(u)
            rec = page_record(u, st, body, fu)
        except Blocked as e:
            rec = {"url": u, "final_url": u, "status": 0, "blocked": True, "block_reason": str(e),
                   "source": "none", "products": []}
        except Exception as e:
            print("error: %s: %s" % (u, e), file=sys.stderr)
            rec = {"url": u, "final_url": u, "status": 0, "blocked": False, "block_reason": None,
                   "source": "none", "products": []}
        print(json.dumps(rec, ensure_ascii=False))


# ---------- shopify ----------
def shopify_summary(url, d):
    vs = [{"title": v.get("title"), "price": num(Decimal(str(v.get("price", 0))) / 100),
           "available": bool(v.get("available")), "sku": _s(v.get("sku"))} for v in d.get("variants", [])]
    return {"url": url, "title": d.get("title"), "in_stock": any(v["available"] for v in vs), "variants": vs}


def cmd_shopify(a):
    p = urllib.parse.urlsplit(a.url)
    m = re.search(r"/products/([^/?#]+)", p.path)
    if not m:
        die("shopify: URL has no /products/<handle>")
    js = "%s://%s/products/%s.js" % (p.scheme, p.netloc, m.group(1))
    try:
        st, body, _ = http(js)
        if st != 200:
            print(json.dumps({"url": a.url, "blocked": st in BLOCK_STATUS, "status": st}))
            return
        print(json.dumps(shopify_summary(a.url, json.loads(body)), ensure_ascii=False))
    except Blocked as e:
        print(json.dumps({"url": a.url, "blocked": True, "block_reason": str(e)}))
    except Exception as e:
        print("error: %s" % e, file=sys.stderr)


# ---------- kaspi ----------
def kaspi_summary(pid, city, d):
    offers = d.get("offers") or []
    out = [{"merchant": o.get("merchantName"), "price": num(o.get("price")),
            "delivery": o.get("delivery") if o.get("delivery") is not None else o.get("deliveryDuration"),
            "rating": o.get("merchantRating"), "reviews": o.get("merchantReviewsQuantity")} for o in offers]
    return {"id": str(pid), "city": str(city), "offers": out, "total": d.get("total", len(out))}


def cmd_kaspi(a):
    m = re.search(r"-(\d+)/?(?:[?#].*)?$", a.target) if "/" in a.target else re.fullmatch(r"(\d+)", a.target)
    if not m:
        die("kaspi: cannot find a numeric product id in %r" % a.target)
    pid = m.group(1)
    body = json.dumps({"cityId": a.city, "id": pid, "limit": a.limit, "page": 0, "sort": True}).encode()
    try:
        st, text, _ = http("https://kaspi.kz/yml/offer-view/offers/" + pid, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "Referer": "https://kaspi.kz/shop/p/-%s/" % pid})
        if st != 200:
            print(json.dumps({"id": pid, "city": a.city, "blocked": st in BLOCK_STATUS, "status": st, "offers": [], "total": 0}))
            return
        print(json.dumps(kaspi_summary(pid, a.city, json.loads(text)), ensure_ascii=False))
    except Blocked as e:
        print(json.dumps({"id": pid, "city": a.city, "blocked": True, "block_reason": str(e), "offers": [], "total": 0}))
    except Exception as e:
        print("error: %s" % e, file=sys.stderr)


# ---------- NBK rates ----------
def parse_rates(xml_text, codes):
    want, out = {c.upper() for c in codes}, {}
    for it in ET.fromstring(xml_text).iter("item"):
        t = (it.findtext("title") or "").strip()
        if t in want:
            out[t] = num(Decimal(it.findtext("description").strip()) / Decimal(it.findtext("quant") or "1"))
    return out


def cmd_rate(a):
    date = a.date or datetime.date.today().strftime("%d.%m.%Y")
    try:
        st, text, _ = http("https://www.nationalbank.kz/rss/get_rates.cfm?fdate=" + date)
        print(json.dumps({"date": date, "rates": parse_rates(text.encode(), a.codes)}))
    except Exception as e:
        print("error: %s" % e, file=sys.stderr)


# ---------- selftest ----------
def ld(*objs):
    return "<html>" + "".join('<script type="application/ld+json">%s</script>' % json.dumps(o) for o in objs) + "</html>"


def selftest():
    fails = 0

    def check(name, fn):
        nonlocal fails
        try:
            fn()
            print("PASS", name)
        except Exception as e:
            fails += 1
            print("FAIL", name, repr(e))

    def t_graph():
        s, p = extract(ld({"@graph": [{"@type": "BreadcrumbList"}, {"@type": ["Product"], "name": "A", "brand": {"name": "B"},
            "offers": [{"price": 10, "priceCurrency": "USD"}, {"price": 11}]}]}))
        assert s == "jsonld" and len(p) == 1 and p[0]["price"] == 10 and p[0]["brand"] == "B"

    def t_agg():
        _, p = extract(ld({"@type": "Product", "name": "A", "offers": {"@type": "AggregateOffer", "lowPrice": "5", "highPrice": "9.5", "priceCurrency": "KZT"}}))
        assert p[0]["price"] == 5 and p[0]["price_high"] == 9.5

    def t_str():
        _, p = extract(ld({"@type": "Product", "name": "A", "offers": {"price": "54.9500", "availability": "https://schema.org/InStock"}}))
        assert p[0]["price"] == 54.95 and isinstance(p[0]["price"], float) and p[0]["availability"] == "InStock"

    def t_sku():
        _, p = extract(ld({"@type": "Product", "name": "A", "sku": 12345}))
        assert p[0]["sku"] == "12345"

    def t_bad():
        h = '<script type="application/ld+json">{oops</script>' + ld({"@type": "Product", "name": "A"})
        assert len(extract(h)[1]) == 1

    def t_search():
        assert len(extract(ld(*[{"@type": "Product", "name": "P%d" % i, "offers": {"price": i}} for i in range(3)]))[1]) == 3

    def t_og():
        s, p = extract('<meta property="og:title" content="T"><meta property="product:price:amount" content="19.99">'
                       '<meta property="product:price:currency" content="EUR">')
        assert s == "og" and p[0]["price"] == 19.99 and p[0]["currency"] == "EUR" and p[0]["title"] == "T"

    def t_inline():
        s, p = extract('<script>var x={"price":"12.50","foo":1,"currency":"USD"}</script>')
        assert s == "inline" and p[0]["price"] == 12.5 and p[0]["currency"] == "USD"

    def t_cf():
        assert detect_block(200, "<title>Just a moment...</title>", "https://x.com/")
        assert detect_block(403, "", "https://x.com/") == "HTTP 403"

    def t_ali():
        assert detect_block(200, "<html></html>", "https://aliexpress.com/_____tmd_____/punish?x5secdata=1")

    def t_shop():
        r = shopify_summary("u", {"title": "T", "variants": [{"title": "a", "price": 1999, "available": False, "sku": "s1"},
                                                              {"title": "b", "price": 2050, "available": True, "sku": "s2"}]})
        assert r["in_stock"] and r["variants"][0]["price"] == 19.99 and r["variants"][1]["price"] == 20.5

    def t_nbk():
        x = b"<rates><item><title>USD</title><description>451.87</description><quant>1</quant></item>" \
            b"<item><title>RUB</title><description>550</description><quant>100</quant></item></rates>"
        r = parse_rates(x, ["USD", "RUB"])
        assert r["USD"] == 451.87 and r["RUB"] == 5.5

    def t_kaspi():
        r = kaspi_summary(1, 750000000, {"total": 1, "offers": [{"merchantName": "M", "price": 1000, "delivery": "x",
                                                                 "merchantRating": 4.9, "merchantReviewsQuantity": 7}]})
        assert r["offers"][0] == {"merchant": "M", "price": 1000, "delivery": "x", "rating": 4.9, "reviews": 7} and r["total"] == 1

    def t_guard():
        for u in ["https://shop.example/cart", "https://shop.example/checkout/step1", "https://kaspi.kz/shop/login?x=1",
                  "https://s.example/my-account/orders", "https://w.example/p/x?add-to-cart=12"]:
            assert forbidden(u), u
        for u in ["https://kaspi.kz/yml/offer-view/offers/113137790", "https://satu.kz/p123-cartridge.html",
                  "https://www.pololu.com/product/2135", "https://x.myshopify.com/products/cart-wheel.js",
                  "https://www.nationalbank.kz/rss/get_rates.cfm?fdate=06.11.2026"]:
            assert not forbidden(u), u
        try:
            http("https://shop.example/cart")
            raise AssertionError("cart URL was not refused")
        except Blocked:
            pass

    for n, f in [("read-only url guard", t_guard), ("jsonld graph+breadcrumb+list offers", t_graph), ("aggregate offer", t_agg), ("string price+availability url", t_str),
                 ("numeric sku", t_sku), ("invalid json block skipped", t_bad), ("search page 3 products", t_search),
                 ("og fallback", t_og), ("inline fallback", t_inline), ("cloudflare block", t_cf),
                 ("aliexpress punish", t_ali), ("shopify cents", t_shop), ("nbk quant 100", t_nbk), ("kaspi offers", t_kaspi)]:
        check(n, f)
    sys.exit(1 if fails else 0)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("page", help="extract products from URLs or a saved file (JSON Lines)")
    p.add_argument("urls", nargs="*", metavar="URL")
    p.add_argument("--file", help="parse a saved HTML file instead of fetching")
    p.add_argument("--url", help="original URL of the saved file")
    p.set_defaults(fn=cmd_page)
    p = sub.add_parser("shopify", help="Shopify product via /products/<handle>.js (untested against live stores)",
                       description="Reads <origin>/products/<handle>.js. NOTE: this method is untested against live stores.")
    p.add_argument("url")
    p.set_defaults(fn=cmd_shopify)
    p = sub.add_parser("kaspi", help="Kaspi.kz offers for a product (undocumented endpoint)",
                       description="POSTs to kaspi.kz/yml/offer-view/offers/<id>. This endpoint is undocumented and can change without notice.")
    p.add_argument("target", metavar="ID_OR_URL")
    p.add_argument("--city", required=True, help="Kaspi city id, e.g. 750000000 (Almaty)")
    p.add_argument("--limit", type=int, default=64)
    p.set_defaults(fn=cmd_kaspi)
    p = sub.add_parser("rate", help="National Bank of Kazakhstan rates, KZT per 1 unit")
    p.add_argument("codes", nargs="+", metavar="CODE")
    p.add_argument("--date", help="DD.MM.YYYY (default today)")
    p.set_defaults(fn=cmd_rate)
    p = sub.add_parser("selftest", help="offline fixture assertions")
    p.set_defaults(fn=lambda a: selftest())
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
