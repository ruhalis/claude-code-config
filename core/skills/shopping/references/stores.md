# Stores

What each store is good for, how to read it, and what is known about shipping to Kazakhstan. Checked 2026-11-06 from a Kazakh IP unless noted; [v] = verified directly, [s] = second-hand. Store behaviour changes: when a read fails or a policy differs, note it with the date in `~/.claude/shopping/profile.md`, and update this file when the change holds.

Read methods: **page** = `listing.py page <url>` (JSON-LD or OpenGraph or inline JSON); **kaspi** = `listing.py kaspi`; **shopify** = `listing.py shopify` (untested live); **browser** = read-only in Chrome; **API** = the kicad-happy distributor skill.

## Kazakh stores

| Store | Good for | Read | Notes |
|---|---|---|---|
| Kaspi.kz | General goods, electronics; many merchants per product | **kaspi** with the product id and city id [v] | Product and search pages carry no price in static HTML. Find product ids with WebSearch (`site:kaspi.kz/shop/p <query>`) or the browser. The offers endpoint is undocumented: if it breaks, read the product page in the browser. Prices and delivery depend on the city. |
| Satu.kz | Small sellers: modules, components, LiPo packs, tools, consumables | **page** on search and product pages, JSON-LD in KZT [v] | The most machine-readable Kazakh source; a search page holds about 10 products. Nationwide delivery depends on the seller. |
| Technodom | Electronics, appliances, tools | **page** on product pages (JSON-LD) and catalog pages (prices in HTML) [v] | The search page is client-rendered: use catalog pages or the browser. Prices and stock vary by city. |
| Wildberries KZ | General goods | **browser** only: curl gets 498/403 [v] | Goods are inside the EAEU, so no customs. |
| Ozon KZ | General goods | **browser** only: bot-challenge redirect [v] | Goods are inside the EAEU, so no customs. |
| OLX.kz | Used goods, local sellers | **browser** only: CloudFront 403 [v] | Used items: flag condition and seller risk. |
| Halyk Market, Sulpak, Mechta, Alser | General goods, electronics | Untested: try **page**, then the browser | Record what works in the profile. |

## China marketplaces

| Store | Good for | Read | Notes |
|---|---|---|---|
| AliExpress | Almost anything, FPV parts, tools | **browser** only: curl gets a bot-wall redirect [v] | A Kazakh IP is redirected to aliexpress.ru [v]. Clones are common: check the store's rating, sales and age, and compare specs with the manufacturer. |
| Banggood | RC/FPV, tools, gadgets | **page**: USD price in inline JSON, rouble price in og:description [v] | Kazakhstan is served via ru.banggood.com [v]. |
| Temu | Cheap general goods | Untested | Operating in Kazakhstan since 2024 [s]. |

## Foreign specialist stores

| Store | Good for | Read | Shipping to Kazakhstan |
|---|---|---|---|
| Pololu | Robotics: motors, drivers, sensors | **page**, JSON-LD in USD [v] | Not stated in its shipping doc [v]. |
| Adafruit | Electronics, sensors, dev boards | **page**, JSON-LD in USD [v] | Listed, but some products can't go to some listed countries [v]. |
| SparkFun | Electronics, sensors | Untested; try **page** | Export page doesn't mention KZ; restrictions are per product [v]. |
| DigiKey, Mouser, LCSC, element14 | Components with an MPN | **API** via kicad-happy | DigiKey reportedly lists KZ [s]; LCSC ships by DHL/FedEx [s]; Mouser's site blocks automation [v]. |
| RaceDayQuads | FPV | Shopify; **shopify** untested. HTTP 429 after about 6 requests [v] | Unknown. It publishes agent rules at `/agents.md` (and a UCP endpoint); read those before reading the store. |
| Pyrodrone | FPV | Shopify; **shopify** untested; 429s [v] | International by DHL Express; no country list [v]. |
| Holybro (direct) | Flight controllers, GPS, telemetry, frames | Shopify; 429s [v] | KZ is not on its embargo list, but its code of conduct forbids routing via intermediaries, so no forwarders [v]. Paused overseas export in June 2025, no resumption found [v/s]. Ships from China, DAP: buyer pays duties [v]. |
| GetFPV | FPV | **browser** only: Cloudflare challenge [v] | Unconfirmed. |
| iFlight (iflight-rc.eu / .com) | FPV motors, ESCs, frames | Untested; .com unreachable from KZ on the test day | The EU policy page has no country list [v]. |
| T-Motor (store.tmotor.com) | Motors, ESCs, props | Untested | No KZ statement found. |
| Amazon.com | General goods | **page** gets HTML without JSON-LD; price not confirmed, so use the browser | Shows "Deliver to Kazakhstan"; some items "cannot be shipped" [v]. Per item. |

## Export restrictions

The US export agency (BIS) lists Kazakhstan as a transshipment-risk destination [s]. Some US and EU sellers refuse, or ask end-use questions about, drone parts and some electronics. Answers must be truthful, and a refusal is final. No store policy found names Kazakhstan outright.

## Spec sources (FPV and robotics)

- https://docs.holybro.com/ : Holybro manuals and specs.
- https://uav-en.tmotor.com/ : T-Motor UAV motors and ESCs.
- https://github.com/am32-firmware/AM32 and https://am32.ca/ : AM32 ESC targets.
- https://github.com/bird-sanctuary/bluejay : Bluejay ESC targets.
- https://github.com/betaflight/unified-targets : flight-controller board configs.
- https://iflight-rc.eu : iFlight spec pages.
