# tools

## make_hand_blender.py — high-fidelity grip hand

Generates the hand model the app loads at `assets/hand-right.glb`. It builds a
smooth, organic hand (Skin modifier + Subdivision Surface) with the crochet
grip **baked into the mesh**, so it needs no armature.

Run locally (Blender is **not** available in the cloud session):

```bash
blender --background --python tools/make_hand_blender.py
```

This writes `assets/hand-right.glb`. Commit and push that file:

```bash
git add assets/hand-right.glb && git commit -m "Add Blender-built grip hand" && git push
```

The app loads it automatically (see `loadHandModel` in `index.html`). After you
push the `.glb`, the placement/scale (`HAND_CFG`) may need a small tune to seat
it on the hook — that part can be done in a cloud session.

To tweak the hand itself, edit the skeleton/curl section near the top of the
script (finger `curl_angles`, `seg_radii`, `fingers` offsets, thumb nodes).
