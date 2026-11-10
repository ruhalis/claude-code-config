# FDM fit values

Starting values, to be calibrated with one test coupon print. Values are for a 0.4 mm nozzle, PLA or PETG. text-to-cad's printing check (`cad model dfm --process printing`) measures walls and overhangs only, not fits or hole diameters; these values and `scripts/fit_check.py` do.

Calibrated on: ______________________ (printer, nozzle, material, date)

## Test coupon

A 30x30x5 mm plate with:
- through holes 2.8 / 3.0 / 3.2 / 3.4 mm (which one passes an M3 screw freely)
- a few slots (e.g. 3.2 x 8 mm) to check slot width and length
- a 10 mm peg on one side with mating 10.2 / 10.3 / 10.4 mm holes (press vs sliding fit)

Print it flat, measure or try the fits, then overwrite the values below.

## Values

| Feature | Nominal | FDM 0.4 mm PLA/PETG | Note |
|---|---|---|---|
| M2 clearance hole | 2.0 | 2.4 | normal fit |
| M2.5 clearance hole | 2.5 | 2.9 | normal fit |
| M3 clearance hole | 3.0 | 3.4 | normal fit |
| M2 heat-set insert hole | 2.0 | ~3.2 | common brass inserts; check the insert datasheet |
| M2.5 heat-set insert hole | 2.5 | ~3.6 | depth 1.2x insert length, 1 mm extra wall around |
| M3 heat-set insert hole | 3.0 | ~4.0 | depth 1.2x insert length, 1 mm extra wall around |
| M2 self-tapping into plastic | 2.0 | 1.8 | pilot hole |
| M2.5 self-tapping into plastic | 2.5 | 2.2 | pilot hole |
| M3 self-tapping into plastic | 3.0 | 2.7 | pilot hole |
| Press fit peg | peg dia. | +0.2 to +0.3 | clearance added to the hole |
| Sliding fit | peg dia. | +0.4 to +0.5 | clearance added to the hole |
| Lid lip gap | 0 | 0.3 per side | |
| PCB pocket clearance | board outline | +0.5 per side | around the board outline |
| Connector cutout clearance | connector body | +0.5 to +1.0 | per side |
| Standoff height above PCB bottom | - | tallest bottom component + 1 mm | |
| Minimum wall | - | 1.6 (4 perimeters), 1.2 thin | |
| Minimum feature | - | 0.8 | |
| Minimum hole | - | 2.0 | text-to-cad's FDM limit, not measured by its dfm; the 1.8 M2 pilot sits under it, so prove it on the coupon |
| Horizontal-axis hole compensation | hole dia. | +0.2 mm or teardrop | holes printed with axis along X/Y sag |
| Bottom edge chamfer | - | 0.5 | elephant foot |

## Check thresholds

Single values `scripts/fit_check.py` asserts, from the table above. The check measures the B-rep, never a mesh.

| Check | Limit | From |
|---|---|---|
| Mounting-hole centre, part vs `board.step` (and `positions.csv` rows) | <= 0.05 mm | |
| Part hole diameter at a mount | table value +/- 0.01 | clearance, insert or pilot row |
| Connector body to part | >= 0.5 mm | low end of connector cutout clearance |
| PCB pocket gap, board edge to walls at board height | >= 0.5 mm per side | PCB pocket clearance |
| Part overlap with board or connectors | 0 mm3 | |

## Mesh export tolerance

STL and 3MF for printing: `--tolerance 0.02` (mm), about a tenth of the smallest clearance above (the +0.2 press fit). The default viewer mesh can sit up to 0.2 mm inside a curved surface, as much as a clearance. Lower it if a tighter fit is added; stay at or above 0.001. STEP takes no tolerance.
