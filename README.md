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
- **Armor** shows armor-specific controls and currently supports **Bracer** and **Pauldron**.

The Bracer generator creates a decorative forearm cuff / arm guard with:

- Length, wrist width, forearm width, thickness, and arc/curvature controls
- Knight, Barbarian, and Elven style options
- Optional raised trim, rivets, center ridge, blunt fantasy spikes, and rune-like decorative motifs
- User-facing warnings when dimensions are clamped into the supported decorative prop range

The Pauldron generator creates decorative shoulder armor with:

- Width, depth, height, plate count, plate overlap, and thickness controls
- Knight, Barbarian, and Elven style options
- Layered overlapping plates with optional trim, rivets, blunt fantasy spikes, and rune-like motifs
- User-facing warnings for thin plates, low overlap, high plate counts, oversized details, and extreme proportions

Armor output uses the same generated SCAD display, `.scad` download, PNG preview, and STL export buttons as Sword mode. OpenSCAD is still only required for preview and STL export.

Armor models are decorative/prototype fantasy prop geometry only. They are not wearable protective equipment and should not be treated as safety gear, fabrication-grade armor, or validated protective equipment.

Bracers and pauldrons are not fitted from real body measurements. Their dimensions are visual prop dimensions used to shape the model silhouette, not ergonomic, medical, safety, or protective fit guidance.

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
- Armor trim, rivets, spikes, and motifs are decorative surface details and are not validated for strength, comfort, or wearability.
- Preview quality and export behavior depend on the local OpenSCAD installation.
- More armor types and larger armor sets are planned but not implemented yet.
