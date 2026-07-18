# Digital Forge Futurewear Physical Calibration

This workflow records printer/material/process-specific prototype results for `DF-MOD-1.0`.
It is not safety certification and does not guarantee commercial fit.

1. Generate the Standard Dock clearance ladder.
2. Print the ladder in the intended material and orientation.
3. Do not force samples together.
4. Remove elephant-foot, brim, and support artifacts consistently before evaluation.
5. Test insertion and intentional removal for each clearance sample.
6. Choose the best sample and perform at least 20 insertion/removal cycles.
7. Test the Null Tile at the selected clearance.
8. Record the results in Futurewear > Connector Test > Record Print Results.
9. Save the printer/material calibration profile.
10. Use the saved profile as the starting point for wristwear and pendant prototypes.

Repeat calibration when changing printer, material, nozzle, layer height, slicer, orientation, or major slicer settings.

Calibration profiles are specific to the physical process used to create them. Wearable products still require comfort, skin-contact, snag, and durability testing.

Sample storage structure:

```json
{
  "schema_version": 1,
  "profiles": [
    {
      "profile_id": "example",
      "name": "Example PLA Standard Dock",
      "standard_version": "DF-MOD-1.0",
      "connector_type": "Slide Rail",
      "connector_size": "Standard",
      "material_name": "PLA",
      "printer_name": "Printer name",
      "nozzle_diameter_mm": 0.4,
      "layer_height_mm": 0.2,
      "slicer_name": "Slicer",
      "print_orientation": "Flat on build plate",
      "printer_compensation_mm": 0.0,
      "elephant_foot_compensation_mm": 0.0,
      "selected_clearance_mm": 0.32,
      "fit_rating": "Firm Functional Fit",
      "repeated_cycle_count": 20,
      "retention_result": "Functional",
      "visible_damage": false,
      "notes": "",
      "created_at": "2026-07-18T00:00:00+00:00",
      "archived": false
    }
  ]
}
```
