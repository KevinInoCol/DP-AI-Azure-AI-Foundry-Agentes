# Registro de decisiones de arquitectura (ADR)

Cada ADR registra una decisión sobre la arquitectura de nuestros agentes **y del harness que los construye y despliega** (skills, hooks y configuración de Claude Code). Cada uno nace de una falla o de una necesidad real y deja escrito qué se eligió y por qué.

## Índice

| # | Título | Estado | Fecha |
|---|---|---|---|
| [0001](0001-verificar-destino-foundry-antes-de-desplegar.md) | Verificar el recurso y el proyecto de Foundry antes de desplegar o crear recursos | Aceptado | 2026-11-06 |
| [0002](0002-fuente-de-verdad-de-las-skills-del-harness.md) | Fuente de verdad de las skills del harness: autoría global, copias reales sincronizadas en el repo | Aceptado | 2026-11-06 |
| [0003](0003-hook-que-bloquea-despliegues-con-destino-inconsistente.md) | Hook PreToolUse que bloquea despliegues y scripts de Foundry con destino inconsistente | Aceptado | 2026-11-06 |

## Convenciones

- Archivo: `NNNN-titulo-en-kebab-case.md`, numeración correlativa y que no se reutiliza.
- Estados: `Propuesto` → `Aceptado` → (`Reemplazado por ADR NNNN` | `Obsoleto`). Un ADR aceptado no se reescribe: si la decisión cambia, se crea uno nuevo que lo reemplaza y se actualiza el estado del anterior.
- Los "Pendientes" de un ADR son candidatos a los ADR siguientes. Marcar un pendiente como resuelto (`[x]` + enlace al ADR que lo resolvió) es la única edición permitida en un ADR aceptado.

## Plantilla

```markdown
# ADR NNNN — <decisión en una frase>

- **Estado:** Propuesto
- **Fecha:** AAAA-MM-DD
- **Ámbito:** <agentes / harness afectados>

## 1. Contexto
Qué problema existía: hechos, fallas observadas y restricciones.

## 2. Decisión
Qué se eligió y cómo se aplica (proceso, código, configuración).

### Alternativas descartadas
| Alternativa | Por qué no |
|---|---|

## 3. Consecuencias
### Qué se gana
### Qué se pierde / costo
### Qué queda pendiente
- [ ] ...

## Referencias
```
