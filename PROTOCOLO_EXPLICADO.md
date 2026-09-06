# El protocolo v2, explicado en lenguaje llano

Este documento describe el sistema tal y como está, no como sería elegante que
estuviera. Donde hay huecos, se dicen. Donde una regla no está clara en la
doctrina, se dice también en lugar de rellenarla.

Está escrito contra este estado verificado del repositorio:

| Fichero | SHA-256 |
|---|---|
| `v2.json` | `c12a1f0d6d9160d278483dbb2e84dba7771b2be321d4abc26a744cf07bb0f5a5` |
| `filtro.py` | `e7ced4352fc1f4be3264ca1a411a301429bbaa28b0b31c01c66ce4bcbdec9ea6` |
| `registro.json` | `8257e0c369406801ddeb94c62c99902711fd76b4cc31b240ed3b6378973e403b` |
| `requirements.txt` | `f0e59c76d7628bed28eecbd49a216dc45f9f4a277d2c3246cc3d64a44b9f4be5` |
| `cadena.py` | `ac6576efbba641f5ef241aa4e1da51739d10ed8defaa8815f5f6dce9a4156997` |
| `enmienda_35.py` | `11682bbad1a0982fc9f721aa0eaf4dafb2c1147ddb98d3c30df9b1ac08f8d737` |
| `informe_2026Q3_ssr_capstables.json` | `eaff81e22ebbe8ecc1c5b7381134206549c9a999a1e70fc1114d54d5801f0e88` |

Este propio documento no aparece en la tabla: no puede contener su propio
SHA-256, porque calcular el hash de un fichero que incluye su propio hash es
una referencia circular. No se disimula el hueco.

Si abres el repositorio y estos hashes no coinciden, el sistema ha cambiado
desde que se escribió esto. Lee la doctrina, no este documento.

---

## 1. Qué responde el sistema y qué no

Contexto-BTC es un **panel de contexto de mercado para Bitcoin**.

Responde a preguntas del tipo: *¿en qué situación está el mercado ahora mismo,
comparado con su propia historia?*

**No** responde a: *¿va a subir?* No es un bot, no ejecuta órdenes, no predice
precio y no da señales de compra ni de venta.

La mayor parte de la maquinaria que verás en el repositorio no sirve para
generar el panel. Sirve para **decidir qué variables merecen entrar en él**. Esa
es la parte cara: el panel en sí es la parte fácil.

El sistema parte de un supuesto incómodo: la mayoría de indicadores de cripto
que parecen funcionar no funcionan, y parecen funcionar porque quien los mira ya
ha visto los datos antes de decidir cómo mirarlos. Todo el protocolo v2 existe
para impedirse a uno mismo hacer eso.

---

## 2. Las cuatro piezas

| Pieza | Fichero | Qué es |
|---|---|---|
| Doctrina | `v2.json` | Las reglas. La fuente de verdad |
| Registro | `registro.json` | El historial de decisiones, encadenado |
| Motor | `filtro.py` | El código que lee las reglas y las aplica |
| Cadena | `cadena.py` | Utilidad de verificación del encadenado |

La separación clave es entre **doctrina** y **motor**, y responde a un problema
concreto: si las reglas viven dentro del código, cambiarlas es tan fácil como
editar una línea, y nadie se entera. Si viven en un fichero aparte que el código
solo lee, cambiar una regla es un acto visible y deliberado.

La doctrina lo dice sin ambigüedad (`meta.precedencia`):

> Este archivo es la fuente de verdad del protocolo. Ninguna regla vive dentro
> del código. Si `filtro.py` y este archivo discrepan, `filtro.py` debe abortar,
> no adaptarse.

**Abortar, no adaptarse.** Esta es probablemente la regla más importante del
sistema entero. Un programa que se adapta a una contradicción la esconde. Un
programa que aborta te obliga a resolverla. El coste es que el sistema se
bloquea con facilidad; el beneficio es que nunca produce un resultado cuyo
significado no esté claro.

La misma lógica aparece en varios sitios: ante un estado desconocido, aborta;
ante un tipo de entrada desconocido, aborta; ante un hueco de tres días en la
serie de precio, aborta.

---

## 3. El registro encadenado

`registro.json` es la lista de todo lo que se ha decidido: variables
propuestas, fichas congeladas, aclaraciones, resultados de test.

Es **append-only**: solo se añade al final, nunca se edita ni se borra lo
anterior.

