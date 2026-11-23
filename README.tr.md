# gemini-omni-mcp v3.0

Claude Code, Cursor, Codex, Antigravity ve tüm MCP istemcileri için geliştirilmiş **yalın, güvenlik sertleştirmeli Google GenAI Çok Modlu (Multimodal) & Ajan MCP Sunucusu**.

- [English (README.md)](README.md) | **Türkçe**

---

## v3.0.0 Yenilikleri

1. **Varsayılan 6 Çekirdek Araç (`--toolsets core`):** Ajan bağlam penceresi (context window) şişmesini önlemek için varsayılan araç sayısı 18'den **6 yüksek etkili çekirdek araca** indirildi (`gemini_image`, `gemini_video`, `gemini_audio`, `gemini_analyze`, `gemini_docs`, `gemini_budget`).
2. **Modüler İsteğe Bağlı Araç Setleri:** Toplu ajan sürüsü (`swarm`: `+3`), yönetilen araştırma ajanı (`research`: `+1`) veya 3D/Blender RLAIF (`3d`: `+3`, **varsayılan olarak KAPALI**) yalnızca ihtiyaç duyulduğunda `--toolsets` veya `GEMINI_OMNI_TOOLSETS` ile açılır (`all` toplam 13 aracı yükler).
3. **`google-genai >= 3.2.0` (`3.6.1+`) SDK Uyumluluk Düzeltmeleri:**
   - `interactions` ve `voices` çağrıları için açık `api_version="v1beta"` yönlendirmesi (`gemini_video`, `gemini_audio`, `gemini_deep_research`).
   - Modele duyarlı `thinking_level` normalizasyonu (`normalize_thinking_level` / `build_thinking_config`): Gemini 4'te `minimal -> low` kırpılır, Carbon/Argon/3.x modellerinde `xhigh -> high` kırpılır, Gemma 4'te `ThinkingConfig` otomatik atlanır.
4. **Varsayılan Güvenlik Kalkanları:**
   - **Çalışma Alanı (Workspace) Koruması:** `resolve_path()` varsayılan olarak `GEMINI_OMNI_WORKSPACE` dışındaki okuma/yazma erişimlerini engeller (`GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false`).
   - **Alt Süreç Sertleştirmesi:** `gemini_3d_judge_and_autopatch` Blender'ı `shell=False` argüman listesiyle çalıştırır; özel `render_command` komutu yalnızca `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=true` verildiğinde açılır.
   - **Sıfır Maliyetli Dokümantasyon & SSRF Koruması:** `gemini_docs` API anahtarı olmadan çalışır (`gemini-api-docs-mcp.dev` + `llms.txt` yedeği) ve yalnızca izin verilen HTTPS alan adlarına izin verir.

---

## Varsayılan Çekirdek Araçlar (6 Araç)

| Araç | Varsayılan Model / API | Ne Yapar? |
| --- | --- | --- |
| `gemini_image` | `gemini-nano-banana-2.1` | `action="generate"` (metinden görsel + 14 referansa kadar füzyon + presetler) veya `edit` / `inpaint` / `outpaint` / `upscale` |
| `gemini_video` | `gemini-omni-1.2-flash` (`v1beta`) | `generate`, `extend`, `edit`, `seamless_loop` (`3s`–`15s`, `360p`–`4K`, iki kare arası interpolasyon) |
| `gemini_audio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, Voices API, `lyria-3.5` (`v1beta`) | Konuşma sentezi (`tts`), deşifre (`text`/`md`/`json`/`srt`), ses tasarımı/klonlama ve `lyria-3.5` müzik |
| `gemini_analyze` | `gemini-4-hydrogen` (varsayılan), `gemini-4-neon`, isteğe bağlı `gemini-4-carbon`, `gemma-4-31b-it` | PDF, görsel, ses, video, kod/CSV, `files/<id>` ve YouTube URL analizi + Google Search + Code Execution |
| `gemini_docs` | `gemini-api-docs-mcp.dev` (Ücretsiz) | `action="search"` (canlı doküman arama + `llms.txt` yedeği) ve `action="fetch"` (chunk ID veya Markdown sayfası) |
| `gemini_budget` | FinOps Defteri + `client.models` | Canlı USD harcama özeti, `OMNI_HARD_STOP_LIMIT_USD` kesicisi, canlı model kataloğu ve toplu iş (Batch) maliyet hesabı |

---

## İsteğe Bağlı Araç Setleri (`--toolsets` / `GEMINI_OMNI_TOOLSETS`)

| Set | Eklenen Araçlar | Örnek Kullanım |
| --- | --- | --- |
| `swarm` (`+3`) | `gemini_async_swarm`, `gemini_context_cache`, `gemini_files` | `--toolsets core,swarm` |
| `research` (`+1`) | `gemini_deep_research` | `--toolsets core,research` |
| `3d` (`+3`, **Varsayılan Kapalı**) | `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `gemini_3d_judge_and_autopatch` | `--toolsets core,3d` |
| `all` (`13` araç) | Tüm araç setlerini aynı anda yükler | `--toolsets all` |

---

## Hızlı Kurulum

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync
uv run gemini-omni-mcp --list-tools
```

[`.env.example`](.env.example) dosyasını çalışma dizininize `.env` olarak kopyalayın:

```dotenv
GEMINI_API_KEY=your-gemini-api-key-here
OMNI_HARD_STOP_LIMIT_USD=50.0
GEMINI_OMNI_TOOLSETS=core
GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false
GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=false
```

> **Bütçe Güvenliği İpucu:** Yerel `OMNI_HARD_STOP_LIMIT_USD` korumasının yanında Google Cloud / AI Studio fatura panelinden de mutlaka sert aylık limit tanımlayın.

### Geliştirme & Test

```bash
uv sync --extra dev
uv run --extra dev pytest -v
```

---

## Lisans

MIT — bkz. [LICENSE](LICENSE).
