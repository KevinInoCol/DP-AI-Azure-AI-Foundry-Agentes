"""
Tool de lectura del catálogo de alquileres de Alpha State en Google Sheets.

La inmobiliaria mantiene sus propiedades en alquiler en una hoja de Google
Sheets. Este módulo la descarga, normaliza las columnas y expone una tool
`buscar_propiedades_alquiler` que el modelo llama con filtros (distrito,
precio máximo, dormitorios, tipo, amoblado, mascotas).

Dos formas de leer la hoja, elegidas en model_config/model_config.yaml:
- Hoja pública ("cualquier persona con el enlace" puede ver): se descarga el
  CSV exportado, sin credenciales. Solo hace falta GOOGLE_SHEETS_ID.
- Hoja privada: define GOOGLE_SERVICE_ACCOUNT_JSON con el contenido del JSON de
  una cuenta de servicio y comparte la hoja con su email; se usa gspread.
Para demos sin internet u orígenes de prueba, `origen: csv_local` lee un CSV.

Campos canónicos que usa la tool:
    id, titulo, tipo, distrito, direccion, dormitorios, banos, area_m2, precio,
    moneda, amoblado, mascotas, estacionamiento, estado, descripcion, link
Si la hoja usa otras cabeceras (por ejemplo "Barrio", "Habitaciones",
"Alquiler Mensual (BRL)"), se indica la correspondencia en `columnas:` de
model_config.yaml. Las columnas no mapeadas se devuelven igualmente al modelo
(por ejemplo IPTU o condiciones del agua) con su cabecera normalizada.
"""

import csv
import io
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Annotated, Any

import requests
from agent_framework import FunctionTool, tool
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

URL_EXPORT_CSV = "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
TIMEOUT_SEGUNDOS = 15
COLUMNAS_BOOLEANAS = ("amoblado", "mascotas")
COLUMNAS_NUMERICAS = ("dormitorios", "banos", "area_m2", "precio", "estacionamiento")
VALORES_VERDADEROS = {"si", "sí", "s", "true", "1", "x", "yes"}
MONEDA_POR_DEFECTO = "BRL"
ALIAS_MONEDA = {
    "reales": "BRL", "real": "BRL", "reais": "BRL", "r$": "BRL", "brl": "BRL",
    "soles": "PEN", "sol": "PEN", "s/": "PEN", "pen": "PEN",
    "dolares": "USD", "dólares": "USD", "usd": "USD", "us$": "USD", "$": "USD",
    "euros": "EUR", "euro": "EUR", "€": "EUR", "eur": "EUR",
}
CAMPOS_CANONICOS = (
    "id", "titulo", "tipo", "distrito", "direccion", "dormitorios", "banos", "area_m2", "precio",
    "moneda", "amoblado", "mascotas", "estacionamiento", "estado", "descripcion", "link",
)
VALORES_FALSOS = {"no", "false", "0", "n", "ninguno", "ninguna"}


def normalizar(texto: Any) -> str:
    """Minúsculas, sin acentos y sin espacios sobrantes; para comparar cabeceras y valores."""
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", "_", texto)


def a_numero(valor: Any) -> float | None:
    """'S/ 2,500.00' -> 2500.0; vacío o no numérico -> None."""
    if valor is None:
        return None
    limpio = re.sub(r"[^\d.,-]", "", str(valor))
    if not limpio:
        return None
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(",", "")
    elif "," in limpio:
        limpio = limpio.replace(",", ".") if limpio.count(",") == 1 and len(limpio.split(",")[1]) <= 2 else limpio.replace(",", "")
    try:
        return float(limpio)
    except ValueError:
        return None


def normalizar_moneda(valor: Any, por_defecto: str = MONEDA_POR_DEFECTO) -> str:
    """'reales' / 'R$' -> 'BRL'; 'soles' -> 'PEN'; 'dólares' -> 'USD'; otro código se devuelve en mayúsculas."""
    texto = str(valor or "").strip().lower()
    return ALIAS_MONEDA.get(texto, texto.upper() or por_defecto)


def a_booleano(valor: Any) -> bool | None:
    """'si' / 'Amoblado' / 'Semi-Amoblado' -> True; 'no' / 'No Amoblado' / 'Sin ...' -> False; vacío -> None."""
    texto = normalizar(valor)
    if not texto:
        return None
    if texto in VALORES_VERDADEROS:
        return True
    if texto in VALORES_FALSOS or texto.startswith(("no_", "no-", "sin_", "sin-")):
        return False
    return True  # cualquier otro texto descriptivo ("Amoblado", "Semi-Amoblado", "Acepta gatos") cuenta como sí