Para que eso no dependa de la buena voluntad, cada entrada lleva el hash SHA-256
de la anterior. Si alguien edita una entrada pasada, su hash cambia y todos los
eslabones posteriores dejan de cuadrar. `filtro.py` recorre la cadena al
arrancar y aborta si algo no encaja.

Git ya guarda el historial, pero un `diff` aislado puede pasar por alto una
edición silenciosa. La cadena la hace imposible de disimular.

**El hueco conocido y su parche.** Una cadena a la que le cortas el final sigue
verificando: el hash apunta hacia atrás, no hacia adelante, así que nada dentro
del propio fichero sabe cuántas entradas debería haber. Para eso hay un GitHub
Action que, en cada push, comprueba que el registro nuevo es una extensión del
viejo (mismo prefijo, cero entradas borradas). Si no lo es, bloquea el merge.

Este parche depende de Git. La doctrina lo declara: **un borrado completo del
historial de Git no es detectable desde dentro del repositorio.**

---

## 4. El recorrido de una variable, de principio a fin

Este es el mapa. Todo lo demás son detalles de alguna de estas etapas.

```
   IDEA
     │
     ▼
   PROPUESTA ──────► se escribe la FICHA CONGELADA
     │                (antes de tocar ningún dato)
     ▼
   EN_TEST ────────► consume 1 de las 12 plazas del trimestre
     │                se fija la fecha de corte de bloques
     │
     ├── bloque 1 (primera mitad de la historia)
     │      └─► LOS 4 GATES ──► si falla ──► DESCARTADA_GATE_n  ✖ FIN
     │
     ├── bloque 2 (segunda mitad)
     │      └─► p-valor + corrección BY ──► si falla ──► RECHAZADA_PVALOR  ✖ FIN
     │
     ▼
   EN_CONFIRMACION ─► 5 trimestres de datos que NO EXISTÍAN al proponerla
     │
     ├── falla ──► RECHAZADA_FORWARD  ✖ FIN
     └── pasa  ──► CONFIRMADA  ✔ entra en el panel
```

Cada flecha marcada con ✖ es definitiva. No hay vuelta atrás desde ninguna.

Los datos de la variable se parten por la mitad: la primera mitad (bloque 1) se
usa para los gates, la segunda (bloque 2) para el p-valor. El bloque 1 queda
**contaminado por la selección** — se ha mirado para decidir — y el bloque 2 no.
Por eso el bloque 2 es la única estimación limpia disponible en el momento del
test, y la que sirve de línea base más adelante.

Si a una variable no le llegan 3 años en cada bloque, no se testea: queda en
`PENDIENTE_REVISION`, no consume presupuesto y no entra en la corrección
estadística. (Es el caso de la variable de flujos de ETF: no tiene historia
suficiente todavía.)

---

## 5. La ficha congelada

Antes de descargar un solo dato, hay que escribir una ficha que fija:

- **`metrica_continua`** — qué se mide exactamente.
- **`mascara`** — la regla determinista que convierte esa métrica en un
  sí/no. Se congela entera: el percentil, el tipo y longitud de ventana, si
  solo puede usar información anterior a *t*, la inclusividad, el warm-up.
- **`horizonte_N`** — a cuántos días se mide el efecto (fijo en 30 para todo v2).
- **`M`** — el efecto mínimo que se considera relevante.
- **`casilla_dashboard`** y su `funcion_D_theta` — qué casilla concreta del
  panel movería esta variable, y cómo.
- **`signo_esperado`** — positivo, negativo o bilateral.

Si falta cualquiera de ellos, `filtro.py` no deja pasar la variable a `EN_TEST`.

**Por qué antes de los datos.** Porque si defines la máscara después de mirar la
serie, estás eligiendo el umbral que mejor funciona y llamándolo hipótesis. La
ficha congelada es un precompromiso: escribes qué esperas encontrar y cómo lo
vas a medir, y luego ya no puedes cambiarlo.

Dos detalles que revelan cuánto se pensó esto:

- **Se congela el percentil, no el valor del umbral.** Un umbral absoluto sobre
  una métrica con tendencia fuerte se activaría casi solo en una época, y la
  variable fallaría el gate de estabilidad por construcción, no por falta de
  señal.
- **La casilla del dashboard se nombra por adelantado.** Sin eso, ante un
  resultado que no mueve la casilla A siempre cabe alegar que mueve la B. Eso es
  elegir la conclusión después de ver la evidencia.

