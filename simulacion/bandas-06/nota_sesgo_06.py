"""Script de un solo uso (2026-09-23): anade nota de sesgo conservador al bloque 06 de app.py.
Decision derivada de la prueba prerregistrada prueba_bandas.py (resultado e1c35052...)."""
import hashlib, sys
RUTA = sys.argv[1] if len(sys.argv) > 1 else "app.py"
ESPERADO = "6b859d2b2a65563c"
src = open(RUTA, encoding="utf-8").read()
h = hashlib.sha256(src.encode("utf-8")).hexdigest()
assert h.startswith(ESPERADO), f"app.py inesperado: {h}"
ANCLA = 'st.table(tabla_rango.set_index("Frecuencia"))\n'
assert src.count(ANCLA) == 1, "ancla no unica"
NOTA = ANCLA + '''
# Nota fijada por la prueba prerregistrada del 2026-09-23 (prueba_bandas.py):
# ningun metodo alternativo mejoro la tabla actual, por lo que se mantiene y
# se avisa del sesgo conservador observado desde 2021.
st.info(
    "**Sesgo conservador desde 2021.** Con la misma volatilidad, el precio ha "
    "recorrido menos terreno que antes. La banda del 75% acertó entre el 84% y "
    "el 92% de las veces, y la del 95% casi siempre. Las bandas probablemente "
    "exageran el rango y los tamaños del bloque 07 quedan del lado prudente. "
    "Se probaron alternativas y ninguna fue mejor de forma consistente.",
    icon="⚠️",
)
'''
nuevo = src.replace(ANCLA, NOTA)
open(RUTA, "w", encoding="utf-8").write(nuevo)
print("OK", hashlib.sha256(nuevo.encode("utf-8")).hexdigest(), len(nuevo.encode("utf-8")))
