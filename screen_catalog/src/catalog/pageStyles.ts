// Shared page chrome for the two catalog pages that are NOT the app itself — the index and the framed viewer.
// index.css is written for the app: it pins #root to a 1200x800 stage, sets body{overflow:hidden} and paints the
// Dell background. Those are right for a screen and wrong for a list or a viewer bar, so this undoes them, but
// only under the catalog-page class that main.tsx adds to <html> for these two pages. A scenario rendered
// directly (automation, or inside the viewer's iframe) never gets the class, so the app's own layout is exactly
// what ships.
//
// Two details that matter on a very large viewport (a 4K monitor, or a browser zoomed far out, where the CSS
// viewport is thousands of px wide):
//  • the root font-size grows with the window (16px up to ~1920px wide, then proportionally), and both pages size
//    everything in rem, so they stay readable instead of shrinking to a thin strip;
//  • body must NOT be its own scroll container — with overflow set on both html and body, body scrolls nothing
//    and `position: sticky` inside it (the index sidebar) never sticks, so body is left visible and the viewport
//    scrolls.
const OVERRIDES = `
html.catalog-page { font-size: clamp(16px, 0.8333vw, 48px); }
html.catalog-page, html.catalog-page body { height: auto; min-height: 100%; }
html.catalog-page body { overflow: visible !important; }
html.catalog-page body::before, html.catalog-page body::after, html.catalog-page .bg-layer { display: none !important; }
html.catalog-page #root { position: static; width: auto; height: auto; display: block; }
`

export function enterCatalogPage(): void {
  document.documentElement.classList.add('catalog-page')
  const style = document.createElement('style')
  style.textContent = OVERRIDES
  document.head.appendChild(style)
}
