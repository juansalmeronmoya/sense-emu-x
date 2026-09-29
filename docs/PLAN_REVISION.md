# Plan de revisión integral — sense-emu-x

Fecha: 2026-09-25 · Rama: `claude/sensehat-multiplatform-review-4agrra` · Base: `63d33ef`

Este documento recoge la revisión completa del emulador Sense HAT multiplataforma
(librería `sense_emu`, GUI PySide6, TUI Textual, CLIs `sense_rec`/`sense_play`/`sense_csv`)
y el plan de trabajo propuesto, por fases, para llevarlo a un estado "estable".

---

## 1. Resumen ejecutivo

**Estado general: funcional, bien testeado en superficie, con deuda concentrada en
cuatro puntos**: (1) un par de bugs de corrección heredados/latentes en el núcleo
(unidades del giroscopio, lock entre procesos), (2) lógica de orquestación duplicada
entre GUI y TUI, (3) tests que "pasan" ocultando fallos reales (hilos) y sin
integración end-to-end, y (4) packaging/CI/docs desalineados con el fork
(nombre PyPI, URLs, docs GTK, 6 workflows solapados, basura en la raíz).

Línea base medida (Linux, Python 3.11, `QT_QPA_PLATFORM=offscreen`):

| Métrica | Valor |
|---|---|
| Tests | **661 passed**, 0 failed, **109 warnings** (mayoría: excepciones no capturadas en hilos de `stick.py`) |
| Cobertura total | **92,09 %** (umbral configurado 85 %) |
| Módulos más débiles | `lock.py` 69 % (rama Windows inalcanzable en Linux), `tui.py` 78 %, `pyside_main.py` 60 % |
| Tiempo de suite | ~20 s |
| Logs de Windows commiteados | fallos `F`/`E` en `test_stick.py` + cobertura 75 % con umbral 95 % |

## 2. Metodología

Revisión en paralelo por cuatro subagentes independientes (núcleo/API, frontends,
tests, packaging/CI/docs), más ejecución real de la suite y **verificación manual
en el código de todos los hallazgos Críticos/Altos** antes de incluirlos aquí.
Los hallazgos marcados ✔ están comprobados leyendo el código o reproduciéndolos;
los marcados ◐ son plausibles y se verificarán al abordarlos.

---

## 3. Hallazgos priorizados

### P0 — Corrección / integridad (arreglar primero)

| # | ✔/◐ | Ubicación | Problema | Fix propuesto |
|---|---|---|---|---|
| P0-1 | ✔ | `imu.py:278` → `imu.py:328` → `RTIMU.py:101` → `sense_hat.py:847` | **Giroscopio en °/s, no en rad/s.** La simulación calcula `gyro = Δorientación(°)/Δt`, y la API documenta rad/s (como el hardware real). Error ×57,3. Heredado del upstream. Agravante: las grabaciones de un HAT real (`record.py:102`, RTIMULib → rad/s) se reproducen en rad/s, así que **simulación y replay usan unidades distintas**. Además no hay tratamiento del salto ±180° → pico espurio de -500 °/s al cruzar yaw 180. | Convertir en la **simulación** (`imu.py::_world_state`: `np.deg2rad` + desenrollado de ángulo), no en `RTIMU.py` (rompería el replay de grabaciones reales). Revisar `GYRO_FACTOR` y el clamp (±500 °/s ≈ ±8,73 rad/s) para no perder resolución al cuantizar a entero. Test de regresión de unidades. |
| P0-2 | ✔ | `lock.py:158-172`, `lock.py:227` | **Lock entre procesos con carrera TOCTOU y `release()` incondicional.** Dos arranques simultáneos con lock "stale": A borra y escribe; B borra el de A y escribe → dos emuladores vivos escribiendo los mismos mmap/sockets. `release()` borra el fichero aunque no sea nuestro (`mine` existe pero no se usa). | Migrar a lock de SO sobre un fd abierto durante toda la vida del proceso (`fcntl.flock` / `msvcrt.locking`): se libera solo al morir el proceso, sin detección de "stale" por PID. `wait()` puede sondear con intento no bloqueante. Mientras tanto: `release()` solo si `self.mine`. |
| P0-3 | ✔ | `stick.py:266-275` + `tests/test_stick.py:219-278` | **Una excepción en un callback de joystick (o en `_read`) mata el hilo en silencio** y deja de entregar eventos. Los tests arrancan ese hilo real contra un `MagicMock` y lo dejan vivo → los 109 warnings en Linux y los fallos en Windows. | `try/except` + `logging.exception` en el bucle; tests con datos válidos y parada explícita; activar `filterwarnings = error::pytest.PytestUnhandledThreadExceptionWarning`. |
| P0-4 | ✔ | `core.py:13-29` | `EmulatorController.__init__` solo captura `OSError`; cualquier otra excepción (mmap corrupto, `struct.error`…) deja el lock adquirido y servidores a medio abrir. | `except Exception` → `self.close()` → relanzar. |
| P0-5 | ✔ | `pyside_app.py:892-914`, `tui.py:476-495` | **Sliders activos durante la reproducción**: `update_sensors()` y el hilo `Player` escriben a la vez en IMU/presión/humedad (regresión respecto al GTK original, que los bloqueaba). | Deshabilitar controles de sensores mientras `player.running`; centralizarlo en la capa de sesión (§4). |

