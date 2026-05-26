# Local Live Translator EN -> ES

MVP local para Windows 10/11 que captura audio de salida del sistema con WASAPI loopback, transcribe ingles con `faster-whisper` y traduce offline a espanol con Argos Translate.

No usa APIs externas para transcribir ni traducir. Argos solo necesita internet la primera vez para descargar el paquete `en -> es`; despues la traduccion funciona offline.

## Estado actual

Implementadas las fases de consola:

- Fase 1: listado de dispositivos y captura WASAPI loopback a WAV.
- Fase 2: transcripcion local con `faster-whisper`.
- Fase 3: traduccion offline con Argos Translate.
- Fase 4: pipeline continuo por consola.

La UI tkinter esta intencionalmente bloqueada hasta validar:

1. `output/test_capture.wav` contiene audio real del sistema.
2. `scripts/test_transcribe_file.py` transcribe ese audio en ingles.
3. `app/translator.py` traduce ingles -> espanol offline.

## Requisitos

- Windows 10/11.
- Python 3.10 o 3.11.
- Audio reproduciendose por el dispositivo de salida que se quiere capturar.

## Instalacion

Desde `E:\OneDrive\Documentos\APPs\local-live-translator`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si usas Python 3.10:

```powershell
py -3.10 -m venv .venv
```

## Fase 1: audio del sistema

Listar dispositivos:

```powershell
python scripts/list_audio_devices.py
```

Grabar 10 segundos de audio del sistema:

```powershell
python scripts/test_capture_to_wav.py
```

Salida esperada:

```text
output/test_capture.wav
```

El script selecciona un dispositivo `LOOPBACK` por defecto. Si se pasa `--device-index`, ese dispositivo debe ser loopback; el codigo rechaza microfonos o entradas normales.

Ejemplo con indice explicito:

```powershell
python scripts/test_capture_to_wav.py --device-index 12 --seconds 10
```

## Fase 2: transcripcion local

Transcribir el WAV capturado:

```powershell
python scripts/test_transcribe_file.py output/test_capture.wav
```

Modelo por defecto:

```text
small.en
```

Modelos permitidos:

```text
tiny.en, base.en, small.en, medium.en
```

CPU por defecto:

```powershell
python scripts/test_transcribe_file.py output/test_capture.wav --device cpu --compute-type int8
```

GPU NVIDIA compatible:

```powershell
python scripts/test_transcribe_file.py output/test_capture.wav --device cuda --compute-type float16
```

## Fase 3: Argos Translate offline

Instalar o verificar el paquete English -> Spanish:

```powershell
python scripts/install_argos_en_es.py
```

Este paso puede requerir internet. Una vez instalado, la traduccion en runtime usa el paquete local.

## Fase 4: pipeline por consola

Ejecutar captura, transcripcion y traduccion en loop:

```powershell
python -m app.pipeline
```

Opciones utiles:

```powershell
python -m app.pipeline --chunk-seconds 4 --model small.en --device cpu --compute-type int8
python -m app.pipeline --chunk-seconds 3 --model base.en --audio-device-index 12
```

Salida esperada:

```text
EN: transcribed English text
ES: texto traducido al espanol
```

El pipeline evita imprimir traducciones identicas consecutivas.

## Configuracion

Editar `app/config.py`:

- `CHUNK_SECONDS`: tamano de chunk para el pipeline.
- `AUDIO_DEVICE_INDEX`: `None` para autoseleccion loopback o indice explicito.
- `WHISPER_MODEL`: `tiny.en`, `base.en`, `small.en`, `medium.en`.
- `WHISPER_DEVICE`: `cpu` o `cuda`.
- `WHISPER_COMPUTE_TYPE`: `int8` para CPU, `float16` para CUDA compatible.

## Troubleshooting

### 1. Solo aparece microfono y no loopback

- Ejecutar `python scripts/list_audio_devices.py`.
- Confirmar que Windows tiene un dispositivo de salida activo.
- Reproducir audio antes de correr la captura.
- Revisar que `PyAudioWPatch` este instalado dentro del venv activo.
- Si no hay ningun dispositivo `LOOPBACK`, no fuerces un microfono: el MVP requiere WASAPI loopback.

### 2. No se escucha audio en el WAV

- Verificar que haya audio reproduciendose durante los 10 segundos.
- Probar otro dispositivo marcado `LOOPBACK` con `--device-index`.
- Confirmar que el audio sale por ese dispositivo y no por HDMI/Bluetooth distinto.
- Abrir `output/test_capture.wav` en un reproductor o editor de audio y revisar forma de onda.

### 3. faster-whisper no detecta GPU

- Probar primero CPU:

```powershell
python scripts/test_transcribe_file.py output/test_capture.wav --device cpu --compute-type int8
```

- Para CUDA, confirmar drivers NVIDIA y runtime compatible con CTranslate2.
- Si `--device cuda --compute-type float16` falla, no es un error del pipeline: es entorno GPU/CUDA.

### 4. Argos no tiene instalado el paquete en-es

Ejecutar:

```powershell
python scripts/install_argos_en_es.py
```

Si el equipo debe quedar offline, hacer este paso una vez con internet y luego volver a probar sin red.

### 5. Latencia alta

- Reducir `CHUNK_SECONDS` de 4 a 3.
- Usar `base.en` o `tiny.en`.
- En CPU mantener `compute_type=int8`.
- Evitar `medium.en` salvo que la precision sea mas importante que la latencia.
- Cerrar apps que consuman CPU/GPU.

## UI

`app/ui.py` existe solo como bloqueo explicito. No se debe implementar ni usar hasta que las tres validaciones de consola pasen.
