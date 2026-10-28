# Auditoría de rendimiento de SynthStudio

Fecha: 2026-10-28. Estado: mediciones y diagnóstico del código fuente completos;
comprobación de interacción en la app instalada pendiente por selección de instancia.

Guerrilla tarda 1,81 s de mediana entre una edición de proyecto y su pintura
correcta; preparar 32 cuadros Full tarda 34,45 s. Text muestra que el trabajo
síncrono del inspector también limita la respuesta: ocupa 0,78 s por edición
de proyecto aunque un seek sin caché tarde 0,16 s. Conviene empezar por el
refresco y la resolución repetida de estados del inspector, antes de modificar
el renderizador. Se proponen cuatro oportunidades, sin implementarlas.

La auditoría mide la espera hasta el retorno del `paintEvent` que corresponde al
cuadro solicitado. Los cambios se limitan a herramientas opcionales y documentación.
El renderizador y la aplicación de producción conservan su código original.

## Entorno y protección del trabajo

- MacBook Pro Mac15,9, M3 Max, 16 núcleos (12 de rendimiento y 4 de eficiencia),
  48 GB de memoria; macOS 26.5.1, build 25F80.
- Python 3.14.6, PySide6 6.11.2, NumPy 2.5.3, Pillow 12.3.0,
  fonttools 4.67.0 y trimesh 4.11.2, desde la `.venv` existente.
- Alimentación de red, batería al 100% y modo de energía automático en el registro
  inicial. Las aplicaciones habituales permanecieron abiertas: Ableton Live
  consumió aproximadamente medio núcleo; WindowServer, navegador y Codex aportan
  carga variable. El manifiesto y las muestras conservan esa carga de fondo.
- Punto de partida limpio: `e40684f23852faf2547b2849501cdf5b6fb9ea5c`.
  El código de producción coincide con
  `0e7c21b7c865da76c578571faa0ece638ba3f75a` (`v0.48.1^{}`);
  los cambios intermedios de main eran documentación.
- Rama: `codex/preview-performance-audit`. Cada ejecución registra commit,
  argumentos, hash del runner, PID y directorio de estado.
- El bundle instalado declara 0.48.1. Su versión no constituye una prueba de un
  hash de compilación embebido; la comprobación instalada se presenta por separado.
- Se usaron copias congeladas y `NEBULA_STATE_DIR` por ejecución. El directorio de
  proxies del proceso de auditoría también se redirigió al estado aislado.
  La instancia del usuario, PID 94173, no se cerró ni se reinició.

El original de Guerrilla y su copia se cargan y normalizan al mismo documento.
Se conservaron el audio de guía, las fuentes y las rutas de medios. Los hashes
de documentos, audio, fuentes y recursos están en el manifiesto local.

## Casos y protocolo

| Caso | Canvas Full | FPS | Duración | Clips |
| --- | ---: | ---: | ---: | ---: |
| Guerrilla Radio — optical print | 1080 × 1920 | 30 | 9,3667 s | 45 |
| Text / one more try | 720 × 406 | 30 | 15 s | 73 |
| Memory / afterimage garden | 720 × 960 | 24 | 15 s | 1 |
| Color film / rotating die | 720 × 1280 | 25 | 15 s | 1 |
| Video testsrc2 con tratamientos | 1920 × 1080 | 30 | 3 s | 1 |

El video se generó con FFmpeg, `testsrc2`, FFV1 lossless, 30 fps, tres segundos,
un hilo y flags bitexact. Se importó mediante `start_video_import` / `ImportVideoJob`;
se añadieron Color emulsion al 50% y Bloom strength 0,3 mediante el composer.
La generación, la importación, la preparación del proxy y la decodificación
posterior tienen registros separados.

Se conservan los parámetros, semillas, efectos y FPS de cada documento.
Guerrilla mantiene la semilla 281026 y sus efectos film_emulsion, crt_capture y
bloom. Full se comprueba con las dimensiones del caso congelado, además del índice
del selector. Esa comprobación también cubre el navegador de efectos.
Low Res Finish está desactivado en todos los estados de los cinco casos
congelados, comprobado en sus presets compilados. Sus parámetros guardados
(360, sampling 0, intensity 100) no implican que esté activo. Ese tratamiento
pertenece a la pieza; el tamaño del monitor es otra propiedad.