### P1 — Robustez, seguridad y recursos

| # | ✔/◐ | Ubicación | Problema | Fix |
|---|---|---|---|---|
| P1-1 | ◐ | `screen.py:57-76`, `imu.py:73-97`, `pressure.py:72-97`, `humidity.py:80-105` | Ficheros mmap con nombre fijo en `/dev/shm`/`/tmp` abiertos sin `O_EXCL`/`O_NOFOLLOW`, con `truncate()` si el tamaño no cuadra → ataque de symlink en máquinas multiusuario (CWE-59/377). Código de apertura duplicado 4 veces. | Función común `open_shared_file()` en `common.py`: namespacing por usuario (`rpi-sense-emu-<uid>-screen` / subdirectorio 0700), `O_NOFOLLOW`, comprobación de fichero regular propio. |
| P1-2 | ✔ | `sense_hat.py` (clase), `pyside_app.py:868-870` | `SenseHat` sin `close()` ni context manager; hilo + socket del joystick solo se liberan por GC. La GUI crea un `SenseHat()` nuevo cada vez que se pulsa "Emulator" sin cerrar el anterior. | `SenseHat.close()`, `__enter__/__exit__`; la GUI reutiliza/cierra la instancia. |
| P1-3 | ◐ | `stick.py:91-169` | El socket cliente UNIX (`rpi-sense-emu-client-<pid>`) nunca se borra en `close()` → ficheros huérfanos. | `os.unlink` en `close()`. |
| P1-4 | ✔ | `pyside_app.py:1053-1064` | `closeEvent` no para `matrix.timer` ni `_hold_timer` antes de `controller.close()`; el tick siguiente falla contra un mmap cerrado (silenciado). | Parar todos los timers antes de cerrar. |
| P1-5 | ✔ | `terminal.py:109` | `locale.getdefaultlocale()` se elimina en Python 3.15 y se ejecuta al importar → rompe `sense_rec/sense_play/sense_csv`. | `locale.getencoding()` (sin fallback: el mínimo es 3.11). |
| P1-6 | ✔ | `pyside_app.py:106,359`, `tui.py:59,117` | `except Exception: pass` en todos los pollers: errores reales invisibles. | `logging` + indicador en barra de estado. |
| P1-7 | ◐ | `sense_hat.py:275` vs `screen.py:166` | Framebuffer escrito con orden de bytes nativo en un sitio y `'<H'` en otro. | `'<H'` explícito en ambos. |
| P1-8 | ◐ | `sense_hat.py:335-410` | `set_pixel(s)`/`get_pixel(s)` abren y cierran el fichero en cada llamada (coste alto en `show_message`). | Reutilizar un mmap persistente. |

### P2 — Limpieza de API / deuda menor

- `lock.py:146` parámetro `name` ignorado; `lock.py:158` `timeout` ignorado en `acquire()`.
- `imu.py:337-340` clamp en grados sobre valores ya en radianes (latente).
- `common.py:67` `slow_pi()` con FIXME: no detecta Pi modernos (usar `/proc/device-tree/model`).
- `pyside_app.py` (1 089 líneas) mezcla 4 widgets + ventana + `main()`.

---

## 4. Arquitectura objetivo

### 4.1 Situación actual

```
 Script usuario ──► SenseHat (sense_hat.py) ──┐ lee mmap / socket joystick
                                              │
                ┌──── ficheros mmap compartidos (/dev/shm | %TEMP%) ────┐
                │  screen · imu · pressure · humidity · lock(pid)        │
                └────────────────────────────────────────────────────────┘
                                              ▲ escriben
 GUI (pyside_app.py) ─┐                       │
                      ├─► EmulatorController (core.py) ─► IMU/Pressure/Humidity/Stick servers
 TUI (tui.py) ────────┘       + cada frontend reimplementa: Player, Recorder,
                                guards de estado, pollers, rotación, HOLD…
```

