---
paths:
  - "static/trainer.js"
  - "templates/index.html"
---

# Frontend Rules (trainer.js)

## ZERO State
trainer.js is a thin rendering layer. It has no state.
- No `this.foo = ...` for storing data
- No variables that persist across renders
- No decision logic (no analysing data to decide what to render)

## Render What Server Sends
The server sends complete render data. The client displays it.
- If text needs to be different per clue type, the SERVER decides — not the client
- If a field is empty, render nothing — don't construct alternatives in JS

## Cache Busting
When changing trainer.js, bump version in templates/index.html:
`<script src="/static/trainer.js?v=N"></script>`
