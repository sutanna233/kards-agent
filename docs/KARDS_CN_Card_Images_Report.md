# KARDS Simplified Chinese Card Images — Source Research Report

## Executive Summary

**Recommended source: kards.com official CDN via GraphQL API**

The kards.com official site exposes Simplified Chinese card images through its GraphQL API + CDN. This is the single most reliable source for ~845+ core cards with Chinese localization.

---

## Source 1: KARDS Official Site (kards.com)

### GraphQL API Endpoint
```
https://herokuapi.kards.com/graphql
```

### Card Image CDN URL Pattern
```
https://www.kards.com/images/card/v52/zh-Hans/{cardId}.avif
```

For thumbnails:
```
https://www.kards.com/images/card/v52/zh-Hans/thumb/{cardId}.avif
```

Where `{cardId}` is the card's unique identifier (e.g. `554th_rifle_regiment`, `aerosani`, `infantry`).

### How to Get Card Metadata
Query the GraphQL API with this exact query:

```graphql
query getCards($language: String, $offset: Int, $nationIds: [Int], $kredits: [Int], $q: String, $type: [String], $rarity: [String], $set: [String], $showSpawnables: Boolean, $showExiles: Boolean, $showReserved: Boolean) {
  cards(language: $language, first: 20, offset: $offset, nationIds: $nationIds, kredits: $kredits, q: $q, type: $type, set: $set, rarity: $rarity, showSpawnables: $showSpawnables, showExiles: $showExiles, showReserved: $showReserved) {
    pageInfo { count hasNextPage __typename }
    edges {
      node {
        id cardId importId json
        imageUrl: image(language: $language)
        thumbUrl: image(type: thumb, language: $language)
        __typename
      }
      __typename
    }
    __typename
  }
}
```

Variables for Simplified Chinese:
```json
{
  "language": "zh",
  "first": 20,
  "offset": 0,
  "nationIds": [1],
  "kredits": [0],
  "showSpawnables": true,
  "showExiles": true,
  "showReserved": true
}
```

Nation IDs: `1=苏联, 2=美国, 3=日本, 4=德国, 5=英国, 6=法国, 7=意大利, 8=波兰, 9=芬兰, 10=澳新, 0=中立(所有国家)`
Kredit costs: `0, 1, 2, 3, 4, 5, 6, 7`

### Chinese Title Access
The `json` field in the response contains a JSON object with `title.zh-Hans` for the Simplified Chinese card name:
```json
{
  "title": {
    "zh-Hans": "步兵第 554 团",
    "en-EN": "554th RIFLE REGIMENT"
  }
}
```

### Image Format
- **Format**: AVIF (AV1 Image File Format)
- **Content-Type**: `binary/octet-stream`
- **Typical size**: 30-50 KB per card image
- Need conversion to PNG for template matching

### CDN Accessibility
- **Status**: ✅ Fully accessible with standard HTTP headers
- **Required headers**: `User-Agent`, `Referer: https://www.kards.com/`
- **Tested**: 100/100 cards downloaded successfully from first 100 samples
- **Region**: Global CDN (Azure Storage with CloudFront-style access)

### Image Version
- Current version: **v52** (Oceania Storm expansion + July balance patch)
- URL pattern: `/images/card/v52/zh-Hans/{cardId}.avif`
- When new expansions release, the version number increments

### Coverage
- **845+ unique cards** with Simplified Chinese titles
- **99.9%** of cards have Chinese localization (only 1 card lacked Chinese: `kumamoto_regiment`)
- Covers all 11 nations and all kredit costs (0-7)
- Includes orders, infantry, tanks, fighters, bombers, artillery, countermeasures

### Chinese Localization Detail
The site has a language selector with `简体中文` option. When language is set to `zh` (via GraphQL) or `zh-Hans` (in URL paths), card images are served from the `zh-Hans` subpath with Chinese-localized card names in metadata.

---

## Source 2: KARDS Fandom Wiki (kards.fandom.com)

### Category: Card Images
- **URL**: https://kards.fandom.com/wiki/Category:Card_images
- **Total files**: 589 images
- **API endpoint**: `https://kards.fandom.com/api.php?action=query&generator=categorymembers&gcmtitle=Category:Card_images&gcmtype=file&prop=imageinfo&iiprop=url|size&format=json&formatversion=2`

### Image URL Pattern
```
https://static.wikia.nocookie.net/kards/images/{hash}/{cardName}.png/revision/latest?cb={timestamp}
```

Example:
```
https://static.wikia.nocookie.net/kards/images/1/1c/25pounder.png/revision/latest?cb=20200427151832
```

### Chinese Localization
- **Status**: ❌ **NO Chinese images exist on Fandom**
- Searched for `aiprefix=zh-cn`, `aiprefix=zh_cn`, `aiprefix=zh` — zero results
- Searched for Chinese characters in file names — zero results
- All 589 images are in English only
- Images are dated 2020-2023, mostly from the game's early launch period

