# Kazakhstan rules for buying from abroad

Checked 2026-11-06. Sources are mostly news sites, and some conflict. Re-check from an official source (kgd.gov.kz, eec.eaeunion.org) when a foreign order's total nears the duty-free limit, or after 2027-01-01. Not legal advice: state the rule, its source and date, and say it's an estimate.

## Customs on personal imports

Customs apply only to parcels from outside the EAEU. Goods bought on Kaspi, Wildberries or Ozon that are already inside the EAEU are not affected.

- **Current regime:** duty-free up to EUR 200 and 31 kg **per parcel**. Above that, a single 15% payment applies to the value over EUR 200, with a minimum of EUR 2 per kg over the weight limit. Source: https://kz.kursiv.media/2026-06-05/lngr-foreign-marketplaces-new-rules/ (2026-06-05, citing the customs committee).
- **Next regime** (EAEU "e-commerce goods", protocol of 2023-12-25): the EUR 200 limit stays and the 31 kg limit is dropped. Above the limit come 5% duty plus VAT, which sources give as 12% or 16%; whether it applies to the excess or the whole value is unclear. The operator files the declaration, not the buyer. Start date: moved from 2026-07-01 to **2027-01-01** per KGD, reported by https://nalogikz.kz/docs/internet-pokupki-iz-za-rubezha-tamozhennye-pravila-zarabotajut-s-2027-goda.html (2026-08-31). Not confirmed as final.
- **Estimate:** convert the parcel value (item + shipping) to EUR with the NBK rate. If it's over EUR 200, apply the regime in force on the expected arrival date and show the working.
- **Never** suggest splitting an order or misstating value to stay under the limit.

## Lithium batteries (LiPo, Li-ion packs, power banks)

- Lithium cells are generally refused for air mail and go by land or sea only (https://habr.com/ru/companies/pochtoy/articles/397453, 2018, may be stale). Some forwarders ban them outright, e.g. BPD Express.
- No Kazakhstan-specific Kazpost or Cainiao rule was found.
- **Buy packs locally.** Satu.kz lists 4S and 6S FPV LiPo packs [verified 2026-11-06]. A foreign listing that "ships" a battery often arrives without it or very late; flag that risk.
- Flying with packs: Air Astana and FlyArystan allow spare lithium batteries in carry-on only, nothing over 160 Wh (https://en.tengrinews.kz/kazakhstan_news/banned-items-new-important-rule-announced-at-kazakhstan-airports-269197, rule from 2025-03-13).

## Drones

- UAVs with a maximum take-off mass of 0.25 kg or more must be registered through eGov (Ministry of Transport). Sources: https://kz.kursiv.media/2025-05-02/lgtn-dron-in-kz/ and https://youth.kz/article/kak-zaregistrirovat-dron-v-kazahstane-i-zachem-eto-delat-fBehzuc78dPaFQ87qQRn
- When the purchase is a complete drone at or above 250 g, mention registration in one line.
- No import permit rule was found for parts (flight controllers, ESCs, motors). Seller-side export restrictions are in `stores.md`.

## Currency

- National Bank of Kazakhstan feed: `https://www.nationalbank.kz/rss/get_rates.cfm?fdate=DD.MM.YYYY` (XML; `<description>` is KZT per `<quant>` units). `listing.py rate USD EUR CNY RUB` reads it. On 2026-11-06: USD 451.87, EUR 507.31, CNY 67.77, RUB 5.53.
- Card and marketplace rates differ from the NBK rate. Say the landed cost uses the NBK rate.

## Parcel forwarders

Only for ordinary goods a store simply doesn't ship to Kazakhstan. Never for restricted items, never for a seller whose terms forbid reshipping (Holybro), never for lithium batteries. The status and prices of each forwarder are unverified: check current reviews before suggesting one.

- US: Pochtoy (US address, buy-for-you, consolidation), Globalshopaholics.
- EU: BPD Express (Germany; lithium prohibited).
- China: cargo agents for Taobao, Pinduoduo and Temu listed on 2GIS (e.g. NEOCARGO, 878 Express Cargo, Jana post).
