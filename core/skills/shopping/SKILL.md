---
name: shopping
description: "Personal shopper for Arlan in Kazakhstan: finds, checks and compares anything to buy - FPV/RC and robotics parts, electronics, tools, consumables, general goods - across Kazakh stores (Kaspi, Satu, Technodom, Wildberries, Ozon, OLX), China marketplaces (AliExpress, Banggood, Temu) and foreign specialist stores, and returns a shortlist plus a private Artifact comparison page with landed cost in tenge (price, shipping, customs estimate), stock, delivery, spec check and risks. Read-only: never logs in, adds to cart or buys. Use whenever the user says buy, where to buy, find me, cheapest, compare prices, is X available in Kazakhstan, parts hunting, купить, где купить, сколько стоит, or names a store or a part to source (ESC, motor, LiPo, frame, sensor, dev board, tool). For components with a manufacturer part number it also uses the kicad-happy lcsc/digikey/mouser/element14 skills; not for a PCB BOM or JLCPCB order (kicad-happy bom/jlcpcb)."
---

# Shopping

Arlan lives in Kazakhstan. Find what Arlan wants to buy, check it against what the job needs, and compare the real options delivered to Kazakhstan: a short answer in the terminal and a private Artifact comparison page to reopen later. Arlan buys from the links; this skill never does.

## Hard limits

