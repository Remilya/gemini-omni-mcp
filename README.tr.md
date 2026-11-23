<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP

**Hepsi Bir Arada Google GenAI Multimodal & Agentic MCP Sunucusu**

*Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · Gemini 3.8 Flash Async Swarm · Gemini 4 Argon · Imagen 3 · İfadeli TTS & Voices API · Lyria 3.5 Müzik · Context Caching · Gerçek Zamanlı USD Bütçe Kilidi*

[English](README.md) | **Türkçe**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D2.21.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Neden Gemini CLI Yerine MCP?

Google ekipleri genelde kod editörünün yanında ayrı bir **Gemini CLI** oturumu açmayı önerir; bu da pencere değiştirmek, ayrı bir sohbet bağlamı taşımak ve üretilen çıktıları tek tek projeye aktarmak demektir.

**`gemini-omni-mcp`, Google'ın tüm multimodal ve yüksek eşzamanlı GenAI ekosistemini doğrudan mevcut AI agent'ının içine (Antigravity, Claude Code, Cursor, Codex, VS Code, Claude Desktop) gömer.** Ekstra uygulama açmadan agent'ın tek adımda otonom görsel, video, ses, müzik ve paralel kod işleri üretmesini sağlar:

| Özellik | Ayrı Gemini CLI Uygulaması | `gemini-omni-mcp` |
| --- | --- | --- |
| **İş Akışı Entegrasyonu** | Ayrı terminal açma ve bağlam kopyalama gerektirir | Antigravity, Claude Code, Cursor, Codex ve VS Code içinde doğrudan tool çağrısı |
| **Multimodal Dosya Üretimi** | Çoğunlukla metin/kod sohbeti odaklı | PNG, MP4, WAV/MP3, contact sheet ve JSON çıktıları doğrudan çalışma dizinine kaydeder |
| **Video & Ses Stüdyosu** | Ayrı script veya harici stüdyo ister | Durumlu `gemini-omni-1.2-flash` video (`extend`/`edit`/`loop`), TTS, Voice Design & Lyria 3.5 |
| **Paralel İşçi Sürüsü (Swarm)** | Tek seferde tek etkileşimli istem | `gemini_async_swarm` + Context Caching ile aynı anda **64 paralel asenkron görev** |
| **Maliyet Güvenliği** | Otomatik USD harcama kesicisi yok | Canlı harcama defteri + otomatik `OMNI_HARD_STOP_LIMIT_USD` bütçe kilidi |
| **Yapısal 3D / Görsel Kalite Kontrol** | Serbest metin çıktısı | Katı Pydantic v2 şemaları, PIL piksel örnekleme ve opsiyonel Blender RLAIF otonom yama |

---

## Araç Matrisi (12 Araç: 9 Çekirdek + 3 Opsiyonel 3D/CAD)

### Çekirdek Multimodal, Swarm & Maliyet Araçları (Her Zaman Aktif)

| Araç | Birincil Model(ler) | Yetenekler |
| --- | --- | --- |
| `gemini_image_fusion` | `gemini-nano-banana-2.1`, `gemini-3-pro-image` | 14 adede kadar referans görsel + 1 stil çıpası birleştirme, `freeform` / `character_sheet` / `architectural_sheet` / `story_scene` / `pixel_sprite` ön ayarları, `0.5K`–`4K` `ImageConfig` |
| `gemini_image_edit` | `gemini-nano-banana-2.1` | Görselin kalanını bozmadan bölgesel/konuşmalı düzenleme (6 adede kadar ek referans desteği) |
| `imagen_studio` | `imagen-3.0-generate-002`, `imagen-3.0-capability-001`, `imagen-3.0-upscale-001` | Üretim, maskeli inpaint/outpaint ve 2x/4x yükseltme (Developer API anahtarlarında otomatik Gemini / Lanczos yedekleme) |
| `gemini_video_studio` | `gemini-omni-1.2-flash`, `gemini-omni-1.1-flash` | `3s`–`15s` video üretimi, uzatma (`extend`), düzenleme (`edit`), kesintisiz döngü (`seamless_loop`), başlangıç-bitiş kare interpolasyonu, `1080p`/`4k` için otomatik URI indirme |
| `gemini_audio_studio` | `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`, `lyria-3.5` | `speech_metadata` ile sahne yönergelerini okumayan tek/çok konuşmacılı TTS, Voices API (`voice_design`, `voice_remix`, `voice_replicate`, `voice_list`) ve Lyria 3.5 müzik üretimi |
| `gemini_context_cache` | `gemini-4-argon`, `gemini-3.8-flash` | %95'e varan girdi token indirimi için Context Caching (`client.caches.create`) + deterministik yerel implicit önbellek yedeği |
| `gemini_async_swarm` | `gemini-3.8-flash` (veya seçilen model) | Code Execution, Google Search, JSON Schema ve doğrudan `output_file` yazımı ile 64 eşzamanlı işçiye kadar `asyncio` sürüsü |
| `gemini_curate_refs` | `gemini-3.8-flash` | Aday görsellerden numaralı Pillow JPEG contact sheet oluşturur ve tek seferde en net `top_k` referansı seçer |
| `gemini_cost_and_budget` | Çevrimdışı FinOps Motoru | Anlık harcama özeti (`summary`), 19 modelli `pricing_table`, `calculate_call`, `estimate_batch` (Standard vs Batch), `set_budget_limit`, `reset_ledger` |

