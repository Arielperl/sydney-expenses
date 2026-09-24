# Generation Prompts (v2)

**v2 requires no AI-generated footage or images.** Every frame is motion design rendered from code (`tools/film.html`), using only the project's own assets: the product's Hebrew UI strings and design tokens, IBM Plex Sans Hebrew, `investment-logo.svg` and `sydney-hero-clean.png`. That removes the identity, continuity and "AI look" risks entirely, and keeps all text and UI pixel-accurate.

The v1 AI prompts (studio owner, pilates studio) were retired with the v1 concept, which the client rejected on 2026-09-24. They remain in git history (commit `48fcf70`) if a live-action spot is ever wanted.

## Optional AI use (not needed for delivery)

To add one live-action "insert" to a future variant, keep it to a single abstract product-free shot. Generate it separately and composite it behind the Act A amounts at ≤ 20% opacity:

```
Macro shot, shallow depth of field, a matte-black countertop card-payment terminal on a light-oak counter in a dark room, a soft mint-teal glow (#41D7B2) pulsing behind its small dark glass window, slow push-in, 24 fps, fine film grain, deep green-black background, no text, no logos, no hands, no people.
```
Negative: `text, digits, logos, brand marks, hands, people, keypad numbers, lens flare, neon, oversaturated, CGI look, flicker`