**Cuándo deja de poderse cambiar.** La ficha se puede sustituir mientras la
variable esté en `PROPUESTA`. En cuanto pasa a `EN_TEST`, queda inmutable.
Después solo caben entradas de transición de estado o aclaraciones, y
`filtro.py` aborta si alguna toca un campo de la ficha.

La doctrina asume el coste explícitamente: un error de concepto en una ficha
descubierto después de `EN_TEST` **no se puede corregir, y esa variable queda
perdida**. Se acepta porque la alternativa —permitir arreglar fichas— es
permitir arreglarlas después de ver el resultado.

---

## 6. Un solo test por variable

> Una variable se testea una sola vez, en el trimestre en que entra.

`re_test_permitido: false`. La lista de excepciones está **vacía**. No hay
mecanismo de reapertura. Una variable descartada queda descartada de forma
permanente bajo este protocolo.

**Por qué esta regla es tan dura.** Si puedes volver a testear, puedes ir
probando variantes hasta que una pase, y entonces lo que has medido no es el
mercado sino tu propia insistencia. La regla es la que da sentido a todas las
demás: es lo que convierte cada test en una apuesta real.

**Consecuencia directa:** los errores de diseño son irreversibles. Si congelas
una máscara mal pensada, no descubres el error hasta después del test, y para
entonces la variable ya está gastada. Por eso se pone tanto cuidado antes y tan
poco margen después.

**Lo que NO es una excepción.** Una variable retirada antes de llegar a
`EN_TEST` (`RETIRADA_EN_PROPUESTA`) no fue testeada, así que volver a proponerla
no es un re-test. La doctrina lo aclara y deja la lista de excepciones vacía
igualmente.

**Caso real.** `ssr_capstables` (el *Stablecoin Supply Ratio*) fue testeada en
el lote 2026-Q3 y **rechazada en el gate 3**. Está en la entrada 23 como
`DESCARTADA_GATE_3`. Su propia entrada declara que el rechazo no otorga derecho
a re-proponerla ni a proponer variantes suyas: sería una puerta de escape
asimétrica, es decir, aceptar el resultado cuando gusta y buscar otra vía cuando
no.

---

## 7. Los gates, y lo permisivos que realmente son

Después de superar la ficha, la variable pasa cuatro filtros sobre el bloque 1.
Todos operan sobre la **máscara binaria**, nunca sobre la métrica continua,
porque el panel decide con la máscara: filtrar por otra cosa sería cribar por
una hipótesis distinta de la que emite el veredicto.

| Gate | Nombre | ¿Vincula? | Qué comprueba, en llano |
|---|---|---|---|
| 1 | `magnitud_en_tramos` | **Sí** | Que el efecto tenga tamaño suficiente, y no solo en un rato: se parte el bloque 1 en 3 tramos iguales y se mira la mediana |
| 2 | `anticipacion` | **No** | Si el efecto va por delante del precio o solo lo acompaña |
| 3 | `contribucion_incremental_R2` | **Sí** | Que aporte algo que no aporten ya Mayer, volatilidad 30d y momento 30d |
| 4 | `coherencia_de_signo_en_tramos` | **Sí** | Que el efecto apunte en la misma dirección en los 3 tramos |

**Qué significa que el gate 2 sea descriptivo.** Se calcula y se reporta en el
informe, pero **no puede descartar nada**. Se degradó (enmienda 19) porque se
midió su potencia y era nula frente a variables de régimen: dejaba pasar el
51,4 % con señal real contra el 53,8 % con ruido puro. Cuando la máscara es
persistente, la ventana hacia atrás está tan contaminada por el efecto como la
de adelante, y la comparación es un empate. Sigue sirviendo para distinguir
anticipación de régimen, que no es lo mismo que distinguir señal de ruido.

**Los umbrales no son números fijos.** Los gates 1 y 3 usan `nulo_por_rotacion`:
se rota circularmente la máscara de la propia variable 300 veces y se exige que
supere el percentil 50 de sus propias versiones barajadas. En llano: *la
variable debe superar lo que supera la mitad de las versiones barajadas de sí
misma*. La ventaja es que se adapta sola a la longitud de la historia y a la
velocidad de la máscara, sin fingir una ley universal. La limitación está
declarada: con máscaras muy lentas (racha media por encima de 60 días) el nulo
por rotación es inestable, y `filtro.py` lo hace constar en el informe.

