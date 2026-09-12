"""
Crea la base de conocimiento de Alpha State en Foundry IQ (Azure AI Search).

Pasos que ejecuta, todos idempotentes (PUT):
1. Knowledge source `azureBlob` que apunta al contenedor con el PDF de políticas
   y FAQ. AI Search crea por dentro el índice, el skillset (chunking +
   embeddings con text-embedding-3-small) y el indexador.
2. Knowledge base que agrupa la fuente y usa gpt-5-mini para planificar
   consultas (agentic retrieval), con instrucciones en español.
3. Conexión "Azure AI Search" en el proyecto de Foundry (categoría
   CognitiveSearch, clave de API) para que la base aparezca en Compilación →
   Conocimiento del portal.
4. Espera a que termine la indexación y hace una consulta de prueba.

El servicio de búsqueda es de nivel Free (sin identidad administrada), por eso
las conexiones a Storage y a los modelos usan claves. Las claves se obtienen en
runtime con Azure CLI y nunca se imprimen ni se guardan en disco.

Requisitos: `az login` en el tenant correcto; el usuario debe ser Owner (o
Search Service Contributor + Search Index Data Contributor) del servicio.

Ejecutar desde src/agent-framework-agent-inmobiliaria/:
    .venv/bin/python rag/crear_base_conocimiento.py
"""

import json
import subprocess
import sys
import time

import requests

SUBSCRIPTION_ID = "57ff11aa-f7e9-4f80-a643-565666f00aed"
RESOURCE_GROUP = "rg-kevin.inofuente-7619"
FOUNDRY_ACCOUNT = "datapath-inofuente-resource"
FOUNDRY_PROJECT = "datapath-inofuente"
AOAI_ENDPOINT = "https://datapath-inofuente-resource.openai.azure.com/"
EMBEDDING_DEPLOYMENT = "text-embedding-3-small"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_DEPLOYMENT = "gpt-5-mini"
CHAT_MODEL = "gpt-5-mini"

SEARCH_SERVICE = "srch-alphastate-datapath"
SEARCH_ENDPOINT = f"https://{SEARCH_SERVICE}.search.windows.net"
SEARCH_API_VERSION = "2026-08-01-preview"
STORAGE_ACCOUNT = "stalphastatea144be"
BLOB_CONTAINER = "base-conocimiento"

KNOWLEDGE_SOURCE = "alpha-state-politicas-ks"
KNOWLEDGE_BASE = "alpha-state-kb"
PROJECT_CONNECTION = "srch-alphastate-datapath"   # nombre de la conexión en el proyecto

ARM = "https://management.azure.com"
PROJECT_ARM_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.CognitiveServices/accounts/{FOUNDRY_ACCOUNT}/projects/{FOUNDRY_PROJECT}"
)
SEARCH_ARM_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
    f"/providers/Microsoft.Search/searchServices/{SEARCH_SERVICE}"
)
ESPERA_INDEXACION_SEGUNDOS = 300


def az(*args: str) -> str:
    """Ejecuta un comando az y devuelve stdout (sin imprimirlo)."""
    return subprocess.run(["az", *args, "-o", "tsv"], check=True, capture_output=True, text=True).stdout.strip()


def token(scope: str) -> str:
    return az("account", "get-access-token", "--scope", scope, "--query", "accessToken")


def search_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {token('https://search.azure.com/.default')}", "Content-Type": "application/json"}


def put_search(ruta: str, cuerpo: dict) -> dict:
    r = requests.put(f"{SEARCH_ENDPOINT}/{ruta}?api-version={SEARCH_API_VERSION}", headers=search_headers(), json=cuerpo, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"PUT {ruta} -> {r.status_code}: {r.text[:800]}")
    return r.json() if r.text else {}


