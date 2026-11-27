# Placement and routing

Gates 4 and 5. The checklist for what a good result looks like is `layout-review.md`; this file is the order of work and how to know it is finished.

## Placement (gate 4)

1. **The user fixes what the model cannot see:** connector positions and orientation, mounting holes, the outline, and which edge the antenna faces. Lock those first and do not move them.
2. Place the rest yourself, in this order: decoupling and other support parts against the pins they serve; regulators with their inductor and capacitors as one tight group; the parts on each matched pair or noise-sensitive net next to each other; everything else last.
3. Keep the antenna keep-out clear of copper, vias and parts on every layer, by the module datasheet's drawing.
4. Run `export_review.sh pcb` and read the renders before any routing. Show the user the top and bottom renders at this gate: a bad placement is cheap to fix now and expensive after routing.

Placing parts yourself is better than routing around a placement you did not make: independent runs of Fable 5.2 on stripped boards routed their own placements more reliably than someone else's.

## Routing (gate 5)

Route in two passes.

**By hand, scripted, with the reason for each choice written down:**

- USB and any other differential pair: matched, over an unbroken reference plane, at the width and gap the stack-up needs.
- Each switching regulator's hot loop and its feedback trace.
- High-current paths, at a width calculated for the current and the copper weight.
- The antenna feed, crystal traces and anything analog and quiet.

**By a router, for the slow nets that are left.** Use the project's own router when it has one (aquila: `tools/route.py` and `tools/router.py`, which wrote both of its boards). The candidate for a board without one is KiCadRoutingTools (github.com/drandyhaas/KiCadRoutingTools, MIT, works on the `.kicad_pcb` file with no running KiCad): pin a release tag, run it on a copy, and compare the open-net count and the post-route checks with what the project's router gives. It has not been run on a board here. Freerouting needs a Java runtime, which this Mac does not have, and a DSN and SES round trip that KiCad 10's `kicad-cli` does not offer. Commercial routers are out: their quality claims are vendor-only and they take the design off the machine.

Rip up and redo a region when the first attempt is bad; do not patch around it.

## Finished means the counts say so

Run `erc_drc.sh drc`. Gate 5 needs 0 violations, 0 unconnected items and 0 parity errors on the saved zones and again on refilled zones. Then the checks DRC does not make, because a router's output can be legal and still poor:

| Check | Why |
|---|---|
| No slow net crosses under a differential pair or cuts a plane beneath a fast or high-current trace | A legal track can still break the return path |
| Track width against current on every supply and motor net | DRC checks the minimum width, not the needed one |
| No acute angles, no stubs that turn back on themselves, no unconnected track ends | Model-written and automatic routers leave them |
| Via count on ground and supply nets is sane, with stitching where planes change layer | Routers over- and under-stitch |
| Quiet analog traces keep their distance from switching nodes and LED or motor copper | Clearance rules do not know which nets are noisy |
| Zones refilled after the last track change | A stale fill can invent or hide a connection |

The project keeps its own standing checks where it has them (aquila: `tools/checks/`); run those too. Read the copper crops from `export_review.sh pcb` last: the picture confirms what the numbers say, and does not replace them.