### Y ahora la parte que no hay que saltarse

La doctrina obliga a imprimir este bloque literalmente en cada informe
(`regla_de_impresion`), precisamente para que nadie lea "capa de gates" y
suponga un cribado riguroso:

> Esta capa de gates no es un cribado permisivo. Medida por simulación sobre un
> bloque_1 de 1387 días con máscara activa el 20 % del tiempo, detecta
> aproximadamente el 39 % de un efecto real de theta=0.084 y deja pasar el 15 %
> del ruido puro. Un efecto real puede no atravesarla. **Que una variable sea
> descartada aquí no demuestra que no exista.**

Detección medida por tamaño del efecto:

| Efecto real (theta) | Lo detecta |
|---|---|
| 0.034 | 20 % |
| 0.056 | 26 % |
| 0.084 | 39 % |
| 0.147 | 56 % |
| ruido puro | pasa el 15 % |

Léelo dos veces: **un efecto real de tamaño medio tiene un 60 % de
probabilidades de morir en los gates.** Cuando dentro de dos años leas
"`ssr_capstables`: DESCARTADA_GATE_3", lo correcto es entender *no atravesó un
filtro que deja fuera a la mayoría de las señales reales*, no *el SSR no
sirve*.

El gate 4 tiene su propia advertencia obligatoria: tres tramos con el mismo
signo ocurre por azar una de cada cuatro veces. Es un cribado, no evidencia de
estabilidad.

Y estas cifras de potencia son **supuestos declarados, no datos observados**:
salen de un modelo sintético (deriva diaria constante con máscara activa, precio
GARCH tipo BTC) en `potencia_gates_v2.py`.

---

## 8. Después de los gates: p-valor y corrección múltiple

Si la variable pasa los tres gates vinculantes, se calcula su p-valor por
permutación sobre el **bloque 2**, con ventanas no solapadas.

Como en un trimestre se pueden testear varias variables, hay que corregir por
comparaciones múltiples: se usa **Benjamini-Yekutieli** con q nominal 0,20,
dentro del lote trimestral. Se eligió BY (y no el más común Benjamini-Hochberg)
porque BY no asume independencia entre las variables, y en cripto casi todo está
correlacionado.

Solo cuentan para la corrección las variables que llegaron a producir p-valor.
Las que murieron en los gates y las que están en `PENDIENTE_REVISION` no cuentan.
Hay un suelo de m=3 para que la corrección no sea trivial en lotes pequeños.

---

## 9. La confirmación forward: dónde está la garantía de verdad

Esta es la pieza central, y la que más fácilmente se pasa por alto.

La doctrina abre con una declaración obligatoria que hay que imprimir en cada
salida:

> Batch-PRDS actúa como cribado de descubrimiento. La garantía real de control
> de falsos positivos descansa en la confirmación forward sobre datos que no
> existían cuando la variable fue propuesta.

Es decir: **los gates y el p-valor no validan nada.** Solo seleccionan
candidatas. La validación ocurre después, contra datos que no existían —y que
por tanto nadie pudo mirar antes de decidir.

Una variable que supera el cribado pasa a `EN_CONFIRMACION` durante **5
trimestres**. La ventana es fija: no se extiende, no se acorta y no se puede
descartar antes de tiempo. Siempre se completan los cinco.

Para confirmarse debe cumplir **los tres criterios**:

1. **Signo agregado** — el efecto en la ventana forward apunta en la misma
   dirección que en el bloque 2.
2. **Magnitud** — el efecto forward conserva al menos la mitad del efecto del
   bloque 2, y además supera el mínimo absoluto M (0,03, o sea 3 puntos
   porcentuales de retorno a 30 días).
3. **Consistencia mínima** — al menos 3 de los 5 trimestres muestran el signo
   esperado.

Dos decisiones de diseño que merece la pena entender:

**Por qué la línea base es el bloque 2 y no la ventana completa.** El bloque 1
participó en la selección a través de los gates, así que su magnitud está
inflada. Exigir "la mitad de lo que dio el bloque 1" sería exigir la mitad de un
número hinchado. El bloque 2 es la única porción no contaminada.

**Por qué el efecto se mide agregado y no trimestre a trimestre.** La versión
original evaluaba cada trimestre y descartaba ante cualquier fallo. Se midió y
producía entre un 41 % y un 94 % de falsos descartes sobre señales reales pero
ruidosas. Tres revisiones externas independientes coincidieron en rechazarla. Un
trimestre suelto de BTC es demasiado ruidoso para decidir nada. El criterio 3 es
la única salvaguarda que mira los trimestres por separado, y está prefijada.

