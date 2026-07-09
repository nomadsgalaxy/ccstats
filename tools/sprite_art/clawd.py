# ccstats — self-hosted Claude Code usage stats (badge firmware + server)
# Copyright (C) 2026 Zapador <zapador@zapador.net>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of version 2 of the GNU General Public License as published by the
# Free Software Foundation. See the LICENSE file for the full text.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

# CLAWD — Claude Code's little crab mascot, the new default avatar. This is a
# FAITHFUL trace of the real Clawd art (Anthropic's mascot; coral #DE886D):
# a plain rectangular torso, two 2px side arms, four little legs, and two thin
# 1x2 vertical bar eyes. No mouth at rest (the real asset's mouth is yawn-only),
# no shade/hi (the art is flat coral) — like every sprite it themes to the
# palette's avatar pen. Geometry mapped 1:1 from clawd-idle-living.svg into the
# 16-cell grid (dy=-1 so the feet sit at ~row14 like GLOOM). Sprite-art data
# module consumed by tools/build-avatar-frames.py.
#
# roster_index -1 sorts CLAWD ahead of GLOOM (0) as the flagship default without
# renumbering the existing roster; the ghost and the other 9 stay reachable in
# the OPTIONS picker / button cycle. happy = the same bar eyes (the real happy
# pose keeps its face; the hop + done-sparkles carry the celebration).

SPRITE = {
    "name": "clawd",
    "label": "CLAWD",
    "roster_index": -1,  # before GLOOM(0): the default, no roster renumber
    "grid_cells": 16,    # 16 -> 7 px cells in the 112px box (matches GLOOM)
    # 12x16 sweat bead top-left, DEVICE px in the neutral 112px box, on the
    # torso's upper-right corner (rides the squash transform at draw time)
    "sweat_anchor": (84, 34),
    "layers": {
        # torso (2,6,11,7) + side arms (0,9,2,2)/(13,9,2,2) + four legs (x=3,5,
        # 9,11), all coral; rows 8-9 are the full-width torso+arms bar
        "fill": ((2, 5, 11, 3), (0, 8, 15, 2), (2, 10, 11, 2),
                 (3, 12, 1, 2), (5, 12, 1, 2), (9, 12, 1, 2), (11, 12, 1, 2)),
        # two thin 1x2 black vertical bar eyes (solid => the pupil layer, drawn
        # in background = dark on the body); no eye-whites
        "eyes_pupil": ((4, 7, 1, 2), (10, 7, 1, 2)),
        "happy": ((4, 7, 1, 2), (10, 7, 1, 2)),
    },
}
