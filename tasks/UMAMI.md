# Umami analytics — the snippet, from his dashboard 2026-08-26

Paste this immediately before `</head>` on EVERY html page of the live site
(`mit-commit/commit-website`): publications, home, projects, people, and any
other page present. Verbatim — no inline config, no extra attributes.

```html
<script defer src="https://cloud.umami.is/script.js" data-website-id="0501f709-b527-45af-8727-062721122bb4"></script>
```

Notes for the cutover worker:

- Umami is cookieless, so no consent banner is needed.
- The website ID identifies the site, not a user, and is public by design —
  it ships in the page source of every site that uses Umami. It is not a
  secret and needs no env-var handling.
- Verify after editing: the number of `*.html` files containing
  `data-website-id` must equal the total number of `*.html` files. A page
  missed here is a page that reports nothing, silently.
- Data lands at https://cloud.umami.is under his account. Confirm during the
  live check that the tag is present on each published page.