def get_search(ruta: str) -> dict:
    r = requests.get(f"{SEARCH_ENDPOINT}/{ruta}?api-version={SEARCH_API_VERSION}", headers=search_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> None:
    print("1) Obteniendo claves (no se muestran)...")
    storage_cs = az("storage", "account", "show-connection-string", "-n", STORAGE_ACCOUNT, "-g", RESOURCE_GROUP, "--query", "connectionString")
    aoai_key = az("cognitiveservices", "account", "keys", "list", "-n", FOUNDRY_ACCOUNT, "-g", RESOURCE_GROUP, "--query", "key1")
    search_admin_key = az("search", "admin-key", "show", "--service-name", SEARCH_SERVICE, "-g", RESOURCE_GROUP, "--query", "primaryKey")

    print(f"2) Knowledge source '{KNOWLEDGE_SOURCE}' (blob {STORAGE_ACCOUNT}/{BLOB_CONTAINER})...")
    ks = put_search(f"knowledgesources/{KNOWLEDGE_SOURCE}", {
        "name": KNOWLEDGE_SOURCE,
        "kind": "azureBlob",
        "description": "Políticas de alquiler, FAQ y pautas operativas de Alpha State Assessoria Imobiliária (Campinas, Brasil). Fuente: PDF 'Base de Conocimiento - Alpha State V2'.",
        "azureBlobParameters": {
            "connectionString": storage_cs,
            "containerName": BLOB_CONTAINER,
            "folderPath": None,
            "isADLSGen2": False,
            "ingestionParameters": {
                "networkAccessMode": "public",
                "disableImageVerbalization": True,
                "embeddingModel": {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": AOAI_ENDPOINT,
                        "deploymentId": EMBEDDING_DEPLOYMENT,
                        "modelName": EMBEDDING_MODEL,
                        "apiKey": aoai_key,
                    },
                },
                "contentExtractionMode": "minimal",
                "ingestionSchedule": None,
            },
        },
    })
    print("   creada/actualizada. Objetos internos:", ks.get("azureBlobParameters", {}).get("createdResources") or ks.get("createdResources") or "(ver status)")

    print(f"3) Knowledge base '{KNOWLEDGE_BASE}' (modelo {CHAT_DEPLOYMENT})...")
    put_search(f"knowledgebases/{KNOWLEDGE_BASE}", {
        "name": KNOWLEDGE_BASE,
        "description": "Base de conocimiento de Alpha State: políticas de alquiler, composición del boleto (alquiler, IPTU, SANASA, seguro), multas y recargos, requisitos para alquilar, garantías y preguntas frecuentes.",
        "retrievalInstructions": (
            "Las preguntas llegan en español (a veces con términos en portugués). Busca en la fuente "
            f"{KNOWLEDGE_SOURCE} políticas, requisitos, pagos, multas, garantías y preguntas frecuentes de Alpha State. "
            "Devuelve los fragmentos más relevantes con su referencia."
        ),
        "outputMode": "extractiveData",
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE}],
        "models": [{
            "kind": "azureOpenAI",
            "azureOpenAIParameters": {
                "resourceUri": AOAI_ENDPOINT,
                "deploymentId": CHAT_DEPLOYMENT,
                "modelName": CHAT_MODEL,
                "apiKey": aoai_key,
            },
        }],
        "retrievalReasoningEffort": {"kind": "low"},
    })
    print("   creada/actualizada.")

    print(f"4) Conexión '{PROJECT_CONNECTION}' (CognitiveSearch, ApiKey) en el proyecto {FOUNDRY_PROJECT}...")
    r = requests.put(
        f"{ARM}{PROJECT_ARM_ID}/connections/{PROJECT_CONNECTION}?api-version=2025-06-01",
        headers={"Authorization": f"Bearer {token('https://management.azure.com/.default')}", "Content-Type": "application/json"},
        json={
            "name": PROJECT_CONNECTION,
            "properties": {
                "category": "CognitiveSearch",
                "target": SEARCH_ENDPOINT,
                "authType": "ApiKey",
                "isSharedToAll": True,
                "credentials": {"key": search_admin_key},
                "metadata": {"ApiType": "Azure", "ResourceId": SEARCH_ARM_ID, "location": "brazilsouth"},
            },
        },
        timeout=60,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Conexión -> {r.status_code}: {r.text[:800]}")
    print("   creada/actualizada:", r.json().get("name"))

    print("5) Esperando a que termine la indexación...")
    inicio = time.time()
    estado = {}
    while time.time() - inicio < ESPERA_INDEXACION_SEGUNDOS:
        try:
            estado = get_search(f"knowledgesources/{KNOWLEDGE_SOURCE}/status")
        except requests.HTTPError as e:
            estado = {"error": str(e)}
        sync = estado.get("synchronizationStatus") or estado.get("status") or {}
        resumen = json.dumps(sync if isinstance(sync, dict) else {"status": sync}, ensure_ascii=False)[:300]
        print("   ", resumen)
        texto = json.dumps(estado).lower()
        if '"success"' in texto or '"active"' in texto or '"completed"' in texto:
            break
        time.sleep(15)

    print("6) Consulta de prueba a la base de conocimiento...")
    r = requests.post(
        f"{SEARCH_ENDPOINT}/knowledgebases/{KNOWLEDGE_BASE}/retrieve?api-version={SEARCH_API_VERSION}",
        headers=search_headers(),
        json={"messages": [{"role": "user", "content": [{"type": "text", "text": "¿Qué recargo se cobra si pago el alquiler con atraso?"}]}]},
        timeout=120,
    )
    print("   HTTP", r.status_code)
    if r.ok:
        data = r.json()
        for item in data.get("response", [])[:1]:
            for c in item.get("content", [])[:1]:
                print("   respuesta:", (c.get("text") or "")[:1200])
        print("   referencias:", len(data.get("references", [])), "| actividad:", [a.get("type") for a in data.get("activity", [])])
    else:
        print("   ", r.text[:800])


if __name__ == "__main__":
    main()
