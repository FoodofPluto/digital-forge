# Digital Forge Version 4

A minimum viable Streamlit fantasy prop designer that turns editable real-world dimensions into a self-contained OpenSCAD model.

## Setup

From this directory, install the two dependencies:

```powershell
pip install streamlit pytest
```

Run the app:

```powershell
streamlit run app.py
```

Use Streamlit's page navigation to open the **Preset Gallery**, which contains seven named,
ready-to-download configurations generated through the same OpenSCAD generator as the designer.

Run the tests:

```powershell
pytest
```

The downloaded `.scad` file can be opened directly in OpenSCAD. Dimensions are in millimetres. Realism and geometry messages are advisory and never prevent export.

## Version 2 Features

- Distinct tapered, leaf, needle, and falchion blade profiles
- Optional shallow fuller channels and a raised central ridge
- Editable ricasso dimensions, including visible greatsword and rapier defaults
- Distinct straight, crescent, downturned, and disk guards
- Distinct sphere, wheel, ring, and spike pommels
- Design notes and additional proportion-based realism guidance

## Version 3 Features

- Shared coordinate contract: blade on positive Y, guard at Y=0, and connected grip/pommel on negative Y
- Geometry audit messages separate from realism guidance
- Corrected guard orientation, capped disk guards, and a forward-heavy falchion profile
- Optional local OpenSCAD PNG preview and STL export with a configurable executable path
- OpenSCAD is optional and is not required for tests

Preview export requires a local OpenSCAD installation and uses its default command-line camera. No
interactive STL viewer is bundled. Generated geometry remains simplified and decorative.

## Version 4

Version 4 focuses on geometry stabilization, visual debugging, and safer optional exports:

- Part-specific generator helpers for blades, guards, grips, pommels, debug markers, and assembly
- Explicit shared anchors and bounds for every major sword part
- Optional visual centerline, anchor, and translucent bounding markers
- Stronger geometry audits for contact, orientation, dimensions, and unsupported combinations
- Structured OpenSCAD preview/export results for missing tools, invalid paths, command failures,
  timeouts, empty outputs, invalid input, and file errors
- A Streamlit debug toggle, grouped audit results, clear export errors, and known limitations

## Armor Mode

The main Streamlit app now has a top-level **Generation category** selector:

- **Sword** remains the default and preserves the existing sword controls, audit, preview, SCAD download, and STL export flow.
- **Scabbard** creates a straight-blade scabbard from inherited sword blade dimensions.
- **Armor** shows armor-specific controls and currently supports **Bracer** and **Pauldron**.

## Scabbard Mode

Scabbard mode is the Week 2 parametric scabbard core. It supports:

- **Symmetrical Tapered** blades
- **Leaf** blades

Unsupported blade families, including **Falchion** and **Curved**, fail with a clear validation message rather than generating a mismatched scabbard. The first scabbard implementation is straight-axis only and does not include curved sweep logic.

The scabbard inherits blade dimensions from the corresponding sword configuration:

- Blade type
- Blade length
- Base width
- Tip width
- Blade thickness
- Ricasso length
- Prop-safe tip width and blade thickness clamps used by sword generation

Clearance is defined as **per-side clearance** in millimetres. It is added around blade width and blade thickness, so the full internal cavity grows by twice the configured clearance across each axis. The default is intended for digital fit testing and early printable prototypes, but printer-specific tolerance calibration is still required.

Wall thickness is the minimum material between the internal blade cavity and the exterior shell on both side walls and face walls. Values below the safe minimum are clamped and reported in the geometry audit.

Split mode supports:

- **Single Piece**, which emits one complete scabbard shell.
- **Two Piece**, which emits named `scabbard_left_half()` and `scabbard_right_half()` modules split along the longitudinal center plane. The preview shows the halves separated for printing; removing the top-level translations digitally reassembles them without overlap.

The basic throat is an optional reinforced collar at the blade-entry opening. It leaves the insertion path open and uses the same cavity subtraction as the body. The basic end cap closes the outside past the blade tip while preserving the configured tip-clearance zone inside the cavity.

Scabbard output uses the same generated SCAD display, `.scad` download, PNG preview, and STL export buttons as Sword mode. OpenSCAD is optional for SCAD download and required only for PNG/STL export.

Automated completion-gate tests use deterministic profile-level checks instead of full solid collision testing. At sampled blade positions, tests verify:

- Cavity half-width is at least blade half-width plus per-side clearance.
- Cavity half-thickness is at least blade half-thickness plus per-side clearance.
- Exterior side and face walls remain at or above the safe minimum wall thickness.
- The throat entry remains open.
- The end cap starts beyond the required tip-clearance zone.

This proves digital clearance at the sampled profile level. It does not guarantee physical fit after printing, because material, slicer settings, support cleanup, sanding, shrinkage, and printer calibration still affect real-world tolerances.

The Bracer generator creates a decorative forearm cuff / arm guard with:

- Length, wrist width, forearm width, thickness, and arc/curvature controls
- Bracer Version 1 decoration choices: **Plain** or **Raised Design Panel**
- A Raised Design Panel with **Wide Panel** and **Narrow Panel** dimensional presets
- Wide Panel provides a broad maker-finished exterior field for sanding, painting, inscriptions, or mounting lightweight original decoration
- Narrow Panel provides a slimmer centered field for inscriptions or smaller original design work
- Expanded raised-panel height limits provide more exterior stock while keeping the arm cavity unchanged
- Adjustable panel length, width, height, edge roundness, and wrist-to-forearm position
- Binding / closure styles: None, Lacing Holes, Lacing Loops, Strap Slots, and Buckle-Ready Slots
- Strap Slots are true pass-through slots with protected edge margins
- Buckle-Ready uses an exterior two-ear receiver, central gap, pass-through strap slot, and transverse pin/bar passage
- User-facing warnings when dimensions are clamped into the supported decorative prop range