Las mediciones se hicieron en serie, en ventanas Cocoa reales. El runner devuelve
el control al event loop exterior de Qt entre operaciones; la ventana de prueba
usa always-on-top para mantener el monitor expuesto. No se utiliza la plataforma
offscreen para tiempos. Las pruebas funcionales se ejecutan por separado.

El cuadro recibido por la UI y el cuadro pintado tienen marcas diferentes. La
finalización exige el paquete, generación, frame absoluto y, en A/B, propietario,
efecto y lado correctos. Un cuadro intermedio durante el debounce de selección no
puede completar una muestra del candidato. El retorno de `paintEvent` confirma
el dibujo de Qt; no mide la composición de WindowServer ni el scanout físico.

El baseline interactivo desactiva la preparación automática para aislar cada
operación. La sesión de diez minutos y las preparaciones públicas la ejercitan
por separado. Reiniciar Python no vacía la caché de disco del sistema.

## Baseline Full canvas

Cada celda de las interacciones repetidas muestra **mediana / p95 en ms**, con
20 observaciones. El p95 es nearest-rank; las muestras originales están guardadas.

| Caso | Seek sin caché | Seek cacheado | Editar clip | Editar proyecto | Soltar slider |
| --- | --- | --- | --- | --- | --- |
| Guerrilla | 1149.3 / 1236.0 | 30.7 / 45.5 | 1648.5 / 1690.0 | 1808.4 / 1857.9 | 1605.4 / 1698.1 |
| Text | 161.8 / 180.1 | 44.7 / 47.3 | 890.5 / 928.8 | 1150.6 / 1199.9 | 1176.9 / 1249.5 |
| Memory | 321.2 / 505.3 | 6.3 / 7.4 | 339.6 / 367.8 | 344.9 / 385.0 | 344.7 / 366.2 |
| Color film | 973.5 / 1044.5 | 6.5 / 7.4 | 1113.0 / 1131.5 | 1110.9 / 1155.9 | 1169.1 / 1194.7 |
| Video | 380.8 / 405.9 | 6.7 / 7.6 | 512.7 / 533.1 | 508.6 / 531.0 | 504.3 / 545.2 |

El estado «sin caché» vacía la caché de cuadros y mantiene los recursos ya cargados.
«Cacheado» solicita inmediatamente el mismo frame. La navegación natural retiene
la caché y sigue una secuencia fija con avances, retrocesos, cortes y revisitas.

| Caso | Navegación natural | Hits / 20 | Abrir navegador (n=1) | Seleccionar candidato | Before | Preview |
| --- | --- | --- | --- | --- | --- | --- |
| Guerrilla | 588.5 / 1215.3 | 10 | 2764.7 | 2802.7 / 2856.9 | 1230.3 / 1262.9 | 139.8 / 145.1 |
| Text | 106.3 / 169.6 | 10 | 1329.7 | 1253.4 / 1278.8 | 271.0 / 293.9 | 157.3 / 164.2 |
| Memory | 6.2 / 429.3 | 16 | 806.5 | 641.1 / 670.8 | 300.1 / 310.9 | 106.7 / 113.7 |
| Color film | 6.0 / 964.2 | 16 | 1492.9 | 2091.1 / 2234.6 | 1081.5 / 1140.6 | 113.3 / 116.8 |
| Video | 6.8 / 496.1 | 14 | 999.7 | 921.9 / 960.4 | 491.0 / 535.5 | 106.9 / 116.1 |

La apertura del navegador se muestra individualmente: incluye la selección del
candidato inicial. Los cambios de candidato y de lado tienen 20 observaciones.
El navegador alterna candidatos disponibles no aplicados y comprueba Full canvas.
La medición de navegación no reproduce el loop de comparación de hasta 12 fps.

### Aperturas y recursos cargados

| Caso | Proceso nuevo (ms) | Construcción (ms) | Reabrir (ms) | Parte síncrona al reabrir (ms) |
| --- | --- | --- | --- | --- |
| Guerrilla | 6610.4 | 6151.1 | 5089.8 | 3369.5 |
| Text | 6017.8 | 5595.0 | 6130.0 | 4710.8 |
| Memory | 4617.2 | 4171.6 | 6090.1 | 4508.7 |
| Color film | 4657.1 | 4003.0 | 4934.0 | 3594.7 |
| Video | 4779.1 | 4343.0 | 4464.1 | 3327.8 |

