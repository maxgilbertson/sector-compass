# How Claude writes the weekly briefing

Every Saturday the GitHub job `briefing.yml` saves `data/briefings/facts/<date>.json` (every number
the briefing may use) and a plain factual draft `data/briefings/<date>.md`. Claude then rewrites the
draft into the finished briefing, following these rules.

## Who it's for

A careful individual investor who is not a finance professional. They use the Sectors and
Countries pages to decide where to look more closely. Write so they understand every sentence
without a glossary.

## Rules

1. **Only use numbers from the facts file.** Never invent, estimate, round differently or
   bring in outside figures, news or events. If the facts don't explain *why* something moved,
   don't guess a cause; describe what happened and, at most, what kind of thing usually drives it
   (for example "gold miners tend to follow the gold price").
2. **Say what every comparison is against.** Sectors are compared with the whole stock market of
   their own region (for example US Technology vs the S&P 500). Countries are compared with all
   world stocks (MSCI ACWI). Never write "their market" or "the market" without naming it.
3. **No jargon without an explanation.** Avoid "pts", "bps", "alpha", "beta", "overweight" (say
   "the data favours holding more"), "momentum" (say "has been doing better"). If a term is
   needed (RSI, P/E), explain it in a few plain words the first time.
4. **Pounds first.** Give returns in pounds where the facts have them, with US dollars or the local
   currency in brackets when useful.
5. **Not advice.** Describe what the data shows. Never tell the reader to buy or sell. The score
   describes past price behaviour; the test on past data found only a possible edge for sectors
   and none for countries, so frame high scores as "worth a closer look", not "buy".
6. **Plain, calm, British English.** Short sentences. No hype, no exclamation marks.

## Structure (about 700 to 1,000 words)

1. Title: `# Weekly briefing: week to <weekEnding written out, e.g. Friday 2 October 2026>`
2. **In brief**: 3 to 5 bullet points a busy reader could stop at.
3. **The big picture**: world stocks and the US market this week (pounds and dollars), the
   economic read and what it means in one or two sentences, and today's conditions for countries.
4. **Sectors**: what scored highest and lowest, the biggest score rises and falls, signal
   changes, and the best and worst weeks. Group related moves (for example several gold-miner
   funds falling together) rather than listing everything.
5. **Countries**: the same, plus notable currency moves and any "cheap and holding up" markets.
6. **Practice portfolios**: how the top-scored and lowest-scored portfolios are doing against
   their markets and world stocks, with a reminder that weeks of results mean very little.
7. **Worth watching next week**: two to four things taken from the facts (for example a market
   whose score is rising fast, a signal that has just changed, next monthly picks).
8. A one-line reminder that this is not investment advice.

The file must start with the line `<!-- author: Claude -->` so the site labels it correctly.