**Y por qué existe M.** Porque el criterio del 50 % por sí solo se rompe en los
dos extremos: si el efecto del bloque 2 salió pequeño por ruido, el listón queda
trivial; si salió grande por ruido, se supera el 50 % pese a una regresión
severa a la media. M se derivó del propio panel: es el salto de estado más
pequeño de la tabla de rangos del bloque 07 (la amplitud p50 pasa de 0,22 a
0,25). La idea es que **una señal real cuyo efecto no mueve ninguna casilla del
panel es, para este sistema, indistinguible del ruido**.

---

## 10. El presupuesto por lote

Cada trimestre admite como máximo **12 propuestas** y **2 familias nuevas**. Las
familias ya existentes en el catálogo no consumen esa segunda cuota.

Una variable consume presupuesto **en el momento en que pasa a `EN_TEST`**, no
al proponerse. Las que caen en `PENDIENTE_REVISION` antes de testearse no
consumen.

**Para qué sirve.** Es una defensa contra el dragado de datos por volumen: si
puedes testear cien variables al trimestre, alguna pasará por azar. Limitar el
número obliga a que cada propuesta sea deliberada.

**El detalle importante:** `filtro.py` **no se fía** del contador almacenado. Lo
recalcula contando entradas del registro y aborta si el valor derivado no
coincide con el guardado. La razón es que el contador vive fuera del array de
entradas, que es lo único que entra en la cadena de hashes — o sea, es editable
sin romper nada. Así que no se le da autoridad.

El conteo va por **id distinto**, no por entrada: una aclaración o una
transición de estado no suman otra vez. El lote histórico `v1-historico` está
exento.

---

## 11. Estados, sellados y la herencia de v1

La lista de estados es **cerrada**: ante una etiqueta que no esté en ella,
`filtro.py` aborta.

| Estado | Significado |
|---|---|
| `PROPUESTA` | Registrada, aún no testeada |
| `EN_TEST` | Consumiendo presupuesto, atravesando gates |
| `DESCARTADA_GATE_1/3/4` | Falló el gate correspondiente |
| `DESCARTADA_GATE_2` | **Ya no puede emitirse** (gate 2 dejó de vincular) |
| `PENDIENTE_REVISION` | Historia insuficiente |
| `RECHAZADA_PVALOR` | No superó el umbral BY del lote |
| `EN_CONFIRMACION` | En ventana forward de 5 trimestres |
| `CONFIRMADA` | Superó los 3 criterios forward |
| `RECHAZADA_FORWARD` | No superó alguno de los 3 |
| `SELLADA_V1` | Hallazgo heredado de v1, no se re-testea |
| `DESCARTADA_PREVIA` | Descartada antes de entrar en test |
| `NULO_V1` | Experimento v1 que no llegó a abrirse |
| `RETIRADA_EN_PROPUESTA` | Retirada antes de testearse |

`DESCARTADA_GATE_2` se conserva en la lista aunque ya no pueda emitirse, porque
el registro es append-only y hay entradas antiguas que lo usan. `filtro.py`
aborta si alguien intenta emitirlo hoy.

`RETIRADA_EN_PROPUESTA` lleva una declaración obligatoria: **no expresa ningún
juicio sobre la variable**, no es evidencia de ausencia de efecto, no es un
resultado de test y no puede citarse como tal.

### La herencia de v1

Si abres `registro.json` verás entradas con lote `v1-historico`. Son de un
protocolo anterior que **tenía sesgo de selección conocido y no corregido**. No
consumen presupuesto v2 y no se re-testean.

El caso a entender es `halving_ciclo`, en estado `SELLADA_V1`. Encontró retornos
**negativos** en la ventana de 18-24 meses tras el halving — es decir, lo
contrario de la narrativa habitual de rally— con p-valores entre 0,014 y 0,049.

Su estatus es deliberadamente ambiguo y está declarado como tal: se conserva por
su valor operativo y por trazabilidad histórica, **no como evidencia validada
bajo el protocolo v2**. Corre en `halving.py`, en silencio, y solo emerge en la
interfaz cuando la fecha se acerca a la ventana de riesgo. No se somete a v2 ni
se re-testea, porque hacerlo violaría la unicidad del test.

---

