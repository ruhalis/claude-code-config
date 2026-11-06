# Visuals for a lesson

How to build and embed each level of the visual ladder in `SKILL.md`, and the brief to send when a level is delegated. Every brief must stand on its own: the agent sees none of the lesson.

All media for a lesson live under the lesson folder in the scratchpad directory, `teach/<slug>/media/`, and are published next to the page through the Artifact tool's `files` map, for example `{"media/turntable.mp4": "<scratchpad>/teach/<slug>/media/turntable.mp4"}`. Limits: 15 MB per binary file, 16 MB for the page including any `data:` URIs.

## Level 2: inline SVG diagram

Load the `artifact-diagramming` skill and follow it (colours as theme tokens so the diagram works in light and dark, real mechanism over decoration). One idea per diagram, every part labeled with the name used in the text. The dependency map at the top of the page is a level-2 diagram too: roots at the top or left, edges meaning "needed to see".

## Level 3: anatomy figure

Delegate to a `general-purpose` agent:

```
Load the `anatomy` skill and build one figure for a lesson on <topic>.
Idea the figure must make visible: <one sentence, e.g. "how the escapement lets the gear advance one tooth per swing">.
Parts to show and label: <list>. Motion, if any: <what moves and why>.
Style: matches a page with <light/dark> theme; no title card needed beyond the part names.
Work in <scratchpad>/teach/<slug>/media/figure/. Run the skill's audit and look at a snapshot before you finish.
Return: path of the built HTML page (self-contained if the skill allows), path of a PNG snapshot, and anything you could not show. Under 150 words.
```

Embed: publish the figure's HTML as a supporting file and show it in an `<iframe>` sized to its card; inline the SVG instead when it is self-contained and static. Keep the PNG as the fallback image. An HTML file in `files` is served as its own page, so it needs its own doctype and charset.

## Level 4: 3D model in three.js

Use when the idea is shape, assembly, frames or rotation. Load three.js as ES modules from jsdelivr at an exact version with an import map:

```html
<script type="importmap">
{"imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>
<script type="module">
  import * as THREE from 'three';
  import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
  import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
  // scene, camera, renderer sized to the container; resize observer; OrbitControls;
  // ambient + directional light; background from the page's theme token
</script>
```

- **Concept geometry** (axes, frames, vectors, a rotating body, a simple linkage): build it in the page with three.js primitives. No GLB needed, and it can be animated to show the idea.
- **A real part**: load a GLB with `GLTFLoader`. GLB is binary glTF 2.0, which three.js loads natively.
  - From the user's repo: an existing `.glb` export.
  - From CAD: delegate to a `general-purpose` agent (brief below).
- **Publishing a GLB**: put it in `files` with an explicit type, `{"media/part.glb": {"from": "<path>", "contentType": "model/gltf-binary"}}`. This path is not yet verified; if the publish refuses the type, embed the file as a base64 `data:model/gltf-binary;base64,...` URI instead (fine up to a few MB, it counts toward the 16 MB page limit) and pass that URI to `GLTFLoader.load`. Note in `learner.md` or the repo which way worked, so the next lesson skips the trial.
- Label parts with HTML overlays or `CSS2DRenderer`, not text baked into textures. No auto-rotate when `prefers-reduced-motion` is set. Give the canvas a fixed aspect so it fits phone width.

CAD-to-GLB brief for a `general-purpose` agent:

```
Load the text-to-cad `cad` skill and model <part or assembly> for a lesson on <topic>.
What the model must show: <the spatial idea>. Accuracy needed: <illustrative / real dimensions from X>.
Separate bodies for: <parts the lesson names>, so they can be coloured and labeled.
Export one GLB to <scratchpad>/teach/<slug>/media/<name>.glb and look at it in CAD Viewer or a snapshot first.
Return: GLB path and size, body names in the file, units, anything simplified. Under 150 words.
```

## Level 5: video or GIF

Always the `video-maker` agent; never run HyperFrames in the main session.

```
Make a <5-20> s explainer clip for a lesson on <topic>.
The one idea it must show: <sentence>. Sequence: <beat 1 -> beat 2 -> beat 3>.
On-screen text: <labels/captions, exact words>, language <English/Russian>. No intro or outro.
Aspect <16:9 / 1:1>, style to match a page with <light/dark> theme, colours <tokens>.
Outputs: MP4<, and a GIF under 10 MB> in <scratchpad>/teach/<slug>/media/. Local render only.
```

Embed the MP4 with `<video controls loop muted playsinline poster="media/<name>.png" src="media/<name>.mp4">` and a GIF as a plain `<img>`, both published through `files`. Look at the poster frame before it goes on the page; if the clip misses the idea, send the same agent a correction with `SendMessage` rather than starting over.

## Fact-check batch

For a `general-purpose` agent, launched once during Plan:

```
Verify each claim below for a lesson on <topic>. For each: TRUE / FALSE / NEEDS CAVEAT, the corrected wording if not TRUE, and one source URL (primary source or textbook preferred).
1. <claim>
2. <claim>
...
Answer as a numbered list in the same order, under 300 words. Don't add claims I didn't ask about.
```
