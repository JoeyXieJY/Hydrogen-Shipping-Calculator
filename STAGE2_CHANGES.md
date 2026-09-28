# Stage 2 implementation record

## Replaced calculation paths

- Removed linear shipping BOG and replaced it with daily exponential loss.
- Removed storage-capacity × 365-day BOG.
- Removed the duplicate `ship_capacity_kg` input.
- Removed `forced_bog`, which previously inflated BOG to match propulsion demand.
- Removed custom route/port calculation paths and the editable ship-speed input.
- Removed the fixed 11-day override.

## Mass-balance sequence

1. Export storage feed is back-calculated so the planned departure fill is achieved after export storage loss.
2. Loaded outbound cargo undergoes exponential shipping BOG.
3. Target heel is retained before unloading.
4. Unloaded cargo undergoes exponential import storage loss.
5. Return-leg loss applies only to heel; only the lost heel is made up.
6. Managed BOG offsets propulsion demand; any remaining demand is separately bunkered and is not deducted from cargo a second time.

## Ammonia cracking

```text
recovered H2 = usable NH3 × 0.177 × cracker conversion × PSA recovery
```

The model reports shipping cost and delivered transport-chain cost separately. The ammonia result still includes cracking cost; the hydrogen route does not include ammonia cracking.

## Emissions

The main result includes export-terminal electricity, ship-fuel CO2/CH4/N2O, import-terminal electricity and ammonia cracking. Hydrogen leakage is shown as a supplementary indirect climate impact. Production of hydrogen and ammonia is excluded.

## Default regression snapshot

| Carrier | Shipping cost (A$/kg H2-eq) | Landed cost (A$/kg H2) | Delivered H2 (kg/year) | Transport-chain emissions (t CO2e/year) |
|---|---:|---:|---:|---:|
| Ammonia | 0.355171 | 0.978345 | 243,780,143.99 | 862,548.97 |
| Hydrogen | 0.791743 | 0.791743 | 182,153,657.02 | 131,645.53 |

These values are regression fixtures for the confirmed assumptions, not external validation of real project performance.