The Pauldron generator creates decorative shoulder armor with:

- Width, depth, height, plate count, plate overlap, and thickness controls
- Knight, Barbarian, and Elven style options
- Layered overlapping plates with optional trim, rivets, blunt fantasy spikes, and rune-like motifs
- User-facing warnings for thin plates, low overlap, high plate counts, oversized details, and extreme proportions

Armor output uses the same generated SCAD display, `.scad` download, PNG preview, and STL export buttons as Sword mode. OpenSCAD is still only required for preview and STL export.

- Bracer PNG preview export can optionally render six angles: front exterior, front three-quarter, side profile, closure side, top oblique, and rear three-quarter.

Armor models are decorative/prototype fantasy prop geometry only. They are not wearable protective equipment and should not be treated as safety gear, fabrication-grade armor, or validated protective equipment.

Pauldron dimensions are visual prop dimensions used to shape the model silhouette, not ergonomic, medical, safety, or protective fit guidance. Bracer Version 1 defaults are wearer-specific prototype dimensions for the current validation build only; they are not universal ergonomic guidance.

### Bracer Version 1 validation preset

Recommended first final test-print settings for the current wearer-specific Bracer V1 prototype:

- Armor type: Bracer
- Length: 241.30 mm
- Wrist width: 76.20 mm
- Forearm width: 114.30 mm
- Depth: 69.85 mm
- Wall thickness: 4 mm
- Opening width: 34 mm
- Coverage angle: 220 degrees
- Exterior finishing allowance: 0.5 mm
- Closure style: Lacing Holes, unless another approved closure style is preferred for the build
- Decoration: Raised Design Panel
- Panel type: Wide Panel
- Panel length: 132 mm
- Panel width: 56 mm
- Panel height: 4.0 mm
- Panel edge roundness: 5 mm
- Panel position: 0 mm

Physical validation checklist:

- Verify fit using the wearer-specific length, depth, wrist width, and forearm width.
- Verify wrist insertion.
- Verify forearm comfort.
- Verify closure alignment.
- Verify no closure passages are obstructed.
- Inspect Strap Slot material around every edge.
- Verify the exterior Buckle-Ready ears are connected.
- Verify the central Buckle-Ready gap remains open.
- Verify the Buckle-Ready strap passage remains open.
- Verify the transverse Buckle-Ready pin passage remains open.
- Verify the Buckle-Ready receiver does not intrude into the arm cavity.
- Test straps or representative hardware through the slots.
- Verify the panel remains attached to the shell.
- Check Wide Panel clearance from closures.
- Compare Narrow and Wide Panel appearance.
- Confirm panel height provides useful finishing stock.
- Verify sanding does not expose or weaken the inner wall.
- Verify sanding does not weaken the shell.
- Check for sharp edges.
- Check for cracking near wrist and forearm openings.
- Confirm print orientation and support requirements for the chosen material and printer.
- Confirm exported geometry is manifold using the available OpenSCAD preview/export workflow.

Do not record the bracer as physically validated until an actual print has passed these checks.

## Coordinate system

All dimensions are millimetres. The sword is centered on `X=0` and points along positive Y.
From lowest to highest on Y, the assembly order is pommel, grip, guard, then blade.

- `grip_start_y = -grip_length_mm`
- `grip_end_y = 0`
- `guard_bottom_y = grip_end_y`
- `guard_top_y = guard_bottom_y + guard_height_mm`
- `blade_start_y = guard_top_y`
- The pommel overlaps the grip by up to 2 mm to prevent visible render gaps

Style-specific details may be offset, but the primary blade, guard, grip, and pommel remain on the
common X centerline.

## Debug geometry

Enable **Debug geometry** in the Streamlit sidebar to add:

- Blade start, guard center, grip start/end, and pommel center markers
- A red sword centerline
- Translucent blade, guard, grip, and pommel bounds

Debug geometry is omitted from normal generated SCAD and exports when the toggle is disabled.

## Preview and export

Core generation, audit, UI startup, and tests do not require OpenSCAD. PNG preview and STL export
require a local OpenSCAD command-line executable. Enter either `openscad` when it is on `PATH` or
the full executable path in the sidebar.

Export failures are reported in the app without stopping SCAD generation or downloads.

## Known limitations

The generated models use intentionally simplified, decorative geometry. They are not exact engineering, weapon-manufacturing, or protective-equipment plans and are not suitable for fabrication decisions. The app does not model accurate edge bevels, distal taper, complex guard construction, body fit, articulation, material properties, mass, balance, structural loads, impact resistance, or fabrication-grade validation.

- OpenSCAD PNG previews use its default command-line camera.
- No interactive STL viewer is bundled.
- Debug bounds are visual diagnostics, not collision or manufacturability analysis.
- Sword and guard variants remain intentionally limited while the shared geometry contract stabilizes.
- Armor mode currently supports Bracer and Pauldron as the first armor modules.
- Scabbard mode currently supports only Symmetrical Tapered and Leaf straight blades.
- Scabbard fit validation is deterministic profile-level digital validation, not physical print validation.
- Scabbard mode does not include suspension rings, belt loops, frog attachments, ornate chapes, decorative throat fittings, magnets, snap-fit locks, retention clips, drainage holes, or alignment pins.
- Bracer Version 1 does not include coded motifs, runes, spikes, rivets, or themed decoration presets.
- Wide and Narrow Raised Design Panels are maker-finished stock only; sanding behavior, attached decorative pieces, fit, supports, print orientation, and material-specific durability still require physical inspection.
- Preview quality and export behavior depend on the local OpenSCAD installation.
- More armor types and larger armor sets are planned but not implemented yet.