## 12. Cómo se enmienda la doctrina

La doctrina se modifica mediante **enmiendas numeradas**, registradas en
`meta.enmiendas` con su número, título, fecha y motivo. Van por la 34.

La versión del esquema (`2.8.0`) usa numeración semántica, pero **la doctrina no
define en ninguna parte qué distingue un cambio mayor de uno menor**. En la
práctica se ha movido el segundo número al añadir campos o reglas nuevas. Esto
es una observación sobre lo que ha ocurrido, no una regla escrita: **si necesitas
saber la regla, no está en `v2.json`.**

Lo que sí está claro es el principio de fondo, visible en las enmiendas 33 y 34,
que se declaran a sí mismas: *"Solo añade. No reescribe ningún texto previo."*

Las enmiendas recientes se escriben con cuidado sobre **cuándo** se escriben. La
33 dice: *"Encadenada antes de que exista ningún resultado del test de
`ssr_capstables`. Escrita después, no valdría nada."* Y también: *"Una enmienda
escrita antes del test que relajase cualquiera de esas cosas no sería una
enmienda sino una propuesta nueva."*

Un ejemplo de disciplina que conviene no perder: la enmienda 34 declaró un caso
concreto (un cambio en `filtro.py` posterior a un resultado) y **expresamente no
creó una regla general**, para no escribir una autorización a medida del caso que
la necesitaba. Si hace falta la regla general, se escribe aparte y en frío.

**Nunca se editan `registro.json` ni `v2.json` a mano.** Siempre mediante un
script de un solo uso que verifica los hashes antes de tocar nada.

---

## 13. Confirmado, estimado y supuesto

El sistema distingue tres cosas y las etiqueta. Ejemplos reales del propio
registro:

**Dato confirmado** — medido y verificable. La partición derivada de
`ssr_capstables`: 1252 días en cada bloque, 3,43 años cada uno, corte el
2023-03-31. Y el hash del snapshot de precio, verificado por `filtro.py` en cada
arranque.

**Dato estimado** — medido, pero con un método que tiene supuestos dentro. Las
cotas de peso de los 6 tokens no acreditados: 0,2523 % global, 0,1613 % en el
bloque 1. Se declararon **junto a** las cotas congeladas del protocolo (0,91 % y
0,26 %), sin sustituirlas: lo congelado sigue siendo el compromiso.

**Supuesto** — no observado, declarado como tal. Las cifras de potencia de los
gates de la sección 7: salen de un modelo sintético, no de datos reales, y la
doctrina lo dice con esas palabras.

Tres patrones que conviene reconocer, porque se repiten:

**Cuando lo medido no coincide con lo congelado, se declara, no se corrige.** Al
ejecutar el test de SSR, los días útiles derivados salieron 2504 y la ficha
decía 2503 — un día de diferencia por convención de borde. La regla aplicada:
*"Se declara el resultado derivado. No se corrige la ficha congelada."*

**Los defectos que ya no se pueden arreglar se declaran también.** La entrada 19
tiene un campo fuera de la lista cerrada, anterior a la enmienda 33. Aparece en
cada ejecución de `filtro.py` como incidencia, con la etiqueta *"declarada, no
corregible"*. No se limpia, porque limpiarla sería editar el pasado.

**Los problemas de los datos se declaran aunque incomoden.** DefiLlama no cubre
la cadena Omni, lo que contamina el arranque de la serie de stablecoins: 166 de
1252 días del bloque 1 (13,3 %), y un 39,8 % del tramo 1. La decisión fue
declarar y ejecutar igualmente, tras consultar a cinco modelos externos (cuatro
a favor, uno en contra), razonando que la contaminación puede impedir el paso de
los gates pero no falsear la estimación del efecto. Y se dejó escrito por
adelantado que esto **no daba derecho a re-proponer si los gates rechazaban**.
Que es exactamente lo que pasó.

---

## 14. Huecos declarados hoy

Cosas que el sistema promete y todavía no comprueba automáticamente. Están
declaradas en el propio registro, no descubiertas aquí:

1. **CERRADO.** Hashes de snapshot sin verificar. `filtro.py` en su versión
   2.9 verifica el CSV de la métrica contra `sha256_serie_metrica` y el
   artefacto bruto contra `sha256_snapshot_metrica`, este último mediante el
   nuevo argumento `--snapshot-metrica`. Antes solo se verificaba el snapshot
   de precio; ahora también estos dos.

