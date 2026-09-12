"""
Pruebas offline de la tool buscar_propiedades_alquiler usando el CSV de ejemplo.

No llaman al modelo ni a Google Sheets: validan la normalización de columnas,
el filtrado y el formato JSON que recibe el modelo.

Ejecutar desde src/agent-framework-agent-inmobiliaria/:
    .venv/bin/python tests/test_catalogo.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.google_sheets import CatalogoAlquileres, a_numero, crear_tool_buscar_propiedades, normalizar

BASE = Path(__file__).resolve().parent.parent

CONFIG_CSV = {
    "origen": "csv_local",
    "csv_local": {"ruta": "data/propiedades_alquiler_ejemplo.csv"},
    "cache_ttl_segundos": 60,
    "max_resultados": 5,
    "moneda_por_defecto": "PEN",
    "estados_disponibles": ["disponible", "libre", "si", "sí", "true", "1"],
}

# Esquema real de la hoja "Inmuebles en Alquiler - Alpha State V2" (Campinas, BRL).
CSV_ALPHA_STATE = """ID Inmueble,Tipo,Barrio,Dirección,Metros Cuadrados,Habitaciones,Baños,Cocheras,Alquiler Mensual (BRL),IPTU Mensual (BRL),Agua / SANASA,Estado Amoblado
BH-001,Casa,Cidade Universitária,Rua Doutor Ruy Vicente de Mello 1318 Casa 03,65,2,1,1,2350,58.83,Compartido (1/3),No Amoblado
BH-002,Departamento / Kitnet,Barão Geraldo,Rua Tranquillo Prosperi 383,35,1,1,0,1400,32.5,Incluido,Semi-Amoblado
BH-003,Casa,Jardim Santa Genebra,Rua Bento de Abreu 54,120,3,2,2,3800,110,Individual,No Amoblado
BH-004,Departamento,Cidade Universitária,Av. Romeu Tortima 420,50,1,1,1,1900,45,Condominio,Amoblado
"""
CONFIG_ALPHA_STATE = {
    "origen": "csv_local",
    "csv_local": {"ruta": "tests/_alpha_state_tmp.csv"},
    "max_resultados": 5,
    "moneda_por_defecto": "BRL",
    "zonas_ignoradas": ["Campinas", "Brasil"],
    "estados_disponibles": ["disponible"],
    "columnas": {
        "id": "ID Inmueble", "tipo": "Tipo", "distrito": "Barrio", "direccion": "Dirección",
        "dormitorios": "Habitaciones", "banos": "Baños", "area_m2": "Metros Cuadrados",
        "precio": "Alquiler Mensual (BRL)", "amoblado": "Estado Amoblado", "estacionamiento": "Cocheras",
    },
}


def test_normalizacion():
    assert normalizar(" Área m2 ") == "area_m2"
    assert a_numero("S/ 2,500.00") == 2500.0
    assert a_numero("") is None


def test_filtros():
    cat = CatalogoAlquileres(CONFIG_CSV, base_dir=Path(__file__).resolve().parent.parent)
    cat.verificar_configuracion()
    filas = cat.cargar()
    assert len(filas) == 12, len(filas)

    # Ordenado por precio; excluye AS-002 (2900) y AS-012 (local en USD: otra moneda).
    ids = [f["id"] for f in cat.buscar(distrito="miraflores", precio_max=2500)]
    assert ids == ["AS-010", "AS-001"], ids
    # Presupuesto en dólares: solo propiedades publicadas en USD.
    assert [f["id"] for f in cat.buscar(distrito="Miraflores", precio_max=2000, moneda="dólares")] == ["AS-012"]
    # Sin precio ni moneda no se filtra por moneda: aparecen ambas.
    assert len(cat.buscar(distrito="Miraflores")) == 4

    assert all(f["estado"].lower() != "alquilado" for f in cat.buscar())   # AS-009 excluido
    assert [f["id"] for f in cat.buscar(dormitorios_min=3, mascotas=True)] == ["AS-007", "AS-003", "AS-004"]
    assert [f["id"] for f in cat.buscar(amoblado=True, tipo="departamento")] == ["AS-006", "AS-002"]
    assert cat.buscar(distrito="Cusco") == []


def test_mapeo_columnas_alpha_state():
    ruta = BASE / "tests" / "_alpha_state_tmp.csv"
    ruta.write_text(CSV_ALPHA_STATE, encoding="utf-8")
    try:
        cat = CatalogoAlquileres(CONFIG_ALPHA_STATE, base_dir=BASE)
        filas = cat.cargar()
        assert len(filas) == 4
        f = {x["id"]: x for x in filas}
        assert f["BH-001"]["distrito"] == "Cidade Universitária" and f["BH-001"]["precio"] == 2350.0
        assert f["BH-001"]["moneda"] == "BRL" and f["BH-001"]["titulo"] == "Casa en Cidade Universitária"
        assert f["BH-001"]["amoblado"] is False and f["BH-004"]["amoblado"] is True
        assert f["BH-002"]["amoblado"] is True and f["BH-002"]["amoblado_detalle"] == "Semi-Amoblado"
        assert f["BH-001"]["iptu_mensual_(brl)"] == "58.83" and f["BH-002"]["agua_/_sanasa"] == "Incluido"
        # Sin columna de estado, todas se consideran disponibles; precio en reales por defecto.
        assert [x["id"] for x in cat.buscar(precio_max=2000)] == ["BH-002", "BH-004"]
        assert [x["id"] for x in cat.buscar(precio_max=2000, moneda="reales")] == ["BH-002", "BH-004"]
        assert cat.buscar(precio_max=2000, moneda="USD") == []
        assert [x["id"] for x in cat.buscar(distrito="cidade universitaria", amoblado=True)] == ["BH-004"]
        assert [x["id"] for x in cat.buscar(dormitorios_min=3)] == ["BH-003"]
        # La ciudad no es un barrio: se ignora como filtro.
        assert [x["id"] for x in cat.buscar(distrito="Campinas", dormitorios_min=3)] == ["BH-003"]
        # La hoja no tiene columna de mascotas: la tool debe avisarlo y no filtrar.
        assert cat.filtros_no_disponibles(mascotas=True, dormitorios_min=3) == ["mascotas"]
        salida = json.loads(crear_tool_buscar_propiedades(cat).func(dormitorios_min=3, mascotas=True))
        assert salida["total"] == 1 and "mascotas" in salida["aviso"]
    finally:
        ruta.unlink(missing_ok=True)


def test_tool_json():
    cat = CatalogoAlquileres(CONFIG_CSV, base_dir=Path(__file__).resolve().parent.parent)
    tool = crear_tool_buscar_propiedades(cat)
    assert tool.name == "buscar_propiedades_alquiler"
    params = tool.parameters()["properties"] if callable(getattr(tool, "parameters", None)) else tool.parameters["properties"]
    assert {"distrito", "precio_max", "moneda", "dormitorios_min", "tipo", "amoblado", "mascotas"} <= set(params), params
    salida = json.loads(tool.func(distrito="Barranco"))
    assert salida["total"] == 1 and salida["propiedades"][0]["id"] == "AS-006" and "aviso" not in salida


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            fn()
            print(f"✅ {nombre}")
    print("Todas las pruebas pasaron.")