Cada apertura de esta tabla es una observación costosa individual, no un
percentil. «Proceso nuevo» incluye el lanzamiento del subproceso Python, imports,
carga del documento, construcción, render y pintura. «Construcción» empieza
después de imports/carga. «Reabrir» reemplaza el documento en memoria con los
recursos del proceso ya cargados; incluye reconstruir su inspector.
Estas fronteras no son tiempos de lanzamiento desde Finder.

### Edición y arrastre

Las ediciones alternan 0,90 / 0,91 sobre Text opacity, Memory light, Solid light o
Bloom strength, en clip y proyecto. Se restaura la base entre alcances para que
un override local no oculte el cambio global. Los hashes confirman que las dos
entradas producen dos imágenes diferentes y que restaurar recupera la referencia.

El arrastre usa ocho eventos de movimiento sobre un slider visible, conservando
tracking=False; se comprueba que no cambió la generación antes de soltarlo.
En Guerrilla usa Bloom strength; en los otros casos, el parámetro de edición
indicado arriba. La columna de arrastre mide **soltar → pintura final**.

La ráfaga de estrés confirma ocho valores a intervalos nominales de 15 ms; sus
tiempos reales se guardan. Es una carga distinta del arrastre que confirma al
soltar. En documentos grandes, los callbacks síncronos impiden despacharlos con
esa cadencia.

| Caso | Última entrada → pintura (med / p95 ms) | Primera entrada → pintura (med ms) | Despachar ocho valores (med ms) | Press → último move QTest (med ms) |
| --- | --- | --- | --- | --- |
| Guerrilla | 1785.2 / 1863.5 | 5335.0 | 3574.7 | 0.5 |
| Text | 1219.0 / 1299.7 | 7071.6 | 5858.6 | 0.5 |
| Memory | 346.9 / 366.6 | 588.0 | 243.7 | 0.5 |
| Color film | 1131.2 / 1200.8 | 1384.6 | 252.3 | 0.6 |
| Video | 502.3 / 536.7 | 669.7 | 159.8 | 0.5 |

El delay nominal de QTest no produjo pausas de 15 ms en Cocoa: los movimientos
se despacharon en menos de 1 ms, según sus marcas originales. Este es un
arrastre sintético rápido que confirma al soltar, no una medición de latencia
de un dispositivo físico. Los valores de clip/proyecto conservan los callbacks
reales de edición. No se atribuye al render todo el tiempo de la ráfaga.

## Preparación, video y memoria

| Caso | Lista fija | Auto (s) | Explícita (s) | Frames/s explícita |
| --- | --- | --- | --- | --- |
| Guerrilla | [0, 1, 93, 140] | 4.270 | 4.242 | 0.94 |
| Text | [0, 1, 150, 225] | 0.516 | 0.484 | 8.27 |
| Memory | [0, 1, 120, 180] | 1.092 | 1.139 | 3.51 |
| Color film | [0, 1, 125, 187] | 3.769 | 3.850 | 1.04 |
| Video | [0, 1, 29, 30] | 1.741 | 1.788 | 2.24 |

Cada celda de preparación es una ejecución individual; no se calcula p95.

Las listas de cuatro frames usan el batching y las reservas normales, fijando el
target directamente. Esa prueba excluye el timer público automático de 400 ms.
La prueba pública de Guerrilla conserva sus listas efectivas y mide por separado
los dos accesos, incluido ese timer. No se reduce resolución para ampliar la lista.

La preparación pública de Guerrilla completó exactamente `[0..31]` en
34,686 s (automática) y 34,447 s (explícita), aproximadamente 0,93 frames/s.
La lista contiene 32 cuadros Full; el límite permite 16 por lado en comparación
cuando ambos bancos deben reservar espacio. El máximo global observado de
caché más reservas fue 189.84 MiB, con cero violaciones del presupuesto de 192 MiB.