El diseño de fondo (servidores + mmap + socket de joystick en lugar de evdev) es
correcto y portable. El problema es **la ausencia de una capa de aplicación
compartida** entre `EmulatorController` y las vistas.

### 4.2 Propuesta

```
sense_emu/
  _shm.py            # NUEVO: apertura segura y común de ficheros compartidos (P1-1)
  lock.py            # reescrito sobre flock/msvcrt (P0-2)
  core.py            # EmulatorController (servidores) — sin cambios de rol
  session.py         # NUEVO: EmulatorSession — estado de la aplicación
                     #   fuente activa (emulador / HAT real / grabación)
                     #   start/stop_playback, start/stop_recording, is_busy
                     #   rotación + remapeo joystick, HOLD, bloqueo de sliders
                     #   eventos on_change → las vistas solo se suscriben
  gui/               # NUEVO paquete (antes pyside_app.py)
    app.py  main_window.py  widgets/led_matrix.py  widgets/telemetry.py
    dialogs/preferences.py  resources.py (iconos, rutas)
  tui/               # tui.py dividido de la misma forma
  sense_hat.py       # + close()/context manager, mmap persistente
```

Reglas:
1. Las vistas no llaman a `Player`/`Recorder`/servidores directamente: solo a `EmulatorSession`.
2. Todo acceso a widgets ocurre en el hilo de UI; los hilos (`Player`, `Recorder`, callbacks de joystick) notifican vía señal Qt / `call_from_thread` de Textual.
3. `logging` estándar en todo el paquete (`logging.getLogger("sense_emu")`), sin `except: pass`.
4. Sin `import` de PySide6/Textual fuera de `gui/` y `tui/` (la librería sigue siendo ligera).

Se mantiene compatibilidad: `sense_emu.pyside_app:main` y `sense_emu.tui:main`
quedan como alias para no romper los entry points existentes.

---

## 5. Features

### 5.1 Matriz de paridad actual

| Función | GUI | TUI | GTK original |
|---|---|---|---|
| Sliders IMU / entorno | ✅ | ✅ (inputs) | ✅ |
| Joystick press/release | ✅ | ✅ | ✅ |
| Joystick HOLD | ✅ | ❌ | ✅ |
| Rotación de vista + remapeo joystick | ✅ | ❌ | ✅ |
| Pintado interactivo de LEDs | ✅ (nuevo) | ❌ | ❌ |
| Fuente "Sense HAT real" | ✅ | ❌ | — |
| Gráficas de telemetría | ✅ (nuevo) | ❌ (solo valores) | ❌ |
| Grabar sesión | ✅ | ✅ | ❌ |
| Reproducir con progreso/stop | ✅ | ✅ | ✅ |
| Preferencias (intervalo, tamaño) | ✅ | ❌ | ✅ |
| Activar/desactivar simulación de ruido / mundo | ❌ | ❌ | ✅ |
| i18n | ❌ | ❌ | ✅ |
| Icono de aplicación | ❌ | — | ✅ |
| Sensor de color TCS34725 (Sense HAT v2) | ❌ | ❌ | ❌ (la librería oficial sí lo tiene) |

### 5.2 Roadmap de features (tras estabilizar P0/P1)

**F1 — Recuperar paridad** (bajo coste, alto valor)
- Preferencias: checkboxes `simulate_imu` / `simulate_env` (GUI y TUI).
- TUI: HOLD, rotación, fuente HAT real, preferencias (todo sale gratis de `EmulatorSession`).
- i18n real: `init_i18n()` en ambos `main()`, `_()` en literales, compilar `.mo` en el build, añadir `es` además de `en_US`.
- Icono y nombre de aplicación (`setWindowIcon`, `setApplicationName`, `.ico`/`.icns`).

**F2 — Paridad con Sense HAT v2**
- Sensor de color/luz TCS34725: fichero compartido `rpi-sense-emu-colour`, API `sense.colour` (`red`, `green`, `blue`, `clear`, `colour`, `gain`, `integration_cycles`, `integration_time`) y control en GUI/TUI (selector de color + intensidad).
- Test de compatibilidad de firma contra la API pública de `sense_hat` (lista congelada).