class CatalogoAlquileres:
    """Carga (con caché) y filtra las propiedades en alquiler."""

    def __init__(self, config: dict[str, Any], base_dir: Path | None = None) -> None:
        self.config = config
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent
        self.cache_ttl = int(config.get("cache_ttl_segundos", 60))
        self.max_resultados = int(config.get("max_resultados", 5))
        self.estados_disponibles = {normalizar(e) for e in config.get("estados_disponibles", [])}
        self.moneda_por_defecto = normalizar_moneda(config.get("moneda_por_defecto"), MONEDA_POR_DEFECTO)
        # Zonas amplias (la ciudad, el estado, el país) que no son barrio: si el modelo las pasa
        # como distrito, se ignora el filtro en lugar de devolver cero resultados.
        self.zonas_ignoradas = {normalizar(z) for z in config.get("zonas_ignoradas", [])}
        # campo canónico -> cabecera normalizada de la hoja (si no se mapea, se busca por el nombre canónico)
        self.columnas = {
            campo: normalizar(cabecera)
            for campo, cabecera in (config.get("columnas") or {}).items()
            if cabecera
        }
        self._filas: list[dict[str, Any]] | None = None
        self._cargado_en = 0.0

    # ---------- configuración ----------

    def verificar_configuracion(self) -> None:
        """Falla rápido si el origen elegido no tiene lo necesario."""
        origen = self.config.get("origen", "google_sheets")
        if origen == "google_sheets":
            if not self._spreadsheet_id():
                var = self.config["google_sheets"].get("spreadsheet_id_env", "GOOGLE_SHEETS_ID")
                raise RuntimeError(
                    f"La tool buscar_propiedades_alquiler necesita la variable {var} "
                    "(ID de la hoja de Google Sheets) o cambia 'origen' a csv_local en model_config.yaml."
                )
        elif origen == "csv_local":
            if not self._ruta_csv_local().exists():
                raise RuntimeError(f"No existe el CSV local {self._ruta_csv_local()}")
        else:
            raise RuntimeError(f"Origen desconocido para la tool: {origen}")

    def _spreadsheet_id(self) -> str | None:
        var = self.config.get("google_sheets", {}).get("spreadsheet_id_env", "GOOGLE_SHEETS_ID")
        return os.getenv(var) or GOOGLE_SHEETS_ID

    def _service_account_json(self) -> str | None:
        var = self.config.get("google_sheets", {}).get("service_account_json_env", "GOOGLE_SERVICE_ACCOUNT_JSON")
        return os.getenv(var) or GOOGLE_SERVICE_ACCOUNT_JSON

    def _ruta_csv_local(self) -> Path:
        ruta = Path(self.config.get("csv_local", {}).get("ruta", "data/propiedades_alquiler_ejemplo.csv"))
        return ruta if ruta.is_absolute() else self.base_dir / ruta

    # ---------- carga ----------

    def _descargar_csv_publico(self) -> str:
        gid = self.config.get("google_sheets", {}).get("gid", 0)
        url = URL_EXPORT_CSV.format(spreadsheet_id=self._spreadsheet_id(), gid=gid)
        respuesta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        if respuesta.status_code != 200 or "text/csv" not in respuesta.headers.get("content-type", ""):
            raise RuntimeError(
                "No se pudo leer la hoja de Google Sheets como pública "
                f"(HTTP {respuesta.status_code}). Compártela como 'cualquier persona con el enlace' "
                "o configura GOOGLE_SERVICE_ACCOUNT_JSON."
            )
        return respuesta.content.decode("utf-8-sig")

    def _leer_con_cuenta_de_servicio(self) -> list[dict[str, Any]]:
        import gspread  # import perezoso: solo hace falta con hoja privada

        credenciales = json.loads(self._service_account_json())
        cliente = gspread.service_account_from_dict(credenciales)
        hoja = cliente.open_by_key(self._spreadsheet_id())
        nombre = self.config.get("google_sheets", {}).get("worksheet")
        pestana = hoja.worksheet(nombre) if nombre else hoja.get_worksheet(0)
        return pestana.get_all_records()

    def _leer_filas_crudas(self) -> list[dict[str, Any]]:
        origen = self.config.get("origen", "google_sheets")
        if origen == "csv_local":
            texto = self._ruta_csv_local().read_text(encoding="utf-8-sig")
            return list(csv.DictReader(io.StringIO(texto)))
        if self._service_account_json():
            return self._leer_con_cuenta_de_servicio()
        return list(csv.DictReader(io.StringIO(self._descargar_csv_publico())))

    def _normalizar_fila(self, fila: dict[str, Any]) -> dict[str, Any]:
        """Convierte una fila de la hoja a los campos canónicos + columnas extra."""
        crudos = {normalizar(k): v for k, v in fila.items() if normalizar(k)}
        limpia: dict[str, Any] = {}
        consumidas: set[str] = set()

        for campo in CAMPOS_CANONICOS:
            cabecera = self.columnas.get(campo, campo)
            if cabecera not in crudos:
                continue
            consumidas.add(cabecera)
            valor = crudos[cabecera]
            if campo in COLUMNAS_NUMERICAS:
                limpia[campo] = a_numero(valor)
            elif campo in COLUMNAS_BOOLEANAS:
                limpia[campo] = a_booleano(valor)
                texto = str(valor).strip() if valor is not None else ""
                if texto and normalizar(texto) not in VALORES_VERDADEROS | VALORES_FALSOS:
                    limpia[f"{campo}_detalle"] = texto  # p. ej. "Semi-Amoblado"
            else:
                limpia[campo] = str(valor).strip() if valor is not None else ""

        # Columnas de la hoja que no corresponden a ningún campo canónico: se pasan tal cual.
        for cabecera, valor in crudos.items():
            if cabecera not in consumidas and cabecera not in limpia:
                limpia[cabecera] = str(valor).strip() if valor is not None else ""

        limpia.setdefault("moneda", self.moneda_por_defecto)
        limpia["moneda"] = normalizar_moneda(limpia["moneda"], self.moneda_por_defecto)
        if not limpia.get("titulo"):
            partes = [limpia.get("tipo"), limpia.get("distrito")]
            limpia["titulo"] = " en ".join(str(x) for x in partes if x) or limpia.get("id", "Propiedad")
        return limpia

    def cargar(self, forzar: bool = False) -> list[dict[str, Any]]:
        """Devuelve las filas normalizadas, releyendo la hoja si la caché expiró."""
        if forzar or self._filas is None or time.time() - self._cargado_en > self.cache_ttl:
            self._filas = [self._normalizar_fila(f) for f in self._leer_filas_crudas()]
            self._cargado_en = time.time()
        return self._filas

    # ---------- búsqueda ----------

    def campos_presentes(self) -> set[str]:
        """Campos canónicos que realmente existen en la hoja (tras el mapeo)."""
        filas = self.cargar()
        if not filas:
            return set()
        return {c for c in CAMPOS_CANONICOS if any(c in f and f[c] not in (None, "") for f in filas)}

    def filtros_no_disponibles(self, **filtros: Any) -> list[str]:
        """Filtros que el cliente pidió pero cuya columna no existe en la hoja."""
        presentes = self.campos_presentes()
        mapa = {"distrito": "distrito", "precio_max": "precio", "dormitorios_min": "dormitorios",
                "tipo": "tipo", "amoblado": "amoblado", "mascotas": "mascotas"}
        return [f for f, campo in mapa.items() if filtros.get(f) is not None and campo not in presentes]

    def buscar(
        self,
        distrito: str | None = None,
        precio_max: float | None = None,
        moneda: str | None = None,
        dormitorios_min: int | None = None,
        tipo: str | None = None,
        amoblado: bool | None = None,
        mascotas: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Filtra el catálogo. El precio solo se compara con filas en la misma moneda
        (por defecto PEN), para no mezclar soles con dólares."""
        moneda_filtro = normalizar_moneda(moneda, self.moneda_por_defecto) if (moneda or precio_max is not None) else None
        if distrito and normalizar(distrito) in self.zonas_ignoradas:
            distrito = None  # "Campinas" es la ciudad, no un barrio
        resultados = []
        for fila in self.cargar():
            estado = normalizar(fila.get("estado"))
            if self.estados_disponibles and estado and estado not in self.estados_disponibles:
                continue
            if distrito and normalizar(distrito) not in normalizar(fila.get("distrito")):
                continue
            if tipo and normalizar(tipo) not in normalizar(fila.get("tipo")):
                continue
            if moneda_filtro and fila.get("moneda") != moneda_filtro:
                continue
            if precio_max is not None and (fila.get("precio") is None or fila["precio"] > precio_max):
                continue
            if dormitorios_min is not None and (fila.get("dormitorios") or 0) < dormitorios_min:
                continue
            if amoblado is not None and fila.get("amoblado") is not None and fila["amoblado"] != amoblado:
                continue
            if mascotas is not None and fila.get("mascotas") is not None and fila["mascotas"] != mascotas:
                continue
            resultados.append(fila)

        resultados.sort(key=lambda f: (f.get("precio") is None, f.get("precio") or 0))
        return resultados[: self.max_resultados]


def crear_tool_buscar_propiedades(catalogo: CatalogoAlquileres) -> FunctionTool:
    """Envuelve el catálogo en la FunctionTool `buscar_propiedades_alquiler` que ve el modelo."""

    @tool
    def buscar_propiedades_alquiler(
        distrito: Annotated[str | None, "Distrito o zona de interés, por ejemplo 'Miraflores'. Omitir para no filtrar."] = None,
        precio_max: Annotated[float | None, "Precio mensual máximo. Se compara solo con propiedades publicadas en la moneda indicada en 'moneda'. Omitir para no filtrar."] = None,
        moneda: Annotated[str | None, "Código de la moneda del presupuesto del cliente: 'BRL' (reales, moneda por defecto del catálogo), 'USD', 'PEN', 'EUR'. Solo se devuelven propiedades publicadas en esa moneda."] = None,
        dormitorios_min: Annotated[int | None, "Número mínimo de dormitorios. Omitir para no filtrar."] = None,
        tipo: Annotated[str | None, "Tipo de inmueble: departamento, casa, oficina, local, terreno. Omitir para no filtrar."] = None,
        amoblado: Annotated[bool | None, "true si el cliente necesita que esté amoblado, false si lo prefiere sin amoblar. Omitir si es indiferente."] = None,
        mascotas: Annotated[bool | None, "true si el cliente tiene mascotas y necesita que las acepten. Omitir si no aplica."] = None,
    ) -> str:
        """Busca propiedades EN ALQUILER disponibles en el catálogo de Alpha State (hoja de Google Sheets).
        Devuelve un JSON con hasta 5 propiedades que cumplen los filtros, ordenadas por precio (solo de la moneda
        indicada, reales BRL por defecto), con id, título,
        tipo, distrito/barrio, dirección, dormitorios, baños, área, precio, moneda, amoblado, estacionamiento y
        cualquier columna adicional de la hoja (por ejemplo IPTU mensual o condiciones del agua).
        Úsala siempre que el cliente pregunte por propiedades, opciones o disponibilidad en alquiler.
        Si devuelve una lista vacía, no hay propiedades que cumplan esos filtros. Si incluye "aviso", el catálogo
        no registra alguno de los criterios pedidos (por ejemplo mascotas) y no debes afirmar que se cumplen."""
        try:
            propiedades = catalogo.buscar(
                distrito=distrito,
                precio_max=precio_max,
                moneda=moneda,
                dormitorios_min=dormitorios_min,
                tipo=tipo,
                amoblado=amoblado,
                mascotas=mascotas,
            )
        except Exception as exc:  # el modelo debe poder explicar el fallo al cliente
            return json.dumps({"error": f"No se pudo consultar el catálogo: {exc}"}, ensure_ascii=False)

        salida: dict[str, Any] = {"total": len(propiedades), "propiedades": propiedades}
        no_disponibles = catalogo.filtros_no_disponibles(
            distrito=distrito, precio_max=precio_max, dormitorios_min=dormitorios_min,
            tipo=tipo, amoblado=amoblado, mascotas=mascotas,
        )
        if no_disponibles:
            salida["aviso"] = (
                "El catálogo NO registra estos criterios, así que no se filtró por ellos: "
                + ", ".join(no_disponibles)
                + ". Indica al cliente que un asesor lo confirmará; no afirmes que las propiedades los cumplen."
            )
        return json.dumps(salida, ensure_ascii=False, default=str)

    return buscar_propiedades_alquiler