La importación real del video tardó 5,397 s, partiendo del documento de bootstrap
Text; la creación del proxy registrada por el proveedor tardó 0,215 s. Ese primer
arranque no se etiqueta como apertura fría de video. Las aperturas y seeks de la
cohorte `baseline-video-full` usan después el documento importado y el proveedor
normal: no se resta el tiempo del proxy a un seek ni se supone disco frío.

### Sesión de diez minutos

Se completaron 120 acciones durante 603,681 s, incluido el asentamiento final:
seek, edición, undo, seek, abrir candidato, Before, Preview y cerrar comparación,
una acción programada cada cinco segundos. La preparación automática estuvo
activada; al final se canceló y se esperaron tres segundos adicionales de calma.
Las marcas de acción son de finalización e incluyen trabajo síncrono; no son
marcas de llegada del input. No se reprodujo audio: sí se ejecutan los callbacks
de sincronización del scrub y se comprueban los contratos de audio en tests.

El pulso nominal de 20 ms obtuvo 28237 intervalos: mediana
20.022 ms, p95 24.333 ms, máximo 745.9 ms.
Hubo 45 intervalos mayores de 100 ms y 41 mayores de 500 ms.
Son huecos del event loop, no latencias de todas las acciones de la sesión.

RSS propio: mediana de los primeros 30 s 1487.2 MiB
(n=29), últimos 30 s 1633.8 MiB (n=28),
última muestra 1624.6 MiB y pico 1829.0 MiB.
El pico observado de hijos dentro de la sesión fue 0 MiB; en el registro completo
del proceso, incluida la apertura, fue 2,2 MiB. La caché más reservas
alcanzó 53.39 MiB durante esta sesión.
El RSS descendió después de algunos picos; no es una rampa monotónica.

RSS es la memoria residente del proceso, distinta de la caché RGB y de physical
footprint. Los hijos se muestrean por separado cada segundo; ese intervalo puede
omitir picos transitorios. La curva no monotónica de una sesión de diez minutos
no prueba ni descarta una fuga a más largo plazo.

## Instrumentación, escalado y atribución

| Control ABBA (n=20 por estado) | Sin caché med / p95 ms | Cacheado med / p95 ms |
| --- | --- | --- |
| observer-1-standard | 1111.0 / 1133.3 | 30.1 / 32.5 |
| observer-2-quiet | 1053.5 / 1062.4 | 30.2 / 31.4 |
| observer-3-quiet | 1053.9 / 1064.9 | 29.7 / 30.8 |
| observer-4-standard | 1125.1 / 1149.5 | 30.8 / 32.7 |

Quiet retiene las marcas mínimas de recepción/pintura y las muestras, y retira
logging de workers, pulso y RSS. Las medianas sin caché de las pasadas normales
excedieron las quiet en aproximadamente 57–72 ms; ese es el costo observado
del conjunto de observadores más la variación entre pasadas, con orden ABBA.
Las medianas cacheadas quedaron entre 29,7 y 30,8 ms. No se resta ese costo
a las tablas ni se atribuye a un observador particular. Este control
no cuantifica el costo común de los hooks mínimos; los tiempos cacheados
de pocos milisegundos son especialmente sensibles a esa base de medición.

| Caso | Escenario | Control sin profiler (ms, n=2) | Con profiler (ms, n=2) |
| --- | --- | --- | --- |
| guerrilla | scrub_uncached | 1108.9, 1123.0 | 1224.9, 1221.1 |
| guerrilla | project_parameter | 1807.0, 1791.0 | 2726.0, 2675.1 |
| guerrilla | candidate_select | 2884.7, 2953.9 | 3522.7, 3451.5 |
| text-dye-transfer | scrub_uncached | 157.8, 155.2 | 268.6, 267.7 |
| text-dye-transfer | project_parameter | 1316.7, 1321.1 | 2793.9, 2625.1 |
| text-dye-transfer | candidate_select | 1247.0, 1244.4 | 2179.9, 2372.3 |

cProfile altera materialmente los tiempos; ninguna cifra perfilada entra en
el baseline. La calibración local de Python 3.14.6 verificó que un colector
registra UI y workers. Un segundo colector simultáneo es rechazado por el
runtime; ese intento fallido se excluyó. Se conserva un único `process.prof`
por diagnóstico, spans con thread y un muestreo nativo independiente. Los
contadores acumulados globales pueden superponer actividad entre threads;
no se usan como porcentajes del tiempo de pared ni se suman entre sí.
Las esperas del monitor de RSS tampoco se atribuyen a la interfaz.

