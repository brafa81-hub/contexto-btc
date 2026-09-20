# Medicion: tasa de supervivencia EN_CONFIRMACION -> CONFIRMADA

Motor: simulacion/calibracion-3de5/pipeline_end_to_end.py (sha256 04e5a9cc606d35957ea01dc1d4d735cb93fba0c17f77a4ec6d1679bebbabd66d), reutilizado sin modificar via medicion_supervivencia.py. 400 replicas por nivel/escenario, generador n_historico=4260, eps_min=8, q_nominal BY=0.2, lote_n=12.

## Resultados

| Escenario | Nivel | n EN_CONF | CONFIRMADA | IC95 | RECHAZADA_FWD | IC95 | PENDIENTE | IC95 |
|---|---|---|---|---|---|---|---|---|
| uniforme | ruido_puro | 0 | - | - | - | - | - | - |
| uniforme | efecto_bajo | 34 | 55.9% | [39.5-71.1] | 38.2% | [23.9-55.0] | 5.9% | [1.6-19.1] |
| uniforme | efecto_medio | 318 | 78.6% | [73.8-82.8] | 17.0% | [13.3-21.5] | 4.4% | [2.6-7.3] |
| uniforme | efecto_alto | 400 | 96.0% | [93.6-97.5] | 3.2% | [1.9-5.5] | 0.8% | [0.3-2.2] |
| concentrado | ruido_puro | 0 | - | - | - | - | - | - |
| concentrado | efecto_bajo | 39 | 43.6% | [29.3-59.0] | 30.8% | [18.6-46.4] | 25.6% | [14.6-41.1] |
| concentrado | efecto_medio | 296 | 70.3% | [64.8-75.2] | 22.0% | [17.6-27.0] | 7.8% | [5.2-11.4] |
| concentrado | efecto_alto | 399 | 90.7% | [87.5-93.2] | 5.8% | [3.9-8.5] | 3.5% | [2.1-5.8] |