2. **CERRADO.** La obligatoriedad de la enmienda 34 no se comprobaba.
   `filtro.py` 2.9 la automatiza —junto con la de la enmienda 35—, leyendo
   los campos, estados y cortes directamente de la doctrina, sin añadir
   constantes nuevas al código.

3. **REDUCIDO, NO CERRADO.** `requirements.txt` fija ahora `pandas==2.3.3` y
   `numpy==2.3.5`. Pero:
   - El intérprete de Python y las dependencias transitivas siguen sin fijar.
   - La fijación solo se ha podido **verificar** contra el arranque
     (`import`) y las fases 0-2, que no usan `pandas`. **No** se ha podido
     verificar contra el camino numérico, porque el lote está cerrado y
     `ssr_capstables` ya no es admisible a `EN_TEST` (unicidad del test).
   - **No** reconstruye las versiones con las que se ejecutó realmente la
     entrada 23: esas siguen siendo **desconocidas**.
   - La propia enmienda 35 lo dice así: *"la limitación se reduce, no
     desaparece"*. No se declara cerrado.

4. **PERMANECE, íntegro.** El alcance de `sha256_motor` es limitado y está
   declarado: cubre el fichero `filtro.py`, no el entorno ni las
   dependencias.

5. **Sin cambios.** N=30 tiene un cabo suelto documentado. El horizonte se
   justificó midiendo la persistencia de la *métrica continua* entre épocas.
   Desde la enmienda 18 los gates operan sobre la *máscara binaria*, así que
   esa justificación ya no describe exactamente lo que el protocolo hace. No
   se recalcula nada, porque `definicion_de_efecto` es inmutable. La
   enmienda 26 lo anotó expresamente *"para que el cabo suelto no se
   descubra como sorpresa dentro de dos años"*.

6. **Sin cambios.** El anti-truncamiento depende de Git. Un borrado del
   historial completo no es detectable desde dentro del repositorio.

7. **Sin cambios.** La numeración de versión del esquema no está definida en
   la doctrina (ver sección 12).

8. **Nuevo.** La enmienda 34 y la enmienda 35 nombran de forma distinta la
   misma lista de estados dentro de su bloque `obligatoriedad_condicional`:
   la 34 la llama `estados_de_resultado_de_test`, la 35 la llama
   `estados_que_lo_exigen`. `filtro.py` no codifica ninguno de los dos
   nombres: toma la única lista de cadenas que encuentra dentro de cada
   bloque `obligatoriedad_condicional`, y aborta si encuentra más de una.
   Funciona, pero es un parche de lectura, no una regla unificada. Queda
   anotado en `huecos_de_doctrina_detectados` de cada informe. Es candidato
   a una enmienda futura que armonice el nombre del campo; esa enmienda no
   se propone en este documento.

**Cabo suelto ya resuelto: "cuatro incidentes históricos" vs. "tres".** En una
versión anterior de este documento se habló de cuatro incidentes históricos,
mientras que la comprobación con `filtro.py --lote 2026-Q3 --solo-comprobar`
mostraba tres. Aclarado: eran cuatro **líneas de incidencia** repartidas en
**tres entradas** (la entrada 13 aparece dos veces, una por la enmienda 28 y
otra por la enmienda 29 parte 4). Con la doctrina 2.9.0 pasan a ser **cinco
líneas en cuatro entradas**: se suma la entrada 22, que está en `EN_TEST` sin
`sha256_serie_metrica`. Esa entrada queda por debajo del corte de la entrada
23, así que es una incidencia declarada, no un bloqueo.

---

## Estado a fecha de este documento

- Esquema **2.9.0**, **35 enmiendas** aplicadas, **23 entradas** en el
  registro, cadena válida.
- Lote **2026-Q3 cerrado**. Consumo: 1 de 12.
- `ssr_capstables` testeada y **rechazada en el gate 3** (entrada 23). No se
  re-propone, ni ella ni variantes.
- Ninguna variable en `EN_TEST` ni en `EN_CONFIRMACION`.
- Ninguna variable **`CONFIRMADA`** hasta la fecha.

Ese último punto es el resumen honesto del proyecto: el sistema lleva más
esfuerzo invertido en no engañarse que en encontrar señales, y hasta hoy no ha
validado ninguna. Es el resultado esperable de un protocolo diseñado para que
pasar sea difícil. Un sistema con estas reglas y una lista larga de variables
confirmadas sería más sospechoso que este.