El par enfocado de preparación de Guerrilla dio 4,404 / 4,427 s sin profiler
y 4,725 / 4,598 s con profiler (auto / explícita, cuatro frames, n=1 por modo).
El par de render enfocado en frames 0 y 93 dio 1128,6 y 1143,5 ms sin profiler,
1224,6 y 1208,9 ms con profiler. Son observaciones individuales adicionales;
no se incorporan a los percentiles del baseline ni se mezclan con frames 0 y 1.

### Control de escala

| Caso | Dimensiones modo 720 | Full, frames 0 y 1 (ms) | 720, mismos frames (ms) |
| --- | --- | --- | --- |
| Guerrilla | [405, 720] | 1129.9, 1111.8 | 351.9, 215.4 |
| Text | [720, 406] | 330.6, 166.1 | 166.9, 153.0 |
| Memory | [540, 720] | 213.8, 209.9 | 285.3, 123.0 |
| Color film | [405, 720] | 1002.4, 999.9 | 353.3, 320.1 |
| Video | [720, 405] | 398.2, 401.5 | 64.2, 84.6 |

Son dos observaciones individuales por calidad, con FPS y tiempos de fuente
idénticos. Text ya tiene 720 × 406 en Full: funciona como control del mismo
tamaño, cuya dispersión no debe interpretarse como escalado. En video, 720
también cambia a la ruta del proxy: la comparación incluye decodificación
y no aísla solamente el número de píxeles. Ninguna reducción se propone
como mejora de Full ni se exige igualdad RGB entre dos tamaños diferentes.

### Atribución comprobada y límites

El relevamiento de los cinco casos (`survey-selection.json`) seleccionó Guerrilla
por costo de render y Text por costo de edición/interfaz. Los siguientes hallazgos
combinan medidas normales, spans diagnósticos y lectura del flujo actual:

- **Trabajo síncrono de edición:** Guerrilla ocupa 370,9 / 513,4 ms de mediana
  en el callback de clip/proyecto; Text, 519,2 / 775,5 ms. Esto sucede antes de
  devolver el control al event loop. Con profiler, `CompositionPanel.commit`
  contiene `refresh`, y este pasa por controles, resúmenes y resolución de estados.
  Los spans diagnósticos de `refresh` fueron 1176,7 ms de mediana en Guerrilla
  y 1800,6 ms en Text (27 llamadas cada uno); son tiempos perturbados, usados
  para localizar trabajo, no para sustituir las medidas normales.
- **Catálogo y copias repetidas:** `_state_preset` llama a `curated_presets()`
  y copia el preset elegido. `curated_presets` obtiene y recorre el catálogo,
  incorpora módulos y mezcla defaults para cada entrada. El perfil completo de
  Guerrilla registró 26 231 llamadas totales al catálogo; el de apertura, 1356.
  Es evidencia de repetición, no de que eliminar todas las copias sea correcto.
  En el perfil de preparación también aparecen normalización y copias, pero
  no se aisló una fracción normal suficiente para prometer una ganancia concreta.
- **Render de trabajo descartado al cambiar candidato:** `selection_changed`
  termina la comparación; `end_comparison` fuerza invalidación del documento
  de trabajo. Luego el debounce de 300 ms prepara el candidato y cancela ese
  trabajo. En las 20 selecciones de Guerrilla hubo 20 workers cancelados que
  siguieron ejecutándose tras la petición de cancelación: cola residual mediana
  872,2 ms. Color film: 20 y 789,3 ms; Memory: 20 y 21,4 ms; video: 20 y
  183,3 ms. Text no mostró ese worker cancelado en estas 20 selecciones: el
  render breve puede terminar antes. No se generaliza la magnitud entre casos.
- **Ejemplo normal de una selección de Guerrilla:** con respecto al input,
  el render transitorio empezó en +101,6 ms, recibió cancelación en +768,6 ms,
  terminó en +1623,5 ms; el candidato empezó en +1625,0 ms y terminó en
  +2737,4 ms; su pintura correcta terminó en +2770,6 ms. Son fronteras de
  un mismo timeline, no duraciones que deban sumarse de nuevo.