**F3 — Mejoras de emulación**
- Orientación 3D visual (el GTK tenía vista de orientación; `orientation.svg` ya existe en el paquete).
- Desenrollado de ángulos y modelo de ruido del giroscopio en rad/s.
- Presets de escenarios (p. ej. "estación ISS", "frigorífico", "agitar") y scripts de estímulo.
- Exportar la matriz LED como PNG/GIF animado.

**F4 — Distribución a usuarios finales**
- Ejecutables con PyInstaller (o Briefcase): `.exe` Windows, `.app` macOS, AppImage Linux; accesos directos (`.desktop`, menú Inicio).
- Instalación recomendada `pipx install "sense-emu-x[gui]"`.

---

## 6. Estrategia de tests

### 6.1 Arreglos inmediatos
- Reescribir `TestSenseStickCallbacks` (`test_stick.py:219-278`) con eventos válidos y `close()` en teardown.
- `filterwarnings = error` para `PytestUnhandledThreadExceptionWarning` (los warnings pasan a ser fallos).
- Eliminar `sleep` sin aserción (`test_humidity.py:74-86` y similares); usar eventos/polling con timeout.

### 6.2 Pirámide objetivo

| Nivel | Qué añadir | Ejemplos |
|---|---|---|
| Unit | Rama Windows de `lock.py` con `importlib.reload` + `ctypes` mockeado; nuevo lock flock/msvcrt | `test_pid_exists_windows_branch`, `test_lock_released_on_process_death` |
| Property-based (Hypothesis) | RGB565, parser de grabaciones, rotaciones/flip | `test_rgb565_roundtrip_property`, `test_parse_recording_rejects_any_truncation`, `test_rotate_four_times_is_identity` |
| Unidades físicas | Regresión de P0-1 | `test_gyro_raw_is_radians_per_second`, `test_yaw_wrap_does_not_spike_gyro` |
| Integración (mismo proceso) | `EmulatorController` + `SenseHat` reales sobre `tmp_path` | `test_sensehat_reads_values_written_by_controller`, `test_joystick_event_roundtrip` |
| Integración (multiproceso) | lock y mmap entre dos procesos reales | `test_second_emulator_refused`, `test_script_in_subprocess_sees_led_writes` |
| GUI (pytest-qt) | flujos completos, no métodos sueltos | `test_sliders_disabled_during_playback`, `test_close_stops_all_timers` |
| TUI (Textual Pilot) | `async with app.run_test() as pilot` | `test_arrow_key_sends_joystick_press`, `test_app_mounts_and_renders_matrix` |
| Compatibilidad API | firma de `SenseHat` vs referencia congelada | `test_public_api_matches_sense_hat_reference` |
| CLI | entry points reales vía `subprocess` | `test_sense_rec_play_csv_pipeline` |

### 6.3 Objetivos
- Cobertura ≥ 90 % global, **≥ 85 % por módulo**, medida **combinando** Linux + Windows + macOS (así la rama Windows de `lock.py` cuenta).
- 0 warnings no filtrados.
- Suite unit < 30 s; integración multiproceso marcada `@pytest.mark.integration`.

---

## 7. Packaging, CI/CD y documentación

### 7.1 Hallazgos

