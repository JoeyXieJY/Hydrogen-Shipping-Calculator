# Stage 1 model corrections

The first correction stage changes the calculation baseline without adding new technologies or advanced loss models.

## Corrected assumptions

- Operating days: 350 days/year.
- Ammonia hydrogen mass conversion: 0.177 kg H2/kg NH3.
- Base route: Gladstone (QLD) to Tokyo (Japan).
- One-way distance: 7,148.72 km.
- One-way voyage time: calculated from distance and ship speed; at 20 knots it is 8.0417 days.
- Optional voyage-time adjustment factor: effective duration equals calculated duration multiplied by the factor. The default is 1.00 (no adjustment).

## Corrected default outputs

| Carrier | Round trips/year | AUD/kg H2 | AUD/tonne medium | AUD/GJ medium |
| --- | ---: | ---: | ---: | ---: |
| Ammonia | 18.3406 | 0.3431 | 60.7335 | 3.2652 |
| Hydrogen | 18.3406 | 0.9151 | 915.0739 | 7.6256 |

These remain shipping-model outputs. Ammonia cracking efficiency, improved BOG treatment, lifecycle emissions and parameter-source updates belong to later stages.

## Verification

Run:

```bash
python -m py_compile app.py model.py test_model.py
python -m unittest test_model.py -v
```

The regression suite checks the corrected route distance, automatic voyage time, optional voyage-time adjustment factor, operating days, ammonia conversion, cost outputs and the effect of ship speed.

