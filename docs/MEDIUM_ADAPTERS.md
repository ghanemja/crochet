# Medium adapters — turning an image into build instructions for any craft

YarnFlow's long-term shape: **drop in an image, pick a medium, get instructions
to reproduce it** — crochet first, then LEGO, cross-stitch, perler beads, pixel
art… The pipeline in `index.html` is three strictly separated layers; to add a
new medium you only touch layer 2.

```
image ──buildIR()──▶ IR ──adapter.generatePlan()──▶ plan ──renderPlanPreview()──▶ 3D viewer
        (layer 1)         (layer 2: per medium)            (layer 3: shared)
```

## Layer 1 — Intermediate representation (IR)

`buildIR(imageOrCanvas, {res, maxColors})` downsamples the image to the
medium's working resolution and quantizes colours to a constrained palette
(median-cut). It is **medium-independent**: every adapter consumes the same IR.

```js
IR = {
  w, h,            // grid size; h derived from the image aspect
  palette,         // ["#rrggbb", …]  (≤ maxColors)
  grid,            // Int16Array(w*h): palette index per cell, -1 = transparent
}                  // row 0 = TOP row of the image
```

`res` is the number of cells across (stitches, studs, beads…); `maxColors`
models the medium's constraint (yarn colours you own, brick colours available).

## Layer 2 — MediumAdapter interface

Register one object per medium:

```js
registerMediumAdapter({
  id: "perler",                       // unique key
  label: "Perler beads",              // shown in the picker + HUD
  cellAspect: 1,                      // optional: physical height/width of one
                                      // cell — the IR adds rows to compensate
                                      // (crochet sc ≈ 0.74; LEGO stud = 1)
  generatePlan(ir, options) {
    return {
      steps: [{ title: "Row 1", detail: "…" }, …],  // human instructions, build order
      // EITHER: render through the app's existing crochet pattern pipeline
      text:  "Row 1: sc 22\n…",       // + optional paint: {unitIndex: "#hex"}
      // OR: render through the generic viewer
      preview: {
        units: [{                     // one entry per physical piece, build order
          geom: {type:"box", w,h,d}   // | {type:"cylinder", r,h}
                                      // | {type:"tube", pts:[[x,y,z]…], radius, closed}
          geomPos: [x,y,z],           // optional offset of the main primitive
          children: [{geom, position}], // extra primitives (e.g. brick studs)
          position: [x,y,z],          // unit placement (world)
          rotY: 0,                    // optional yaw
          color: "#hex",
          step: 0,                    // index into steps — drives HUD/step highlight
        }, …],
        ground: { w, d, color },      // optional base slab (baseplate, pegboard)
      },
      meta: { summary: "97 bricks · 6 colours" },   // toast/telemetry text
    };
  },
});
```

Rules that keep the layers clean:

- **Adapters never touch THREE or the DOM.** They emit data (geometry
  descriptors + step text). The viewer builds meshes from primitives only, so
  it renders crochet stitches or LEGO bricks with zero medium branching.
- `units` order **is** the build/reveal order — the shared transport
  (play / scrub / prev / next) and step list work automatically.
- Prefer the `text` route when the medium *is* crochet-shaped: you inherit the
  entire battle-tested pattern pipeline (parser, drape layout, hook animation).

## Layer 3 — Shared viewer

`renderPlanPreview(adapter, plan)` loads `plan.preview` into the existing 3D
studio: builds one mesh (group) per unit, frames the camera, wires the scrub
bar/HUD/step list. Reveal state comes from `App.progress` exactly as for
patterns — `totalUnits()` abstracts over the two modes.

## Shipped adapters

| id        | route     | notes |
|-----------|-----------|-------|
| `crochet` | `text`    | Tapestry chart: each IR row → `Row n: sc w`, per-stitch colours via the paint map; odd rows account for back-and-forth working so the image isn't mirrored. Transparent cells become background yarn. |
| `lego`    | `preview` | Mosaic on a baseplate: 1 cell = 1 stud; same-colour runs snap greedily to 1×8/6/4/3/2/1 bricks; transparent cells are skipped. |

## Adding the next medium (checklist)

1. Decide the route: crochet-shaped → `text`; anything else → `preview`.
2. Map IR cells to physical pieces; snap to the medium's real part sizes
   (like the LEGO brick lengths) and encode each piece as primitives.
3. Write `steps` a human can follow, one entry per visual group (usually rows).
4. `registerMediumAdapter(...)` — the picker, generation flow, viewer,
   transport and step list all pick it up with no further wiring.