| Sev. | Ubicación | Problema | Fix |
|---|---|---|---|
| Crítica | `pyproject.toml:5` | `name = "sense-emu"` **colisiona con el paquete oficial en PyPI**; `publish.yml` publicaría sobre un proyecto ajeno (o fallaría). | Renombrar distribución (p. ej. `sense-emu-x`), manteniendo el paquete importable `sense_emu`. |
| Alta | `pyproject.toml:56-57`, `README.rst`, `INSTALL.md`, `DEVELOPMENT.md`, `.github/CI.md` | URLs a `astro-pi/…` y `RPi-Distro/…` (ni siquiera coinciden entre sí). | Unificar a `juansalmeronmoya/sense-emu-x`. |
| Alta | `docs/install.rst`, `docs/sense_emu_gui.rst`, `README.rst` | Sphinx describe la GUI **GTK** (PyGObject, apt, brew gtk+3). | Reescribir para PySide6/pip/pipx; capturas nuevas. |
| Alta | `.github/workflows/` | 6 workflows solapados; `ci.yml` (el "principal") solo Ubuntu; `tests.yml` ejecuta pytest dos veces; lint `continue-on-error`. | Un único `ci.yml` (ver 7.2). |
| Alta | raíz | Basura commiteada: `test_output.txt`, `test_result.txt`, `test_run_2.txt`, `test_summary.txt`, `final_test.txt` (con rutas locales de Windows), `test_gui.py`, `patch_setup.py` (código muerto de migración). | `git rm` + `.gitignore`. Mover `example.py` a `sense_emu/examples/`. |
| Alta | `RELEASE.md` | Documenta publicación por tag + `PYPI_API_TOKEN`; `publish.yml` real usa `release: published` + OIDC trusted publishing (correcto). | Reescribir la sección. |
| Media | `pyproject.toml` package-data + `.gitignore` | Se declaran `.mo` pero nunca se compilan en el build → wheels sin traducciones. | Paso `msgfmt` en build (hook o CI). |
| Media | README / pyproject / `__init__` | Versión 1.0.0 vs 1.2.1; "427 tests / 91,67 %" hardcodeado (real: 661 / 92 %). | Una sola fuente de versión (`__init__` dinámico); badges en vez de cifras. |
| Media | `pyproject.toml:32` | `requires-python >=3.8` pero CI prueba 3.10+; 3.8 y 3.9 están EOL. Falta clasificador 3.14. | `>=3.11`, clasificadores 3.11–3.14 (decisión §9.2). |
| Baja | `pyproject.toml:10` | Licencia dual (LGPL lib / GPL apps) expresada solo como GPL. | `license-files` + expresión SPDX correcta. |
| Baja | `.pre-commit-config.yaml` | black+isort+flake8+pydocstyle; nada de eso bloquea en CI. | Sustituir por `ruff` (lint+format) y ejecutarlo en CI. |

### 7.2 Pipeline objetivo (`.github/workflows/ci.yml` único)

```
lint        ubuntu · ruff check · ruff format --check              (bloqueante)
typecheck   ubuntu · mypy sense_emu (progresivo, bloqueante al estabilizar)
test        matriz {ubuntu, windows, macos} × {3.11 … 3.14}
            pip install -e ".[gui,tui,test]" · pytest · upload coverage
coverage    combina los .coverage de la matriz · fail-under 90 global
build       python -m build · twine check · msgfmt · artefacto wheel/sdist
bundle      (tags) PyInstaller por SO → .exe / .app / AppImage como assets del release
publish     release: published → TestPyPI → PyPI (OIDC, ya existente)
schedule    semanal: misma matriz contra dependencias más recientes
```

---

## 8. Plan por fases

Cada fase = 1 PR (o varios pequeños), con CI verde antes de pasar a la siguiente.

| Fase | Contenido | Hallazgos | Esfuerzo |
|---|---|---|---|
| **0. Higiene** ✅ | Borrar basura de la raíz, `.gitignore`, unificar URLs, versión única, consolidar workflows en `ci.yml` con matriz 3 SO, ruff | 7.1 (Altas/Medias de CI y repo) | S |
| **1. Bugs críticos** ✅ | Giroscopio rad/s + desenrollado; lock flock/msvcrt; hilo de joystick robusto + tests; `core.py` cleanup; sliders bloqueados en replay; timers en `closeEvent`; `getdefaultlocale` | P0-1…P0-5, P1-4, P1-5 | M |
| **2. Recursos y seguridad** | `_shm.py` común (O_NOFOLLOW, namespacing por usuario); `SenseHat.close()`; unlink de socket cliente; byte order; mmap persistente en `sense_hat.py`; logging | P1-1…P1-3, P1-6…P1-8 | M |
| **3. Arquitectura** | `session.py` (`EmulatorSession`); dividir `pyside_app.py` → `gui/`, `tui.py` → `tui/`; eventos de hilo → UI thread | §4 | L |
| **4. Tests** | Integración mismo proceso + multiproceso, Pilot TUI, Hypothesis, compat API, cobertura combinada por SO | §6 | M |
| **5. Paridad de features** | F1: preferencias de simulación, TUI completa, i18n (en/es), icono | §5.2 F1 | M |
| **6. Sense HAT v2 y extras** | F2 sensor de color; F3 vista 3D de orientación, presets, export PNG/GIF | §5.2 F2–F3 | L |
| **7. Distribución** | Renombrado PyPI, docs Sphinx reescritas, PyInstaller por SO, guía pipx | §5.2 F4, 7.1 | M |

Las fases 0–2 son independientes de la arquitectura y pueden entrar ya; la fase 3
conviene hacerla **antes** de añadir features (fases 5–6) para no duplicarlas en GUI y TUI.