- **Reuso A/B:** las 20 visitas a Before de cada caso produjeron una sola
  identidad RGB por caso, pero ninguna fue cache hit. Preview sí volvió al
  candidato ya cacheado. Cada candidato crea un token y la invalidación fuerza
  limpiar los bancos; conservar Before exigiría demostrar identidad de todas sus
  dependencias y mantener el aislamiento de propietarios.
- **Construcción de controles:** reabrir ocupa síncronamente 3,33–4,71 s en
  estas cinco aperturas normales. En el diagnóstico de apertura, reconstruir
  módulos ocupó 4,604 s acumulados; se construyeron 94 secciones de efectos
  (2,451 s acumulados). Visibilidad y constructor del inspector están anidados
  en esa fase. Las miniaturas también generan renders pequeños: los conteos
  de `render_synth_frame` de una apertura no equivalen a cuadros Full.
- **Trabajo nativo:** `native-stack.txt` confirma actividad en Gaussian/BoxBlur
  de Pillow y operaciones de NumPy durante los workers. El perfil enfocado de
  render registra 90 llamadas nativas gaussian_blur, 0,726 s propios en total,
  dentro de un proceso diagnóstico que también abre controles y miniaturas.
  No se divide esa cifra por los dos seeks ni se convierte en porcentaje de
  latencia Full. La codificación PNG vista en el hilo principal pertenece al
  guardado de referencias del runner, fuera de las ventanas de interacción;
  no se propone eliminarla del producto.

La recepción no equivale a presentación: en Guerrilla, recepción → retorno de
pintura dio medianas de aproximadamente 29–35 ms en edición/A-B; Text, 39–49 ms.
El resultado cacheado de Preview aún incluye programación/debounce y UI. Tampoco
es una medida aislada del costo de blit. No se identificó un cambio seguro de
kernels, conversiones, proveedor de video o geometría con beneficio cuantificado
y RGB exacto demostrado. Los 34,45 s de preparación Full son costo real; este
informe no promete resolverlos con las oportunidades de interfaz.

El muestreo `vmmap` del proceso diagnóstico registró physical footprint de
811 MB (pico 1,0 GB), distinto del RSS de la sesión larga. Regiones grandes de
malloc retenidas y páginas de librerías contribuyen a memoria fuera de la caché
RGB. Este muestreo es compatible con retención del allocator; no permite
atribuir cada MiB ni afirmar que no existan fugas.

## Oportunidades priorizadas

Los límites de beneficio corresponden a costos observados que, como máximo,
podrían eliminarse por completo. No son mejoras implementadas ni porcentajes
prometidos. No se suman funciones anidadas ni tiempos de UI y worker superpuestos.

### 1. Reducir la resolución repetida de estados y los refrescos del inspector

**Escenario y evidencia:** edición de clip/proyecto y ráfagas, especialmente Text
(73 clips) y Guerrilla (45). Los callbacks normales consumen 0,37–0,78 s por
entrada; los spans sitúan buena parte del trabajo en `commit → refresh`, junto
con resolución de presets y resúmenes. La ráfaga acumula ese costo antes de que
puedan llegar las entradas siguientes.

**Primer parche recomendado:** experimentar con un snapshot inmutable del
catálogo y la resolución de estados dentro de una sola transacción de refresco,
y evitar recalcular resúmenes idénticos. Medir primero ese alcance limitado;
no compartir diccionarios mutables entre documentos ni conservarlos entre
transacciones sin una clave completa.

**Límite de beneficio:** eliminar el callback completo solo podría recuperar
hasta su duración observada: medianas de 371/513 ms en Guerrilla y 519/775 ms
en Text, clip/proyecto. El trabajo obligatorio permanecerá y los renders se
superponen con otras fases; no se promete que esa resta aparezca íntegra en
editar → pintura. **Dificultad:** media. **Riesgos:** defaults históricos,
mutación cruzada, resumen atrasado, overrides, controles ocultos y undo/redo.
**Validación:** repetir las 20 ediciones y ráfagas, medir spans sin profiler,
comparar RGB exacto, documento e historia, abrir todas las pestañas tras editar
y pasar frozen-study, scope, reuse y compatibilidad de proyectos.

