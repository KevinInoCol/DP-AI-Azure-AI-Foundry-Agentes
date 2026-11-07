"""
Crea la base de conocimiento de la Alcaldía de Girardota en Foundry IQ (Azure AI Search).

Pasos que ejecuta, todos idempotentes:
0. Cuenta de almacenamiento + contenedor, y sube todos los documentos que haya
   en `rag/Base de Conocimiento/` (PDF, DOCX, TXT, MD, HTML).
1. Knowledge source `azureBlob` que apunta a ese contenedor. AI Search crea por
   dentro el índice, el skillset (chunking + embeddings con
   text-embedding-3-small) y el indexador.
2. Knowledge base que agrupa la fuente y usa el chat model (CHAT_DEPLOYMENT) para planificar
   consultas (agentic retrieval), con instrucciones en español.
3. Conexión "Azure AI Search" en el proyecto de Foundry (categoría
   CognitiveSearch, clave de API) para que la base aparezca en Compilación →
   Conocimiento del portal.
4. Espera a que termine la indexación y hace una consulta de prueba.

El servicio de búsqueda es de nivel Free (sin identidad administrada) y se
comparte con el otro agente del taller: el nivel Free solo permite un servicio
por suscripción y admite 3 índices. Por eso las conexiones a Storage y a los
modelos usan claves, que se obtienen en runtime con Azure CLI y nunca se
imprimen ni se guardan en disco.

Después de ejecutarlo hay que conceder "Search Index Data Reader" en el
servicio de búsqueda a tu usuario, a la identidad del proyecto y a la identidad
de instancia del agente hospedado (`azd ai agent show`); el script imprime los
comandos al final. Luego pon `enabled: true` en la tool
`consultar_tramites_girardota` de model_config.yaml y vuelve a desplegar.

Requisitos: `az login` en el tenant correcto; el usuario debe ser Owner (o
Search Service Contributor + Search Index Data Contributor) del servicio.

Ejecutar desde src/agent-framework-agent-municipalidad/:
    .venv/bin/python rag/crear_base_conocimiento.py
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

SUBSCRIPTION_ID = "57ff11aa-f7e9-4f80-a643-565666f00aed"

# DESTINO: recurso y proyecto de Foundry donde vive el agente. Deben coincidir con
# el endpoint de azure.yaml (verificar_destino() aborta si no). Cada recurso puede
# estar en un resource group distinto: no asumas que comparten RG.
FOUNDRY_RESOURCE_GROUP = "Datapath-ai-engineer-ka-ic"
FOUNDRY_ACCOUNT = "Datapath-AI-Engineer-KAIC"
FOUNDRY_PROJECT = "proj-ai-engineer-foundry"
AOAI_ENDPOINT = "https://datapath-ai-engineer-kaic.openai.azure.com/"
EMBEDDING_DEPLOYMENT = "text-embedding-3-small"
EMBEDDING_MODEL = "text-embedding-3-small"
# gpt-5-mini no existe en KAIC (bloqueo 715-123420 al crearlo); gpt-5.4-mini sí.
CHAT_DEPLOYMENT = "gpt-5.4-mini"
CHAT_MODEL = "gpt-5.4-mini"

# Servicio de búsqueda compartido del taller (Free, Brazil South). Puede estar en
# una región y un RG distintos a los del proyecto de Foundry; no afecta.
SEARCH_RESOURCE_GROUP = "rg-kevin.inofuente-7619"
SEARCH_SERVICE = "srch-alphastate-datapath"
SEARCH_ENDPOINT = f"https://{SEARCH_SERVICE}.search.windows.net"
SEARCH_API_VERSION = "2026-08-01-preview"
SEARCH_LOCATION = "brazilsouth"

# Storage propio de la alcaldía. El nombre es global: si ya existe en otra
# suscripción, define STORAGE_ACCOUNT con otro valor antes de ejecutar.
STORAGE_ACCOUNT = os.getenv("STORAGE_ACCOUNT", "stgirardotadatapath")
STORAGE_RESOURCE_GROUP = "rg-kevin.inofuente-7619"
STORAGE_LOCATION = "eastus2"
BLOB_CONTAINER = "base-conocimiento"

# El embedding de un knowledge source es inmutable ("The embedding model configuration
# cannot be changed"). Al pasar a KAIC se creó una fuente nueva con los embeddings de KAIC;
# la anterior (girardota-tramites-ks, embeddings de datapath-inofuente) quedó huérfana.
KNOWLEDGE_SOURCE = "girardota-tramites-kaic-ks"
KNOWLEDGE_BASE = "girardota-kb"
PROJECT_CONNECTION = "srch-alphastate-datapath"   # nombre de la conexión en el proyecto

CARPETA_DOCUMENTOS = Path(__file__).resolve().parent / "Base de Conocimiento"
EXTENSIONES = {".pdf", ".docx", ".doc", ".txt", ".md", ".html", ".pptx", ".xlsx"}
# Archivos de la propia carpeta que son instrucciones para el equipo, no conocimiento.
EXCLUIDOS = {"leeme.md", "readme.md"}

ARM = "https://management.azure.com"
PROJECT_ARM_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{FOUNDRY_RESOURCE_GROUP}"
    f"/providers/Microsoft.CognitiveServices/accounts/{FOUNDRY_ACCOUNT}/projects/{FOUNDRY_PROJECT}"
)
SEARCH_ARM_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{SEARCH_RESOURCE_GROUP}"
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


def verificar_destino() -> None:
    """Confirma que el script apunta al mismo recurso/proyecto de Foundry que el agente.

    Con dos o más recursos de Foundry en la suscripción es fácil crear la base y la
    conexión en el proyecto equivocado (la KB funciona, pero no aparece en
    Compilación → Conocimiento del proyecto del agente). Compara las constantes con
    el endpoint de azure.yaml, comprueba que el proyecto y los despliegues existen y
    pide confirmación explícita antes de crear nada.
    """
    raiz = next((d for d in Path(__file__).resolve().parents if (d / "azure.yaml").exists()), None)
    if raiz is None:
        sys.exit("   No encontré azure.yaml: no puedo saber a qué proyecto apunta el agente. Abortando.")
    m = re.search(r"https://([^.]+)\.services\.ai\.azure\.com/api/projects/([^\s/]+)", (raiz / "azure.yaml").read_text())
    if m is None:
        sys.exit("   azure.yaml no tiene un endpoint de proyecto de Foundry. Abortando.")
    cuenta_yaml, proyecto_yaml = m.group(1), m.group(2)
    if cuenta_yaml.lower() != FOUNDRY_ACCOUNT.lower() or proyecto_yaml != FOUNDRY_PROJECT:
        sys.exit(
            f"   DESTINO DISTINTO\n"
            f"     azure.yaml (agente): {cuenta_yaml} / {proyecto_yaml}\n"
            f"     este script       : {FOUNDRY_ACCOUNT} / {FOUNDRY_PROJECT}\n"
            f"   Corrige FOUNDRY_* en la cabecera del script (o el endpoint de azure.yaml). Abortando."
        )
    try:
        az("cognitiveservices", "account", "show", "-n", FOUNDRY_ACCOUNT, "-g", FOUNDRY_RESOURCE_GROUP, "--query", "id")
        despliegues = set(az("cognitiveservices", "account", "deployment", "list", "-n", FOUNDRY_ACCOUNT,
                             "-g", FOUNDRY_RESOURCE_GROUP, "--query", "[].name").split())
        az("search", "service", "show", "-n", SEARCH_SERVICE, "-g", SEARCH_RESOURCE_GROUP, "--query", "id")
    except subprocess.CalledProcessError as e:
        sys.exit(f"   No encontré un recurso del destino (revisa nombres y resource groups): {e.stderr.strip()[:300]}")
    faltan = {EMBEDDING_DEPLOYMENT, CHAT_DEPLOYMENT} - despliegues
    if faltan:
        sys.exit(f"   Faltan despliegues en {FOUNDRY_ACCOUNT}: {sorted(faltan)}. Disponibles: {sorted(despliegues)}")

    print("   Destino de la base de conocimiento:")
    print(f"     Suscripción     : {SUBSCRIPTION_ID}")
    print(f"     Foundry         : {FOUNDRY_ACCOUNT} (RG {FOUNDRY_RESOURCE_GROUP}) / proyecto {FOUNDRY_PROJECT}")
    print(f"     Modelos         : {EMBEDDING_DEPLOYMENT} + {CHAT_DEPLOYMENT}")
    print(f"     AI Search       : {SEARCH_SERVICE} (RG {SEARCH_RESOURCE_GROUP})")
    print(f"     Storage         : {STORAGE_ACCOUNT} (RG {STORAGE_RESOURCE_GROUP})")
    print(f"     KS / KB         : {KNOWLEDGE_SOURCE} / {KNOWLEDGE_BASE}")
    if "--yes" not in sys.argv and input("   ¿Es el proyecto correcto? (s/N): ").strip().lower() not in {"s", "si", "sí", "y", "yes"}:
        sys.exit("   Cancelado por el usuario.")


def subir_documentos() -> int:
    """Crea storage + contenedor si faltan y sube la carpeta 'Base de Conocimiento'."""
    documentos = sorted(
        p for p in CARPETA_DOCUMENTOS.glob("*")
        if p.suffix.lower() in EXTENSIONES and p.name.lower() not in EXCLUIDOS
    )
    if not documentos:
        print(f"   No hay documentos en '{CARPETA_DOCUMENTOS}'. Copia ahí los PDF oficiales y vuelve a ejecutar.")
        sys.exit(1)

    existe = az("storage", "account", "list", "-g", STORAGE_RESOURCE_GROUP, "--query", f"[?name=='{STORAGE_ACCOUNT}'].name")
    if not existe:
        print(f"   Creando cuenta de almacenamiento '{STORAGE_ACCOUNT}'...")
        az("storage", "account", "create", "-n", STORAGE_ACCOUNT, "-g", STORAGE_RESOURCE_GROUP, "-l", STORAGE_LOCATION,
           "--sku", "Standard_LRS", "--kind", "StorageV2", "--min-tls-version", "TLS1_2",
           "--allow-blob-public-access", "false")
    # --auth-mode key: ser Owner no concede roles de datos de blob.
    az("storage", "container", "create", "--account-name", STORAGE_ACCOUNT, "-n", BLOB_CONTAINER, "--auth-mode", "key")
    for doc in documentos:
        print(f"   subiendo {doc.name}")
        az("storage", "blob", "upload", "--account-name", STORAGE_ACCOUNT, "-c", BLOB_CONTAINER,
           "-f", str(doc), "-n", doc.name, "--auth-mode", "key", "--overwrite")
    return len(documentos)


def main() -> None:
    print("-) Verificando el destino...")
    verificar_destino()

    print(f"0) Storage '{STORAGE_ACCOUNT}/{BLOB_CONTAINER}' y subida de documentos...")
    total = subir_documentos()
    print(f"   {total} documento(s) en el contenedor.")

    print("1) Obteniendo claves (no se muestran)...")
    storage_cs = az("storage", "account", "show-connection-string", "-n", STORAGE_ACCOUNT, "-g", STORAGE_RESOURCE_GROUP, "--query", "connectionString")
    aoai_key = az("cognitiveservices", "account", "keys", "list", "-n", FOUNDRY_ACCOUNT, "-g", FOUNDRY_RESOURCE_GROUP, "--query", "key1")
    search_admin_key = az("search", "admin-key", "show", "--service-name", SEARCH_SERVICE, "-g", SEARCH_RESOURCE_GROUP, "--query", "primaryKey")

    print(f"2) Knowledge source '{KNOWLEDGE_SOURCE}' (blob {STORAGE_ACCOUNT}/{BLOB_CONTAINER})...")
    ks = put_search(f"knowledgesources/{KNOWLEDGE_SOURCE}", {
        "name": KNOWLEDGE_SOURCE,
        "kind": "azureBlob",
        "description": "Documentos oficiales de la Alcaldía Municipal de Girardota (Antioquia): trámites y servicios, requisitos, costos, plazos, dependencias, horarios y preguntas frecuentes.",
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
        "description": "Base de conocimiento de la Alcaldía Municipal de Girardota: trámites y servicios, requisitos y documentos, costos y descuentos, plazos, dependencias responsables, horarios, puntos de atención y preguntas frecuentes.",
        "retrievalInstructions": (
            "Las preguntas llegan en español, de ciudadanía sin lenguaje técnico. Busca en la fuente "
            f"{KNOWLEDGE_SOURCE} trámites, requisitos, documentos, costos, descuentos, plazos, dependencias, "
            "horarios, puntos de atención y preguntas frecuentes de la Alcaldía Municipal de Girardota. "
            "Prioriza requisitos, plazos y costos exactos. Devuelve los fragmentos más relevantes con su referencia."
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
                "metadata": {"ApiType": "Azure", "ResourceId": SEARCH_ARM_ID, "location": SEARCH_LOCATION},
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
        json={
            "messages": [{"role": "user", "content": [{"type": "text", "text": "¿Qué requisitos piden para el certificado de residencia?"}]}],
            "maxOutputSize": 8000,
        },
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

    print()
    print("7) Falta conceder 'Search Index Data Reader' (retrieve da 403 aunque seas Owner):")
    print(f'   SEARCH_ID=$(az search service show -n {SEARCH_SERVICE} -g {SEARCH_RESOURCE_GROUP} --query id -o tsv)')
    print('   az role assignment create --assignee-object-id $(az ad signed-in-user show --query id -o tsv) \\')
    print('     --assignee-principal-type User --role "Search Index Data Reader" --scope "$SEARCH_ID"')
    print('   # identidad de instancia del agente hospedado (azd ai agent show → Instance Identity Principal ID):')
    print('   az role assignment create --assignee-object-id <principal-del-agente> \\')
    print('     --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope "$SEARCH_ID"')
    print()
    print("8) Después: pon enabled: true en tools.consultar_tramites_girardota de model_config.yaml y ejecuta azd deploy --no-prompt")


if __name__ == "__main__":
    main()