### Opsiyonel 3D / CAD RLAIF Paketi (Varsayılan Açık; İsteğe Bağlı Kapatılabilir)

Yalnızca **9 çekirdek araçla** hafif modda çalıştırmak için `GEMINI_OMNI_ENABLE_3D_TOOLS=false` ayarlayın veya `--no-3d-tools` bayrağını verin.

| Araç | Birincil Model(ler) | Yetenekler |
| --- | --- | --- |
| `vision_extract_3d_spec` | `gemini-3.8-flash` + PIL | Piksel medyanı HEX örnekleme + yapısal PBR malzeme paleti, 3D oranlar ve üçgen bütçesi spesifikasyonu |
| `vision_rlaif_3d_critic` | `gemini-3.8-flash` | Çok açılı 3D render'ları referans görseller ve özel kurallarla kıyaslayarak koordinat/mesh düzeltme listesi üretir |
| `argon_judge_and_autopatch` | `gemini-4-argon` + `gemini-3.8-flash` | Üst düzey 3D görsel ve kod denetçisi; `.py` scriptlerini yamalar, `ast.parse` sözdizimi kontrolü yapar, Blender/özel render çalıştırır, hatada yedekten geri döner ve 5 denemede devreyi keser |

---

## Hızlı Kurulum

### Gereksinimler
- Python **3.11+** (veya [`uv`](https://docs.astral.sh/uv/))
- **Gemini Developer API anahtarı** (`GEMINI_API_KEY` veya `GOOGLE_API_KEY`) — ya da Vertex AI kimlik bilgileri

### Seçenek A: `uvx` / `uv` ile Sıfır Kurulum (Önerilen)

```bash
# Doğrudan GitHub üzerinden uvx ile çalıştırma
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp

# Veya yerel klondan çalıştırma
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv run gemini-omni-mcp --list-tools
```

### Seçenek B: `pip` ile Kurulum

```bash
pip install git+https://github.com/Remilya/gemini-omni-mcp.git
# Geliştirici / düzenlenebilir kurulum:
pip install -e .

gemini-omni-mcp --version
```

---

## AI Agent İstemcilerine Bağlama

<details open>
<summary><strong>Antigravity (Plugin Paketi veya MCP Yapılandırması)</strong></summary>

Bu repo doğrudan **Antigravity Plugin** yapısıyla (`plugin.json`, `mcp_config.json`, `assets/logo.svg`, `skills/gemini-omni/SKILL.md`) birlikte gelir.

Doğrudan `~/.gemini/antigravity/mcp_config.json` dosyanıza da ekleyebilirsiniz:

```json
{
  "mcpServers": {
    "gemini-omni": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "GEMINI_API_ANAHTARINIZ",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0",
        "GEMINI_OMNI_ENABLE_3D_TOOLS": "true"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code (CLI)</strong></summary>

```bash
claude mcp add gemini-omni \
  -e GEMINI_API_KEY="GEMINI_API_ANAHTARINIZ" \
  -e OMNI_HARD_STOP_LIMIT_USD="50.0" \
  -- uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp
```

</details>

<details>
<summary><strong>Cursor / Claude Desktop / Windsurf (`mcp.json`)</strong></summary>

```json
{
  "mcpServers": {
    "gemini-omni": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Remilya/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "GEMINI_API_ANAHTARINIZ",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Codex CLI (`~/.codex/config.toml`)</strong></summary>

```toml
[mcp_servers.gemini-omni]
command = "uvx"
args = ["--from", "git+https://github.com/Remilya/gemini-omni-mcp", "gemini-omni-mcp"]

[mcp_servers.gemini-omni.env]
GEMINI_API_KEY = "GEMINI_API_ANAHTARINIZ"
OMNI_HARD_STOP_LIMIT_USD = "50.0"
```

</details>

<details>
<summary><strong>VS Code / GitHub Copilot (`.vscode/mcp.json`)</strong></summary>

```json
{
  "servers": {
    "gemini-omni": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Remilya/gemini-omni-mcp",
        "gemini-omni-mcp"
      ],
      "env": {
        "GEMINI_API_KEY": "${input:gemini_api_key}",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "gemini_api_key",
      "description": "Google Gemini API Anahtarı",
      "password": true
    }
  ]
}
```

</details>

---

## Gerçek Zamanlı USD Harcama Takibi & Sert Bütçe Kilidi

Paralel swarm görevleri veya 1080p/4K video üretimi kontrolsüz bırakıldığında API faturasını hızla yükseltebilir. `gemini-omni-mcp`, her çağrıdaki token, görsel, video, ses ve önbellek tüketimini `<workspace>/.gemini-omni/usage_ledger.json` dosyasına kaydeder:

- **Varsayılan limit:** `$50.00 USD` (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Otomatik devre kesici:** Toplam harcama limite ulaştığında (veya sıradaki tahmini çağrı limiti aşacaksa) defter kilitlenir, bellek içi API anahtarları temizlenir ve yeni ağ çağrısı yapılmadan `HardBudgetStopError` fırlatılır.
- **Araç üzerinden anlık yönetim:**
  - Harcama ve model dağılımını gör: `gemini_cost_and_budget(action="summary")`
  - Toplu iş öncesi maliyet hesapla: `gemini_cost_and_budget(action="estimate_batch", model="gemini-3.8-flash", num_items=100, ...)`
  - Limiti yükselt veya kilidi aç: `gemini_cost_and_budget(action="set_budget_limit", new_budget_limit_usd=100.0)`
  - Sert limiti kapatmak için: `OMNI_HARD_STOP_LIMIT_USD=0` veya `--budget-limit 0`

---

## Ortam Değişkenleri Referansı

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini Developer API anahtarı (veya `GOOGLE_API_KEY`) |
| `OMNI_HARD_STOP_LIMIT_USD` | `50.0` | USD sert bütçe limiti (`0` verilirse devre dışı kalır) |
| `GEMINI_OMNI_WORKSPACE` | Çalışma dizini (`cwd`) | Göreli yollar, önbellek ve harcama defteri için kök dizin |
| `GEMINI_OMNI_LEDGER_PATH` | `<workspace>/.gemini-omni/usage_ledger.json` | Harcama defteri JSON dosyasının özel yolu |
| `GEMINI_OMNI_ENABLE_3D_TOOLS` | `true` | Opsiyonel 3 3D/CAD aracını kapatmak için `false` yapın |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Google Cloud Vertex AI kullanımı için `true` yapın |
| `GOOGLE_CLOUD_PROJECT` | — | Vertex AI için GCP Proje Kimliği |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI bölgesi |
| `BLENDER_PATH` | Otomatik algılanır | `argon_judge_and_autopatch` için Blender çalıştırılabilir dosya yolu |

---

## CLI Seçenekleri

```bash
gemini-omni-mcp --help
gemini-omni-mcp --list-tools
gemini-omni-mcp --no-3d-tools --list-tools
gemini-omni-mcp --workspace /proje/dizini --budget-limit 25.0
gemini-omni-mcp --transport streamable-http
```

---

## Geliştirme & Testler

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync --extra dev

# Çevrimdışı birim testlerini çalıştır (API anahtarı gerekmez)
uv run --extra dev pytest -v

# Kayıtlı araçları listele
uv run gemini-omni-mcp --list-tools
```

---

## Lisans

MIT Lisansı — ayrıntılar için [LICENSE](LICENSE) dosyasına bakın.
