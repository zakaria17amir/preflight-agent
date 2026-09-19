| bug | size | A_cold_strong | B_brief_cheap | C_cascade | D_cascade_nohandoff | E_capped_handoff | F_capped_nohandoff |
|---|---|---|---|---|---|---|---|
| report_counter | S | PASS $0.083 | PASS $0.055 | PASS $0.064 (haiku) | PASS $0.065 (haiku) | PASS $0.154 (sonnet) | PASS $0.055 (haiku) |
| fahrenheit | S | PASS $0.105 | PASS $0.091 | PASS $0.059 (haiku) | PASS $0.062 (haiku) | PASS $0.064 (haiku) | PASS $0.053 (haiku) |
| power_assoc | M | PASS $0.092 | PASS $0.082 | PASS $0.058 (haiku) | PASS $0.087 (haiku) | PASS $0.147 (sonnet) | PASS $0.056 (haiku) |
| leading_dot | M | PASS $0.169 | PASS $0.076 | PASS $0.076 (haiku) | PASS $0.073 (haiku) | PASS $0.132 (sonnet) | PASS $0.056 (haiku) |
| unit_to_base | L | PASS $0.174 | PASS $0.117 | PASS $0.124 (haiku) | PASS $0.128 (haiku) | PASS $0.225 (sonnet) | PASS $0.212 (sonnet) |
| **total** | | **5/5 pass, $0.623** | **5/5 pass, $0.421** | **5/5 pass, $0.380** | **5/5 pass, $0.415** | **5/5 pass, $0.721** | **5/5 pass, $0.431** |

Other engines / tier pairs (devin $ are list-price estimates):

| bug | size | A_cold_strong@devin_gpt-5.6-luna-to-sonnet | B_brief_cheap@devin_gpt-5.6-luna-to-sonnet | C_cascade@devin_gpt-5.6-luna-to-sonnet |
|---|---|---|---|---|
| report_counter | S | PASS $0.042 | PASS $0.016 | PASS $0.018 (gpt-5.6-luna) |
| fahrenheit | S | PASS $0.043 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| power_assoc | M | PASS $0.045 | PASS $0.011 | PASS $0.018 (gpt-5.6-luna) |
| leading_dot | M | PASS $0.052 | PASS $0.015 | PASS $0.012 (gpt-5.6-luna) |
| unit_to_base | L | PASS $0.070 | PASS $0.014 | PASS $0.017 (gpt-5.6-luna) |
| **total** | | **5/5 pass, $0.253** | **5/5 pass, $0.067** | **5/5 pass, $0.082** |