### 2. Evitar iniciar el render transitorio que una selección va a descartar

**Escenario y evidencia:** cambiar candidato cuesta 2802,7 ms de mediana en
Guerrilla y 2091,1 ms en Color film. La secuencia de invalidación y los 20
workers cancelados por caso muestran trabajo del documento base antes del
candidato. La cola residual tras cancelar es 872,2 / 789,3 ms de mediana.

**Posible parche:** una transición explícita entre candidatos que conserve las
garantías de invalidación y espere el nuevo propietario sin solicitar ese render
intermedio. **Límite:** la cola residual observada es el techo de espera directa
que esta causa explica; no todo el render descartado retrasa al candidato.
No se estima para Text, donde este patrón no produjo cancelación observada.
**Dificultad:** media. **Riesgos:** mostrar un frame antiguo, cerrar la exploración
en un estado vacío, seleccionar un efecto ya aplicado o cambiar documento/scope
durante el debounce. **Validación:** mismo timeline con 20 cambios, selección
rápida/escape/cierre, checks de owner/generación, Full canvas y RGB; confirmar
que desaparece el worker redundante y que la cancelación sigue siendo correcta.

### 3. Conservar Before cuando se pruebe que su contenido es idéntico

**Escenario y evidencia:** Before en Guerrilla tarda 1230,3 ms de mediana,
frente a 139,8 ms para retornar al Preview cacheado. Sus 20 referencias Before
son RGB idéntico y todas fueron misses; cambiar candidato renueva el owner y
limpia los bancos. También ocurre en los otros cuatro casos.

**Límite:** como máximo el render de Before y la espera que provoque; la duración
total observada de 1230,3 ms es un techo absoluto, no una predicción de ahorro.
La programación, pintura y comprobaciones permanecen. No sumar este techo al
de la oportunidad 2: pueden afectar fases relacionadas. **Dificultad:** media/alta.
**Riesgos:** confundir propietarios A/B, media externa modificada, tiempo, seed,
clocks de efectos/fuente, audio reactivo o parámetros implícitos. **Validación:**
clave completa de identidad, generaciones separadas, secuencias A/B no lineales,
cambios de fuente y documento, RGB exacto y contabilidad global de 192 MiB
incluyendo reservas; no aumentar el presupuesto.

### 4. Construir controles no visibles cuando se necesiten

**Escenario y evidencia:** abrir/reabrir documentos tarda varios segundos aun
con recursos cargados. Se construyen 94 secciones de efectos en la apertura
perfilada; `_rebuild_modules` identifica el trabajo pesado del inspector.
**Límite:** la parte síncrona normal de reabrir (3,33–4,71 s, n=1 por caso)
es el techo de toda la fase. Solo una fracción corresponde a controles que
puedan diferirse; las cifras del profiler no se suman ni se usan como ganancia.
**Dificultad:** media/alta. **Riesgos:** primera apertura de una pestaña lenta,
señales duplicadas, controles ausentes, estado desactualizado y accesibilidad.
**Validación:** aperturas nuevas y calientes por separado, interacción inmediata,
abrir todos los inspectores, editar/undo/redo/cambiar documento antes de abrirlos;
misma imagen y comportamiento, midiendo también el costo trasladado a la primera
visita. La oportunidad 1 puede reducir parte de esta fase: no sumar ambos techos.

La normalización por frame, la vida de proveedores y los intermediarios del
render quedan como hipótesis para una medición más acotada. El muestreo confirma
trabajo nativo, pero no justifica una quinta propuesta de ganancia segura.
No se recomienda GPU, más concurrencia ni cambios de calidad con esta evidencia.

## Comprobación instalada y validación

La app instalada declara 0.48.1 y usa Python 3.14 con las dependencias registradas
en `installed-metadata.json`. Se abrió una segunda instancia propia (PID 65162),
con estado aislado, cuyo documento inicial es «Refined signal». No se editaron
ni guardaron documentos en ella.

