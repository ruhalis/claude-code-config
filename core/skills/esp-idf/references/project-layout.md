# IDF project layout and house style

Read from SKILL.md when creating a project, adding a registry dependency, touching `.gitignore` or credentials, or writing new firmware code in a project that has no style of its own. A project's own docs and existing code win over this file.

## Shape

`CMakeLists.txt` at the project root, `main/` with its own `CMakeLists.txt`, `main/idf_component.yml` for registry dependencies, `sdkconfig.defaults`, and `partitions.csv` when the table is custom. A `components/` directory at the project root is found automatically; `EXTRA_COMPONENT_DIRS` is only for shared component directories outside the project, such as a `../components` that several apps use.

| Committed | Generated, not committed |
|---|---|
| `sdkconfig.defaults`, `sdkconfig.defaults.<chip>`, `partitions.csv`, `dependencies.lock`, `*.h.example` | `sdkconfig`, `sdkconfig.old`, `build/`, `managed_components/`, `.cache/` (clangd index), the real secrets header |

Before the first commit in a new project, make sure its `.gitignore` covers the right column; add the lines if it does not.

## Dependencies

Registry dependencies go through the component manager rather than copied sources, so the version is recorded and updates stay one command: `idf.py -C "<dir>" add-dependency "<name>"`, then recommend committing the changed `idf_component.yml` and `dependencies.lock`. One exception: a manifest with Kconfig-conditional `rules:` dependencies makes the lock file machine-specific, so leave the lock out then.

A failed registry fetch (no network) is not fatal: `dependencies.lock` plus a warm `managed_components/` still builds offline.

To change an upstream component, copy it into the project's `components/` under the same name (project components win over IDF and managed ones) and note the override in the project docs.

## Credentials

Credentials live in a gitignored header with a committed `.example` next to it, named by the project. Source files include that header; a literal credential in source ends up in a commit.

## House style, where the project has none

- FreeRTOS tasks, `esp_log` with a per-file `TAG`, `vTaskDelay(pdMS_TO_TICKS(n))`. None of the Arduino idioms (`setup()`/`loop()`, `Serial.`, `delay()`, `Wire.`, `millis()`): they do not exist under pure IDF.
- Wi-Fi via `esp_wifi` plus `nvs_flash`; networking clients from the registry (`espressif/esp_websocket_client`, `espressif/mdns`) rather than hand-rolled sockets.
- Chip-specific keys (flash size, PSRAM) in `sdkconfig.defaults.<chip>`, one per chip the project builds for, committed.