- **Read-only.** Never log in, create an account, open a cart, checkout, account or order page, add to cart, enter an address or payment details, message a seller, post a review, or click anything that changes state on a store.
- **The browser is Arlan's own logged-in Chrome.** Read product and search pages only. Never copy or record names, addresses, phone numbers, order history or anything else personal that a page shows. Only one agent drives the browser at a time.
- **No getting around sellers or export rules.** If a seller doesn't ship to Kazakhstan, or restricts the item (flight controllers, ESCs, radios and other dual-use electronics can be), say so and drop or flag that option; a refusal is final. A parcel forwarder is only for ordinary goods that a store simply doesn't ship to Kazakhstan, and never for a seller whose terms forbid reshipping (Holybro's do). Never suggest misdeclaring value, contents or destination, or splitting an order to stay under the duty-free limit; compute duty honestly.
- **Low volume.** A few requests per store, at least 5 s apart per host (the script enforces it), back off on HTTP 429. Each store is read by exactly one agent per search.
- **Prices are snapshots.** Every price carries the time it was checked and its source link.

## Profile

`~/.claude/shopping/profile.md` holds: city (Kaspi and Technodom prices and stock depend on it), Kaspi city id, stores Arlan likes or avoids, dated store notes ("GetFPV: Cloudflare, browser only, 2026-11-06"; "<store> refused KZ for <item>, <date>"), and outcomes of past purchases (where, price paid, what arrived, how long it took). Never addresses, cards, phone numbers or account names.

Read it first. If there is no city yet, ask once and save it. Kaspi city ids look like KATO codes (Almaty 750000000, Astana 710000000); confirm the id on first use from a Kaspi offers response before saving it. Update the profile at the end of every search.

## Process

### 1. Pin down the need

What, how many, budget in KZT, deadline, must-haves. For a project part, read the project CLAUDE.md `## Hardware`, `## Boards` and `## Motors` sections and turn them into hard specs (for an ESC: cell count, continuous and burst current, mounting pattern, protocol, firmware, weight, connectors). Ask one `AskUserQuestion` round only if a missing spec would change the answer.

Parts with a manufacturer part number (ICs, passives, connectors, modules with an MPN): load the kicad-happy `lcsc`, `digikey`, `mouser` or `element14` skill for those distributors, and still check the Kazakh stores.

### 2. Choose sources, local first

1. **Kazakh stores**: fastest, no customs, and the only sensible route for LiPo and Li-ion packs.
2. **China marketplaces that serve Kazakhstan** (AliExpress, Banggood, Temu).
3. **Foreign specialist stores** (FPV, robotics, electronics) when the item isn't sold locally or the local price is far off.

`references/stores.md` lists each store: what it's good for, how to read it (script method or browser only), and what is known about shipping to Kazakhstan, with dates. `references/kz-rules.md` holds customs, battery, drone and currency facts with sources and dates.

### 3. Search and read

- Find candidates with WebSearch (`mode: "extended"` for prices and availability), in Russian as well as English: most Kazakh listings are in Russian.
- Read every listing with the script before any browser (see Script). Use the browser, read-only, only for stores marked browser-only or when the script reports `blocked`.
- **Delegate when more than about three stores are involved:** one `general-purpose` agent per store group (Kazakh stores, China marketplaces, foreign stores), launched together, every browser-only store given to the same single agent. Brief below. If a subagent turns out to have no browser tools, it returns those URLs and the main session reads them.

### 4. Verify

- Specs from the manufacturer's page or manual (download PDFs with `curl` and Read them), not the reseller's description. FPV spec sources are in `references/stores.md`.
- Flag likely clones or fakes: price far below the brand's own, no brand, specs or photos that don't match the manufacturer's, new sellers with few sales.
- Seller rating and review count, stock, and whether this item ships to Kazakhstan (Amazon decides per item; specialist stores per policy).

### 5. Landed cost in tenge

Item + shipping + customs estimate for foreign parcels (current rules and their dates in `references/kz-rules.md`; re-check them when a foreign total nears the duty-free limit or the rules' effective date has passed). Convert with the National Bank of Kazakhstan rate from `listing.py rate`, and state the rate and its date. Say which numbers are estimates. Give a delivery-time estimate with its source.

### 6. Present

- **Terminal:** the top 2-3 options, one line each on why, and the page link.
- **Page** (see Comparison page). Then stop; narrow further only if Arlan asks.

### 7. Record

Update the profile's store notes (what worked, what blocked, who refused Kazakhstan). When Arlan later says what was bought and how it went, add it to the outcomes.

## Script

`python3 ~/.claude/skills/shopping/scripts/listing.py <subcommand>`, stdlib only, JSON Lines on stdout. Agents call it by this path.

- `page URL ...` or `page --file saved.html --url URL`: product or search page to products (title, price, currency, availability, SKU, MPN, brand) from schema.org JSON-LD, OpenGraph price tags or inline JSON; reports `blocked` with a reason for bot walls.
- `shopify URL`: variant prices and stock for a Shopify store's product (untested on live stores; they rate-limit hard).
- `kaspi ID_OR_URL --city CITY_ID`: offers from every Kaspi merchant for one product (undocumented endpoint; if it breaks, read the product page in the browser).
- `rate USD EUR CNY RUB`: National Bank of Kazakhstan rates in KZT.
- `selftest`: offline parser checks.

## Delegation brief

For each `general-purpose` agent:

```
Shopping search for <item> delivered to Kazakhstan, city <city>. Hard specs: <list>. Budget: <KZT>.
Your stores: <store list>. Read only these; another agent has the others.
Read-only rules: never log in, open cart/checkout/account/order pages, add to cart, enter any address or payment data, or message a seller. In the browser (if you have it), read product and search pages only and never copy personal data shown on a page. A few requests per store; the script spaces them.
Read listings with `python3 ~/.claude/skills/shopping/scripts/listing.py page <url>` (Kaspi: `kaspi <id> --city <city id>`). Use the browser only for stores the script reports blocked or that are browser-only: <list or "none">. If you have no browser tools, return those URLs unread.
For each candidate return one row: store, seller, title, url, price, currency, shipping cost to KZ (or "unknown"), stock, delivery estimate and its source, spec check against each hard spec (pass/fail/unknown with the source), seller rating and reviews, risks (clone, restriction, used), checked-at time.
Also return: stores that refuse Kazakhstan or the item, with the policy link; stores that blocked you.
Report as a JSON array of rows plus those two lists, under 500 words. No recommendations; the main session compares.
```

## Comparison page

- Before the first page of a search, call the Artifact tool with `action: "quickstart"`, `intent: "other"`, and follow it.
- Build it in the scratchpad directory at `shopping/<slug>.html` when the system prompt lists one; otherwise at `~/.claude/shopping/pages/<slug>.html`.
- Contents: the need and hard specs; the recommendation with its reason; a table (item, store and seller, price in original currency, landed KZT, stock, delivery, spec check, risks, link, checked-at); excluded options with the reason (refuses KZ, fails a spec, likely clone); the exchange rate and date, the customs assumptions, and the sources.
- No product images from stores: the Artifact contract inlines everything except a short list of script CDNs, so hotlinked images break. Text and links only.
- To refresh prices later, re-read the rows and republish the same file. To continue an old search in a new session, find the page with `action: "list"`, read it with `action: "read"`, and build on the saved file it names.

## Language

Answer in the language Arlan asks in (Russian or English); keep product names as the store lists them.