**Comprobación de interacción en el bundle pendiente:** la herramienta macOS
resuelve las dos instancias al mismo bundle ID y devuelve siempre la ventana
original «Guerrilla Radio» (PID 94173). Se intentó volver a enlazar por ruta,
nombre y tras reiniciar la conexión; el usuario puso «Refined signal» al frente
en su segunda pantalla y la herramienta siguió devolviendo la original. No hay
selector de PID/ventana documentado para macOS en esta interfaz. Se evitó enviar
inputs a una instancia cuya identidad no era la de prueba. Por ello no hay
latencias ni validación visual de los cinco casos en el bundle instalado.
Los tiempos de este informe son del código fuente en ventanas Cocoa reales.
Este límite impide dar por completada la comprobación instalada del plan.
Se terminó únicamente la instancia de prueba PID 65162; se confirmó que la
original PID 94173 seguía abierta.

La batería pertinente terminó con **120 passed, 1 skipped en 633,98 s** y salida
0: `test_synth_preview_reuse`, `test_synth_preview_scope`, `test_synth_preview_ux`,
`test_synth_effect_discovery_ui`, `test_synth_exploration_ui`,
`test_synth_exploration` y `test_synth_soundtrack_preview`. Se ejecutó después
de las mediciones, con estado aislado y Qt offscreen solo para tests. La prueba
omitida es el smoke opt-in de codec/dispositivo de audio
(`NEBULA_AUDIO_SMOKE=1`); los contratos automatizados de reloj, seek y sincronía
pasaron. La escucha y la sincronía audiovisual real no quedan certificadas por
esta ejecución.

Se verificaron 54 PNG de referencia de las cinco cohortes contra sus hashes
PNG, dimensiones y bytes RGB. Cada caso recuperó el hash inicial al restaurar
frame cero; las ediciones alternadas dieron dos imágenes distintas en ambos
alcances. Las capturas finales del viewer de los cinco casos también se
inspeccionaron visualmente. Son capturas del viewer Qt del código fuente.

Los hashes finales del original de Guerrilla, su audio, las cinco copias y los
31 recursos coinciden con los iniciales. `validation-final.json` conserva las
comprobaciones y el resultado de tests. La comparación con el commit inicial
confirma que los cambios de auditoría afectan únicamente herramientas y
documentación. No hay cambios de renderizador, instalación, versión ni merge.

## Evidencia y reproducción

- Runner: [`tools/audit_synth_preview.py`](../tools/audit_synth_preview.py).
- Instrucciones: [`preview-performance-audit-runner.md`](preview-performance-audit-runner.md).
- Resumen reproducible: [`tools/summarize_synth_audit.py`](../tools/summarize_synth_audit.py).
- Evidencia local, deliberadamente fuera de Git: `output/preview-performance-audit/`.
  `manifest.json` contiene casos, recursos, parámetros, frames y hashes;
  cada etiqueta tiene `events.jsonl`, `samples.json` y referencias PNG con hashes
  RGB y PNG separados. `summary.json` conserva estadísticas y originales.
- Cohortes de las tablas: `baseline-guerrilla-full`,
  `baseline-text-dye-transfer-full`, `baseline-image-memory-full`,
  `baseline-color-film-die-full-r2` y `baseline-video-full` (185 muestras cada una,
  contando aperturas y restauración). Sus arrastres son `baseline-slider-*-full`;
  Guerrilla usa la etiqueta `baseline-slider-release-full`.
- `excluded-runs.json` documenta calibraciones, fallos y solapamientos excluidos.
  Se descartaron los prototipos con esperas Qt anidadas/GIL, el error inicial del
  observador de pintura y el intento de dos colectores cProfile simultáneos.
  Ninguno constituye un cuello de botella de la aplicación.
- Los benchmarks de otra tarea se esperaron según la preferencia del usuario.
  El supervisor detuvo solo sus procesos de auditoría cuando reaparecieron; los
  intentos de Color film con solapamiento se excluyeron completos. Las tablas
  basales usan únicamente las cinco cohortes finales completas y sus arrastres.

Una futura mejora debe repetir estas entradas a la misma calidad, verificar RGB
exacto en el mismo entorno, clocks/semillas/automatizaciones/orden e intensidad,
undo/redo, cancelación, propiedad A/B, audio, export y el presupuesto de 192 MiB
con reservas. El control 720 es un estudio de escala, no una mejora del baseline.