### Criterios de "hecho" globales
- CI verde en Linux, Windows y macOS para Python 3.11–3.14.
- 0 warnings no filtrados en la suite; cobertura combinada ≥ 90 %.
- `pipx install sense-emu-x[gui]` → `sense_emu_gui` funciona en los tres SO; un script con `from sense_emu import SenseHat` lee valores físicamente correctos (unidades verificadas por test).
- Docs y README describen exactamente lo que hay.

---

## 9. Decisiones (resueltas por el propietario)

| # | Decisión | Resolución |
|---|---|---|
| 1 | Nombre en PyPI | **`sense-emu-x`** (el paquete importable sigue siendo `sense_emu`). |
| 2 | Python mínimo | **3.11**: la versión más antigua de CPython que sigue con soporte de seguridad (3.10 llega a EOL en octubre de 2026). Matriz de CI 3.11–3.14. |
| 3 | Unidades del giroscopio | Se aplica como *breaking fix*: versión **2.0.0** y entrada explícita en el changelog. |
| 4 | Sense HAT v2 (sensor de color) | **Dentro del alcance** (Fase 6). |
| 5 | Distribución | **Ambas**: paquete en PyPI (pip/pipx) **y** ejecutables nativos con PyInstaller por SO adjuntos a cada release (Fase 7). |
| 6 | Versión en el formato mmap | **Sí**: campo de versión y error claro si no coincide (se implementa junto con `_shm.py`, Fase 2). |

### Notas de ejecución
- El renombrado de la distribución (`sense-emu-x`), `requires-python`, clasificadores, URLs y licencia SPDX se adelantaron a la **Fase 0** porque publicar con el nombre anterior escribiría sobre un proyecto ajeno.
- `ruff format --check` y el job de `mypy` se posponen: reformatear todo el código ahora ocultaría los cambios reales en el diff. Entran cuando se haga un único commit de formato.
- El `Makefile` distingue ahora nombre de distribución (`sense-emu-x`), directorio del paquete (`sense_emu`) y dominio gettext (`sense-emu`).

### Notas de la Fase 1 (implementada)
- **Giroscopio (P0-1):** además de convertir a rad/s y desenrollar el ángulo, se corrigió la cuantización. El registro guarda cuentas LSB de un rango de ±500 dps (17,5 mdps/LSB), pero se le aplicaba el factor de °/s a valores en rad/s, dejando un escalón de ~0,0175 rad/s. `GYRO_FACTOR` pasa a ser LSB por rad/s (≈ 3274) y el límite a ±500 dps en rad/s. El ruido simulado se mantiene en ~1 dps. Como cambia la interpretación del fichero IMU compartido, una GUI antigua no interopera con la librería nueva hasta que la Fase 2 añada el campo de versión del formato (decisión §9.6); el changelog lo advierte. La versión queda en `2.0.0.dev0` hasta publicar.
- **Lock (P0-2):** en lugar de eliminar por completo el fichero de PID, se mantiene su formato (PID, magic, hora de inicio) para que `SenseHat.wait()` y las versiones antiguas sigan funcionando, y se añade un bloqueo del SO (`flock` / `msvcrt.locking`) sobre un fd abierto mientras viva el proceso. El kernel arbitra: ya no hay ventana TOCTOU ni hace falta decidir si un lock está "obsoleto" para adquirirlo. Se conserva una comprobación del PID solo para detectar un titular de una versión antigua que no usa bloqueo de SO. `release()` solo actúa si el objeto es el titular. `acquire(timeout=...)` ahora se respeta (`None` = fallar de inmediato, como antes). **La rama de Windows no se puede ejecutar en el entorno de desarrollo (Linux): la valida el job `windows-latest` del CI.**
- **Hilo del joystick (P0-3):** además de capturar excepciones, el hilo sondeaba con una lectura bloqueante y `close()` se quedaba esperando al siguiente evento; ahora sondea con `select` y se detiene al instante. También se corrigió que `direction_x = None` dejaba la clave en el diccionario, con lo que el hilo nunca se paraba. Un `PytestUnhandledThreadExceptionWarning` es ahora un error de la suite (`setup.cfg`).
- **Tests:** los tests del hilo usaban `MagicMock` como fichero del joystick; ahora usan un `socketpair` real. Quedan `ResourceWarning` de tests antiguos (RTIMU, dump, play…) que dejan ficheros sin cerrar: se limpian en la Fase 4.
- **GUI/TUI (P0-5):** al terminar la reproducción los controles se reactivan y el emulador vuelve a reflejar los valores de los controles, en lugar de conservar el último fotograma de la grabación.
