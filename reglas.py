"""
reglas.py - Nivel 1 del modulo de auto-mejora de Contexto-BTC.

Responsabilidad unica: custodiar las reglas blindadas, aplicarlas y dejar
constancia inmutable de cada experimento.

Este modulo NO decide que variables se prueban (eso es el Nivel 2, explorador.py)
ni como se calculan los p-valores (eso es filtro.py). Solo responde a:
  - Que reglas estan vigentes y estan intactas.
  - Cual es el umbral que le toca al siguiente test.
  - Que ha pasado historicamente, y bajo que version.

Sin dependencias externas: solo stdlib. Corre igual en local y en GitHub Actions.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone, date
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------

BASE = Path(os.environ.get("CONTEXTO_BTC_BASE", Path(__file__).resolve().parent))
DIR_REGLAS = BASE / "reglas"
DIR_EXPERIMENTOS = BASE / "experimentos"
MANIFIESTO = DIR_REGLAS / "MANIFIESTO.json"
REGISTRO = DIR_EXPERIMENTOS / "registro.jsonl"
DIR_PROPUESTAS = BASE / "propuestas_reglas"

ESTADOS = {
    "PROPUESTA", "RECHAZADA", "PENDIENTE_REVISION",
    "CANDIDATA", "CONFIRMADA", "RECHAZADA_EN_CONFIRMACION",
}
COLAS = {"descubrimiento", "revision"}


class ReglasError(Exception):
    """Fallo de integridad o de uso. Siempre detiene la ejecucion."""


# --------------------------------------------------------------------------
# Hashing e integridad
# --------------------------------------------------------------------------

def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _sha_fichero(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonico(d: dict) -> str:
    """Serializacion determinista: mismo dict -> mismo string -> mismo hash."""
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Carga de reglas
# --------------------------------------------------------------------------

def _manifiesto() -> dict:
    if not MANIFIESTO.exists():
        raise ReglasError(f"No existe el manifiesto: {MANIFIESTO}")
    return json.loads(MANIFIESTO.read_text(encoding="utf-8"))


def cargar(reglas_id: str) -> dict:
    """Carga una version de reglas verificando que no ha sido alterada."""
    man = _manifiesto()
    entradas = {v["id"]: v for v in man["versiones"]}
    if reglas_id not in entradas:
        raise ReglasError(f"Version de reglas desconocida: {reglas_id}")

    path = DIR_REGLAS / f"{reglas_id}.json"
    real = _sha_fichero(path)
    esperado = entradas[reglas_id]["sha256"]
    if real is None:
        raise ReglasError(f"Falta el fichero de reglas {path}")
    if real != esperado:
        raise ReglasError(
            f"INTEGRIDAD ROTA: {reglas_id}.json ha sido modificado despues de sellarse.\n"
            f"  esperado: {esperado}\n  real:     {real}\n"
            f"Las reglas selladas no se editan. Abre una version nueva."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def cargar_vigente() -> dict:
    """Carga la unica version con vigente_hasta == null."""
    man = _manifiesto()
    vigentes = [v["id"] for v in man["versiones"] if v.get("vigente_hasta") is None]
    if len(vigentes) != 1:
        raise ReglasError(
            f"Debe haber exactamente una version vigente, hay {len(vigentes)}: {vigentes}"
        )
    return cargar(vigentes[0])


# --------------------------------------------------------------------------
# SAFFRON  (Ramdas, Zrnic, Wainwright, Jordan 2018)
# --------------------------------------------------------------------------
# Implementacion propia en stdlib, verificada contra el paquete de referencia
# `online-fdr` 0.0.3 sobre 2000 p-valores aleatorios (coincidencia exacta).
# Se implementa aqui en lugar de importar la libreria para no anadir una
# dependencia externa a un modulo que debe correr sin fallos en CI durante anos.

_GAMMA_C = 0.4374901658   # normalizacion de sum_{j>=1} j^-1.6
_GAMMA_EXP = 1.6


def _gamma(j: int) -> float:
    """Secuencia gamma por defecto de SAFFRON. Devuelve 0 para j <= 0."""
    if j <= 0:
        return 0.0
    return _GAMMA_C / (j ** _GAMMA_EXP)


def _alpha_t(t: int, candidatos: list[bool], rechazos: list[int],
             q: float, w0: float, lam: float) -> float:
    """Umbral del test t (1-based) dado el estado de los t-1 anteriores."""
    if t == 1:
        return min(lam, (1 - lam) * _gamma(1) * w0)

    alpha = w0 * _gamma(t - sum(candidatos))

    if rechazos:
        k1 = rechazos[0]
        c1 = sum(candidatos[k1:])      # candidatos posteriores al 1er rechazo
        alpha += (q - w0) * _gamma(t - k1 - c1)

    for kj in rechazos[1:]:
        cj = sum(candidatos[kj:])
        alpha += q * _gamma(t - kj - cj)

    return min(lam, (1 - lam) * alpha)


def _recorrer(p_previos: list[float], q: float, w0: float, lam: float):
    """
    Reproduce en una sola pasada la secuencia completa de decisiones.

    El estado se DERIVA del historico, nunca se guarda mutable: asi es imposible
    que el umbral y el registro auditable se desincronicen.
    """
    candidatos: list[bool] = []
    rechazos: list[int] = []
    for i, p in enumerate(p_previos, start=1):
        a_i = _alpha_t(i, candidatos, rechazos, q, w0, lam)
        if p <= a_i:
            rechazos.append(i)
        candidatos.append(p <= lam)
    return candidatos, rechazos


def umbral_saffron(p_previos: list[float], q: float, w0: float, lam: float) -> float:
    """Umbral alfa_t para el siguiente test, dado el historico de la misma cola."""
    candidatos, rechazos = _recorrer(p_previos, q, w0, lam)
    return _alpha_t(len(p_previos) + 1, candidatos, rechazos, q, w0, lam)


# --------------------------------------------------------------------------
# Batch-BH  (Zrnic, Jiang, Ramdas, Jordan 2020 - The Power of Batching)
# --------------------------------------------------------------------------
# Alternativa por lotes. Los tests no llegan de uno en uno: llegan en lotes
# trimestrales, y aprovechar esa estructura da mas poder que tratarlos como
# una secuencia. A diferencia de SAFFRON, el presupuesto NO decae en los lotes
# sin descubrimientos: solo se gasta alfa cuando se rechaza algo.

def _bh(p_vals: list[float], alpha: float) -> tuple[int, float]:
    """
    Benjamini-Hochberg. Busca el MAYOR i con p_(i) <= alpha*i/n.
    Lineal a proposito: la condicion BH no es monotona y una busqueda binaria
    puede devolver un resultado incorrecto.
    """
    n = len(p_vals)
    if n == 0:
        return 0, 0.0
    orden = sorted(p_vals)
    k = 0
    for i in range(n, 0, -1):
        if orden[i - 1] <= alpha * i / n:
            k = i
            break
    return k, (alpha * k / n if k else 0.0)


def _batch_bh_recorrer(lotes: list[list[float]], q: float):
    """
    Reproduce la secuencia de lotes. Devuelve (decisiones_por_lote, alfas).
    Estado derivado del historico completo, como en SAFFRON.
    """
    r_s: list[int] = []        # rechazos por lote
    r_plus: list[int] = []     # rechazos maximos si un p-valor fuese 0
    alfas: list[float] = []
    decisiones: list[list[bool]] = []

    for t, lote in enumerate(lotes):
        n = len(lote)
        if n == 0:
            decisiones.append([]); r_s.append(0); r_plus.append(0); alfas.append(0.0)
            continue

        if t == 0:
            a_t = q * _gamma(1)
        else:
            total = sum(r_s)
            beta = 0.0
            for s in range(t):
                den = r_plus[s] + (total - r_s[s])
                if den > 0:
                    beta += alfas[s] * r_plus[s] / den
            gsum = sum(_gamma(i) for i in range(1, t + 2))
            a_t = max(0.0, (gsum * q - beta) * (n + total) / n)

        k, umbral = _bh(lote, a_t)

        rp = k
        for i in range(n):
            alterado = list(lote)
            alterado[i] = 0.0
            rp = max(rp, _bh(alterado, a_t)[0])

        decisiones.append([p <= umbral for p in lote])
        r_s.append(k); r_plus.append(rp); alfas.append(a_t)

    return decisiones, alfas


def decidir_lote_batch_bh(lotes_previos: list[list[float]],
                          lote_actual: list[float], q: float):
    """Decisiones del lote actual dados los lotes previos de la misma cola."""
    dec, alfas = _batch_bh_recorrer(list(lotes_previos) + [list(lote_actual)], q)
    return dec[-1], alfas[-1]


# --------------------------------------------------------------------------
# Batch-PRDS  (Zrnic et al. 2020, variante para dependencia positiva)
# --------------------------------------------------------------------------
# Motor por defecto. Batch-BH exige independencia de los p-valores dentro del
# lote, supuesto insostenible aqui: las variables candidatas comparten factores
# de mercado. Batch-PRDS extiende el control a dependencia positiva dentro del
# lote, manteniendo independencia entre lotes (trimestres distintos, razonable).

def _batch_prds_recorrer(lotes: list[list[float]], q: float):
    """Reproduce la secuencia de lotes. Devuelve (decisiones, alfas)."""
    decisiones: list[list[bool]] = []
    alfas: list[float] = []
    r_total = 0
    for t, lote in enumerate(lotes, start=1):
        n = len(lote)
        if n == 0:
            decisiones.append([]); alfas.append(0.0); continue
        a_t = q * _gamma(t) / n * (n + r_total)
        k, umbral = _bh(lote, a_t)
        r_total += k
        decisiones.append([p <= umbral for p in lote])
        alfas.append(a_t)
    return decisiones, alfas


def decidir_lote_batch_prds(lotes_previos: list[list[float]],
                            lote_actual: list[float], q: float):
    dec, alfas = _batch_prds_recorrer(list(lotes_previos) + [list(lote_actual)], q)
    return dec[-1], alfas[-1]


class Cola:
    """
    Estado de una cola, reconstruido desde el registro. Despacha al motor que
    fijen las reglas vigentes: SAFFRON (secuencial) o BATCH_BH (por lotes).
    """

    def __init__(self, nombre: str, reglas: dict, lotes_previos: list[list[float]]):
        if nombre not in COLAS:
            raise ReglasError(f"Cola desconocida: {nombre}")
        self.nombre = nombre
        self.reglas = reglas
        self.lotes = [list(l) for l in lotes_previos]
        sig = reglas["significacion"]
        self.metodo = sig["metodo"]
        self.q = sig["q"]
        self.lam = sig.get("lambda", 0.5)
        self.w0 = sig["q"] * sig.get("w0_fraccion_de_q", 0.5)
        self.presupuesto = reglas["colas"][nombre]["presupuesto_tests"]
        self.n_min_lote = reglas["significacion"].get("n_min_lote", 1)
        if self.metodo not in ("SAFFRON", "BATCH_BH", "BATCH_PRDS"):
            raise ReglasError(f"Motor no soportado: {self.metodo}")

    @property
    def p_previos(self) -> list[float]:
        return [p for l in self.lotes for p in l]

    @property
    def usados(self) -> int:
        return len(self.p_previos)

    @property
    def restantes(self) -> int:
        return self.presupuesto - self.usados

    def decidir_lote(self, p_valores: dict[str, float]) -> list[tuple[str, bool, float]]:
        """
        Decide un lote completo. Devuelve [(id, rechaza, umbral_aplicado), ...].
        El orden lo fija el llamante (evaluar_lote), siempre alfabetico.
        """
        for v in p_valores.values():
            if not 0.0 <= v <= 1.0:
                raise ReglasError(f"p-valor fuera de [0,1]: {v}")
        ids = sorted(p_valores)
        ps = [p_valores[i] for i in ids]

        if self.metodo in ("BATCH_BH", "BATCH_PRDS"):
            fn = (decidir_lote_batch_bh if self.metodo == "BATCH_BH"
                  else decidir_lote_batch_prds)
            dec, alfa_lote = fn(self.lotes, ps, self.q)
            # el umbral efectivo de BH es comun a todo el lote
            k = sum(dec)
            umbral = alfa_lote * k / len(ps) if k else 0.0
            return [(i, d, umbral) for i, d in zip(ids, dec)]

        # SAFFRON: secuencial dentro del lote
        acumulado = list(self.p_previos)
        out = []
        for i, p in zip(ids, ps):
            a = umbral_saffron(acumulado, self.q, self.w0, self.lam)
            out.append((i, p <= a, a))
            acumulado.append(p)
        return out

    def umbral_orientativo(self) -> float:
        """Solo informativo (estado_presupuesto). No decide nada."""
        if self.metodo == "SAFFRON":
            return umbral_saffron(self.p_previos, self.q, self.w0, self.lam)
        rec = (_batch_bh_recorrer if self.metodo == "BATCH_BH"
               else _batch_prds_recorrer)
        _, alfas = rec(self.lotes + [[1.0]], self.q)
        return alfas[-1]


# --------------------------------------------------------------------------
# Registro append-only encadenado
# --------------------------------------------------------------------------

def _leer_registro() -> list[dict]:
    if not REGISTRO.exists():
        return []
    lineas = [l for l in REGISTRO.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lineas]


def _hash_entrada(entrada: dict) -> str:
    cuerpo = {k: v for k, v in entrada.items() if k != "hash"}
    return _sha(_canonico(cuerpo))


def sellar(datos_sha256: str | None = None, ruta_filtro: str = "filtro.py") -> dict:
    """
    Bloque de sello de un experimento. Cuatro hashes, porque hay cuatro cosas
    que pueden cambiar por debajo sin avisar:
      reglas  -> alguien edito el criterio
      filtro  -> el mismo criterio aplicado por otro codigo no es el mismo test
      datos   -> la fuente reviso el historico y el resultado ya no es reproducible
      commit  -> ancla al repositorio
    """
    man = _manifiesto()
    vig = [v for v in man["versiones"] if v.get("vigente_hasta") is None][0]
    return {
        "reglas_id": vig["id"],
        "reglas_sha256": vig["sha256"],
        "filtro_sha256": _sha_fichero(BASE / ruta_filtro),
        "datos_sha256": datos_sha256,
        "commit": os.environ.get("GITHUB_SHA"),
        "fecha_utc": _ahora(),
    }


def registrar(entrada: dict) -> dict:
    """Anade una linea al registro, encadenada a la anterior. Nunca sobrescribe."""
    previas = _leer_registro()
    entrada = dict(entrada)
    entrada["n"] = len(previas) + 1
    entrada["hash_previo"] = previas[-1]["hash"] if previas else None
    entrada["hash"] = _hash_entrada(entrada)

    DIR_EXPERIMENTOS.mkdir(parents=True, exist_ok=True)
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(_canonico(entrada) + "\n")
    return entrada


def verificar_integridad() -> dict:
    """
    Comprueba manifiesto + cadena del registro. Devuelve informe.
    Debe llamarse al principio de cualquier ejecucion automatica.
    """
    problemas: list[str] = []
    man = _manifiesto()

    for v in man["versiones"]:
        real = _sha_fichero(DIR_REGLAS / f"{v['id']}.json")
        if real is None:
            problemas.append(f"falta reglas/{v['id']}.json")
        elif real != v["sha256"]:
            problemas.append(f"reglas/{v['id']}.json ALTERADO tras sellarse")

    vigentes = [v["id"] for v in man["versiones"] if v.get("vigente_hasta") is None]
    if len(vigentes) != 1:
        problemas.append(f"versiones vigentes simultaneas: {vigentes}")

    previo = None
    for e in _leer_registro():
        if e.get("hash_previo") != previo:
            problemas.append(f"cadena rota en experimento n={e.get('n')}")
        if _hash_entrada(e) != e.get("hash"):
            problemas.append(f"experimento n={e.get('n')} ALTERADO")
        previo = e.get("hash")

    return {"ok": not problemas, "problemas": problemas,
            "n_experimentos": len(_leer_registro())}


# --------------------------------------------------------------------------
# Consulta de historial
# --------------------------------------------------------------------------

def historial(variable: str | None = None) -> dict:
    """
    Historial agrupado POR VERSION DE REGLAS, nunca mezclado.
    Comparar resultados obtenidos bajo criterios distintos es exactamente el
    error que este modulo existe para impedir.
    """
    por_version: dict[str, list[dict]] = {}
    for e in _leer_registro():
        if variable and e.get("id_candidata") != variable:
            continue
        vid = e.get("sello", {}).get("reglas_id", "?")
        por_version.setdefault(vid, []).append(e)

    aviso = None
    if len(por_version) > 1:
        aviso = ("AVISO: hay resultados bajo mas de una version de reglas. "
                 "No son directamente comparables entre si.")
    return {"variable": variable, "por_version": por_version, "aviso": aviso}


def estado(id_candidata: str) -> str | None:
    """Ultimo estado conocido de una variable."""
    ultimo = None
    for e in _leer_registro():
        if e.get("id_candidata") == id_candidata and e.get("estado"):
            ultimo = e["estado"]
    return ultimo


def _lotes_previos(nombre_cola: str, reglas_id: str) -> list[list[float]]:
    """p-valores de esa cola bajo esa version, agrupados por lote y en orden."""
    lotes: dict[str, list[float]] = {}
    orden: list[str] = []
    for e in _leer_registro():
        if (e.get("cola") != nombre_cola or e.get("p_valor") is None
                or e.get("sello", {}).get("reglas_id") != reglas_id):
            continue
        lid = e.get("lote_id") or f"_suelto_{e['n']}"
        if lid not in lotes:
            lotes[lid] = []; orden.append(lid)
        lotes[lid].append(e["p_valor"])
    return [lotes[l] for l in orden]


def cola(nombre: str, reglas: dict | None = None) -> Cola:
    reglas = reglas or cargar_vigente()
    return Cola(nombre, reglas, _lotes_previos(nombre, reglas["id"]))


def estado_presupuesto() -> dict:
    r = cargar_vigente()
    out = {"reglas_id": r["id"], "colas": {}}
    total = 0
    for n in ("descubrimiento", "revision"):
        c = cola(n, r)
        out["colas"][n] = {"usados": c.usados, "presupuesto": c.presupuesto,
                           "restantes": c.restantes,
                           "umbral_orientativo": round(c.umbral_orientativo(), 6)}
        total += c.usados
    out["total_usados"] = total
    out["total_presupuesto"] = r["presupuesto_version"]["total_tests"]
    out["version_agotada"] = total >= out["total_presupuesto"]
    return out


# --------------------------------------------------------------------------
# API de alto nivel: lo que llama filtro.py / explorador.py
# --------------------------------------------------------------------------

def evaluar_lote(p_valores: dict[str, float], nombre_cola: str,
                 datos_sha256: str | None = None,
                 metadatos: dict | None = None,
                 lote_id: str | None = None) -> list[dict]:
    """
    Evalua un lote trimestral completo y lo registra.

    p_valores: {id_candidata: p_valor} de las variables que superaron TODOS los
               gates previos de filtro.py. Las descartadas antes no se pasan
               aqui: no consumen presupuesto alfa porque nunca produjeron p-valor.

    El orden de ejecucion lo fija ESTE modulo (alfabetico por id), no quien
    llama. Ordenar por p-valor destruiria la garantia de SAFFRON, y esa es una
    forma de romperlo demasiado facil como para dejarla en manos del llamante.
    """
    integridad = verificar_integridad()
    if not integridad["ok"]:
        raise ReglasError(f"Integridad comprometida: {integridad['problemas']}")

    reglas = cargar_vigente()
    if reglas["orden_tests"]["criterio"] != "alfabetico_por_id_candidata":
        raise ReglasError("Criterio de orden no soportado por esta implementacion.")

    c = cola(nombre_cola, reglas)
    ids = sorted(p_valores)
    if len(ids) < c.n_min_lote:
        raise ReglasError(
            f"Lote de {len(ids)} variables, minimo {c.n_min_lote}. Los lotes "
            f"pequenos degradan el control del FDR: acumula hasta el minimo o "
            f"marca las variables como PENDIENTE_REVISION."
        )
    if len(ids) > c.restantes:
        raise ReglasError(
            f"Presupuesto insuficiente en cola '{nombre_cola}': quedan "
            f"{c.restantes} tests y el lote trae {len(ids)}. "
            f"La version {reglas['id']} debe cerrarse (decision humana)."
        )

    sello = sellar(datos_sha256)
    lote_id = lote_id or f"{nombre_cola}-{sello['fecha_utc'][:10]}"
    decisiones = c.decidir_lote(p_valores)

    resultados = []
    for cid, rechaza, umbral in decisiones:
        resultados.append(registrar({
            "tipo": "test",
            "id_candidata": cid,
            "cola": nombre_cola,
            "lote_id": lote_id,
            "motor": c.metodo,
            "p_valor": p_valores[cid],
            "umbral_aplicado": umbral,
            "estado": "CANDIDATA" if rechaza else "RECHAZADA",
            "sello": sello,
            "metadatos": (metadatos or {}).get(cid, {}),
        }))
    return resultados


def marcar_pendiente(id_candidata: str, motivo: str,
                     n_obs: int | None = None,
                     n_episodios: int | None = None) -> dict:
    """
    PENDIENTE_REVISION: no alcanza los minimos de datos. NO consume presupuesto
    alfa, porque no se ha testeado nada. Falta de datos no es evidencia de
    ausencia de senal.
    """
    return registrar({
        "tipo": "pendiente",
        "id_candidata": id_candidata,
        "cola": None,
        "p_valor": None,
        "estado": "PENDIENTE_REVISION",
        "motivo": motivo,
        "n_observaciones": n_obs,
        "n_episodios": n_episodios,
        "sello": sellar(),
    })


def registrar_confirmacion(id_candidata: str, trimestres: list[dict]) -> dict:
    """
    Aplica la confirmacion forward a una CANDIDATA.

    trimestres: [{"periodo": "2026Q4", "signo": 1, "magnitud_rel": 0.82}, ...]
    Los datos deben ser POSTERIORES a la fecha en que la variable fue propuesta.
    Esa es toda la proteccion: son datos que no existian cuando el Nivel 2 la vio.
    """
    r = cargar_vigente()
    conf = r["confirmacion_forward"]
    if estado(id_candidata) != "CANDIDATA":
        raise ReglasError(
            f"{id_candidata} no esta en estado CANDIDATA (esta en {estado(id_candidata)})."
        )

    n_req = conf["trimestres_requeridos"]
    if len(trimestres) < n_req:
        return registrar({
            "tipo": "confirmacion_parcial",
            "id_candidata": id_candidata, "estado": "CANDIDATA",
            "trimestres_acumulados": len(trimestres), "requeridos": n_req,
            "trimestres": trimestres, "sello": sellar(),
        })

    usados = trimestres[:n_req]
    signos = {t["signo"] for t in usados}
    mag_ok = all(t["magnitud_rel"] >= conf["criterio_magnitud_min_fraccion"] for t in usados)
    ok = len(signos) == 1 and mag_ok

    return registrar({
        "tipo": "confirmacion",
        "id_candidata": id_candidata,
        "estado": "CONFIRMADA" if ok else conf["al_fallar"],
        "signo_estable": len(signos) == 1,
        "magnitud_ok": mag_ok,
        "trimestres": usados,
        "sello": sellar(),
    })


def confirmadas() -> list[str]:
    """Unicas variables que pueden aparecer en el dashboard."""
    return sorted({e["id_candidata"] for e in _leer_registro()
                   if e.get("estado") == "CONFIRMADA"}
                  - {e["id_candidata"] for e in _leer_registro()
                     if e.get("estado") == "RECHAZADA_EN_CONFIRMACION"})


def proponer_cambio_reglas(motivo: str, cambio: dict) -> Path:
    """
    UNICA via por la que el sistema puede tocar el Nivel 1: dejar una propuesta.
    Nunca escribe en reglas/. Si el explorador concluye que una regla deberia
    cambiar, deja el fichero y sigue corriendo con las reglas vigentes.
    """
    DIR_PROPUESTAS.mkdir(parents=True, exist_ok=True)
    p = DIR_PROPUESTAS / f"propuesta_{date.today().isoformat()}_{_sha(motivo)[:8]}.json"
    p.write_text(json.dumps({
        "fecha": _ahora(), "reglas_vigentes": cargar_vigente()["id"],
        "motivo": motivo, "cambio_propuesto": cambio,
        "nota": "Requiere decision humana. Abrir version nueva, nunca editar la vigente.",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return p