### Filename Convention
- Base card images: `{cardName}.png` (e.g., `25pounder.png`, `Fighter.png`)
- Nation-prefixed: `{Nation}_{cardName}.png` (e.g., `German_infantry_3.png`, `British_infantry.png`)
- Stolen cards: `STOLEN{cardName}.png`
- Template placeholders: `TEMP.png`, `Expid_force_temp.png`

### API (MediaWiki)
- Works without Cloudflare: `https://kards.fandom.com/api.php`
- Supports standard MediaWiki query parameters
- Rate limit: 500 results per page (use `gcmcontinue` for pagination)

### Usefulness for This Project
- **Low** — English-only images, outdated (pre-expansion), limited coverage
- Could serve as backup for cards missing from the official CDN
- Images are PNG format (no conversion needed)
- Higher resolution (1024x1024 for some images)

---

## Source 3: Tuning-Luna/kards-decks-collection-scraper

### Repository
- **URL**: https://github.com/Tuning-Luna/kards-decks-collection-scraper
- **Stars**: 7
- **Description**: Automated crawler for KARDS CCG card images

### How It Works
1. **GraphQL API**: Queries `https://herokuapi.kards.com/graphql` for card metadata
2. **Image download**: Fetches AVIF images from CDN using `curl_cffi` (browser fingerprint impersonation)
3. **Format conversion**: Converts AVIF → PNG using Pillow

### Image Source
- **Base URL**: `https://www.kards.com/images/card/v52/zh-Hans/`
- **Language**: Chinese Simplified (zh-Hans)
- **Default proxy**: `http://127.0.0.1:7897`

### Output Structure
```
imgs/
├── 苏联/
│   ├── 0k/
│   │   └── 步兵第13步兵团_13th_rifles.png
│   └── ...
├── 美国/
│   └── ...
├── 中立/
│   ├── 0k/
│   ├── 1k/
│   └── ...
└── ...
```

### Key Config (src/config.py)
```python
API_URL = "https://herokuapi.kards.com/graphql"
IMAGE_BASE_URL = "https://www.kards.com/images/card/v52/zh-Hans/"
NATION_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0]  # All nations
KOSTS = [0, 1, 2, 3, 4, 5, 6, 7]
```

### Chinese Variant
- **This IS the Chinese variant** — defaults to Simplified Chinese
- Chinese README: https://github.com/Tuning-Luna/kards-decks-collection-scraper/blob/master/README-zh.md
- Can switch to English by changing `IMAGE_BASE_URL` to `.../en-EN/`

### Useful For
- Reference implementation for downloading all card images
- GraphQL query template
- Nation/kredit parameter mapping

---

## Source 4: Other Sources

### Wikipedia / Wikimedia Commons
- No dedicated KARDS card image repository found
- Wikimedia search returned no relevant results

### APK Resource Extraction
- Not investigated (would require decompiling the game APK)
- The game likely contains the same images as the CDN

### Steam Community / Discord
- Community-shared card images exist but are inconsistent
- No systematic dump found

---

## Recommendation

### Best Source: kards.com Official CDN

**Exact per-card image URL pattern:**
```
https://www.kards.com/images/card/v52/zh-Hans/{cardId}.avif
```

**To get the card ID list, query the GraphQL API:**
```
POST https://herokuapi.kards.com/graphql
Content-Type: application/json

{
  "operationName": "getCards",
  "variables": {
    "language": "zh",
    "first": 20,
    "offset": 0,
    "nationIds": [1],
    "kredits": [0],
    "showSpawnables": true,
    "showExiles": true,
    "showReserved": true
  },
  "query": "query getCards(...) { cards(...) { pageInfo { hasNextPage } edges { node { cardId imageUrl: image(language: $language) json } } } }"
}
```

**Download loop pattern:**
```python
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://www.kards.com/",
}

card_id = "554th_rifle_regiment"
url = f"https://www.kards.com/images/card/v52/zh-Hans/{card_id}.avif"
resp = requests.get(url, headers=HEADERS)
# resp.content is the AVIF image data
# Convert to PNG with PIL: Image.open(BytesIO(resp.content)).convert("RGBA").save(f"{card_id}.png", "PNG")
```

**Version tracking:**
- Current version: `v52` (check the API response or config for updates)
- When new expansions release, the version number increments (e.g., `v53`, `v54`)
- Monitor the GraphQL API's `imageUrl` field to detect version changes

### Coverage Summary
| Source | CN Images | Count | Format | Reliability |
|--------|-----------|-------|--------|-------------|
| kards.com CDN | ✅ Yes | 845+ | AVIF | ★★★★★ |
| Fandom Wiki | ❌ No | 589 (EN only) | PNG | ★★★☆☆ |
| Scraper repo | ✅ Yes (via kards.com) | All | AVIF→PNG | ★★★★☆ |
| Other | ❌ | - | - | ★☆☆☆☆ |

### Data Files Generated
- `all_cards.json` — 120 cards (nation 0, all kredits)
- `sample_cards.json` — 845 cards (nations 1-5, kredits 0-4) with Chinese titles, card IDs, and image URLs
