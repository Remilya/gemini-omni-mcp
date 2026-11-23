<div align="center">

<img src="assets/logo.svg" alt="Gemini Omni MCP Logo" width="110" />

# Gemini Omni MCP

**Hepsi Bir Arada Google GenAI Çok Modlu (Multimodal), Ajan & Canlı Dokümantasyon MCP Sunucusu**

*Canlı Docs Puller · Gemini 4 (`Neon`, `Hydrogen`, isteğe bağlı `Carbon`) & Gemma 4 · YouTube/PDF Analizi · Nano Banana 2.1 · Gemini Omni 1.2 Flash Video · SRT Deşifre, TTS & Voices API · Lyria 3.5 Müzik · Modüler Swarm, Research & 3D Setleri · Gerçek Zamanlı USD Bütçe Kilidi*

[English](README.md) | **Türkçe**

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-2.x%20%26%201.x-purple.svg)](https://modelcontextprotocol.io/)
[![google-genai](https://img.shields.io/badge/google--genai-%3E%3D3.2.0-4285F4.svg)](https://github.com/googleapis/python-genai)
[![4-IDE Plugin](https://img.shields.io/badge/Plugin-Antigravity%20%7C%20Claude%20%7C%20Cursor%20%7C%20Codex-orange.svg)](#yapay-zeka-istemcilerine-ba%C4%9Flama)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## Neden Ayrı CLI Yerine MCP?

Editörün yanında harici bir CLI açmak sürekli pencere değiştirmek ve çıktıları elle projeye taşımak demektir. Google'ın resmi `google-gemini/gemini-cli` aracı kurumsal Code Assist sohbetine odaklanır ve Nano Banana görsel birleştirme, durum korumalı Omni video döngüleri veya otomatik USD bütçe koruması için tasarlanmamıştır; `google-gemini/gemini-api-cli` ise sürekli kabuk komutu çalıştırır.

**`gemini-omni-mcp`, Google'ın en güncel GenAI ekosistemini — *ve* sıfır maliyetli Canlı Dokümantasyon Çekicisini — varsayılan 6 çekirdek araçlık (`--toolsets core`) yalın bir arayüzle doğrudan AI agent'ınızın içine gömer:**

| Özellik | Ayrı CLI Penceresi | `gemini-omni-mcp` |
| --- | --- | --- |
| **Canlı Resmi Dokümanlar** | Tarayıcı sekmesi veya ek MCP kurulumu | Dahili `gemini_docs` (`gemini-api-docs-mcp.dev` + `llms.txt` yedeği + SSRF koruması, `$0.00`) |
| **Gemini 4 & Gemma 4** | Her seferde tek kabuk çağrısı | `gemini_analyze` (`gemini-4-hydrogen`, `gemini-4-neon`, isteğe bağlı `gemini-4-carbon`, `gemma-4-31b-it`) + isteğe bağlı **64 paralel işçi** |
| **Düşük Bağlam Maliyeti** | Her oturumda ağır araç kalabalığı | Varsayılan **6 çekirdek araç**; `swarm` (`+3`), `research` (`+1`) veya `3d` (`+3`) yalnızca gerektiğinde yüklenir |
| **Multimodal Çıktılar** | Çıktıları elle kopyalayıp taşıma | PNG, MP4, WAV/MP3, `.srt`/`.md`/`.json` transkriptler ve raporlar doğrudan güvenli çalışma alanına yazılır |
| **SDK & Güvenlik Kalkanları** | Sınırsız disk erişimi / SDK uyumsuzlukları | Çalışma alanı koruması, `shell=False` Blender alt süreçleri, açık `v1beta` yönlendirmesi ve otomatik `thinking_level` normalizasyonu |
| **Maliyet Güvenliği** | Otomatik USD harcama kesicisi yok | Canlı harcama defteri (`usage_ledger.json`) + `OMNI_HARD_STOP_LIMIT_USD` kilidi + canlı model listeleme |

---

## Araç Mimarisi (Varsayılan 6 Çekirdek Araç + İsteğe Bağlı Setler)

Bağlam penceresini temiz tutmak için varsayılan olarak **6 çekirdek araç** yüklenir. İhtiyaç duyulan ek modüller `--toolsets` veya `GEMINI_OMNI_TOOLSETS` ile açılır (`all` toplam **13 aracı** yükler).

### Çekirdek Araç Seti (Varsayılan — 6 Araç)

| Kategori | Araç | Model(ler) / Kaynak | Yetenekler |
| --- | --- | --- | --- |
| **Görsel Stüdyosu** | `gemini_image` | `gemini-nano-banana-2.1` | `action="generate"` (metinden görsel + 14 referansa kadar + stil çıpası + `freeform`, `character_sheet`, `architectural_sheet`, `story_scene`, `pixel_sprite` ön ayarları) veya `edit`, `inpaint`, `outpaint`, `upscale` (Pillow Lanczos yedekli) |
| **Video Stüdyosu** | `gemini_video` | `gemini-omni-1.2-flash` (`v1beta` Interactions) | Durum korumalı `generate`, `extend`, `edit` ve `seamless_loop` (`3s`–`15s`, `360p`–`4k`, iki kare arası interpolasyon, otomatik URI teslimatı) |
| **Ses & Müzik** | `gemini_audio` | `gemini-3.8-flash-tts`, `gemini-3.5-transcribe`, Voices API, `lyria-3.5` (`v1beta`) | Çok konuşmacılı `tts` (`speech_metadata`), `transcribe` (`text`/`md`/`json`/`srt` + konuşmacı ayrımı + kelime zaman damgası), `voice_design`/`remix`/`replicate`/`list`/`get`/`delete` ve `music` |
| **Analiz** | `gemini_analyze` | `gemini-4-hydrogen` (varsayılan), `gemini-4-neon`, isteğe bağlı `gemini-4-carbon`, `gemma-4-31b-it` | PDF, görsel, ses, video, kod/CSV, `files/<id>` URI'leri ve YouTube URL analizi + Google Search + Code Execution + JSON Schema |
| **Canlı Docs** | `gemini_docs` | `gemini-api-docs-mcp.dev` + `aistudio.google.com` | `action="search"` (canlı SDK/API arama + otomatik `llms.txt` yedeği) ve `action="fetch"` (`chunk_id` veya HTTPS sayfa çekme; API anahtarı gerekmez, `$0.00`) |
| **FinOps & Modeller** | `gemini_budget` | Yerel Defter + `client.models` | Canlı `summary`, `pricing_table`, `live_models` (`models.list`/`get`), `calculate_call`, `estimate_batch`, `set_budget_limit`, `reset_ledger` |

### Modüler İsteğe Bağlı Araç Setleri (`--toolsets` / `GEMINI_OMNI_TOOLSETS`)

| Set | Eklenen Araçlar | Yetenekler | Açma Komutu |
| --- | --- | --- | --- |
| **`swarm`** (`+3`) | `gemini_async_swarm`, `gemini_context_cache`, `gemini_files` | 64 paralel Gemini 4 işçisi, %95 indirimli implicit önbellek demeti / açık önbellek ve 48 saatlik Files API dosya yönetimi | `--toolsets core,swarm` |
| **`research`** (`+1`) | `gemini_deep_research` | Arka planda yönetilen araştırma ajanları (`deep-research-preview-04-2026`, `antigravity-preview-09-2026`) — `start`, `status`, `run_and_wait`, `cancel`, `delete` | `--toolsets core,research` |
| **`3d`** (`+3`, **Varsayılan Kapalı**) | `vision_extract_3d_spec`, `vision_rlaif_3d_critic`, `gemini_3d_judge_and_autopatch` | PBR `#RRGGBB` + 3D oran çıkarımı, çok açılı RLAIF denetimi ve `gemini-4-neon` denetçili + `shell=False` headless Blender yamalama (5 denemeli devre kesici) | `--toolsets core,3d` |
| **`all`** (`13` araç) | Yukarıdaki tüm setler | `core` + `swarm` + `research` + `3d` setlerini aynı anda yükler | `--toolsets all` |

---

## Canlı Docs Puller & Resmi Google Yardımcı Araçları

`gemini_docs`, resmi Google Gemini API ve SDK dokümantasyonunu **API anahtarı olmadan** (`$0.00` maliyet) canlı sorgular; uzak Docs MCP erişilemezse otomatik olarak `https://aistudio.google.com/llms.txt` dizinine geçer ve yalnızca izin verilen HTTPS alan adlarına izin verir.

İsterseniz Google'ın bağımsız geliştirici araçlarını da yanına kurabilirsiniz:

```bash
# Bağımsız resmi Gemini Docs MCP sunucusu
npx add-mcp "https://gemini-api-docs-mcp.dev"

# Resmi Gemini API agent yetenekleri (güncel SDK sözdizimi ve kurallar)
npx skills add google-gemini/gemini-skills --skill gemini-api-dev

# Antigravity'de tek komutla eklenti kurulumu
agy plugin install https://github.com/google-gemini/gemini-skills

# Terminalden doğrudan Gemini API çağıran bağımsız Go CLI
curl -fsSL https://raw.githubusercontent.com/google-gemini/gemini-api-cli/main/scripts/install.sh | bash
```

---

## Hızlı Kurulum

### Seçenek A: Kurulumsuz Çalıştırma (`uvx`, Önerilen)

```bash
uvx --from git+https://github.com/Remilya/gemini-omni-mcp gemini-omni-mcp --list-tools
```

### Seçenek B: Yerel Klondan Çalıştırma (`uv`)

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync

# Varsayılan yalın mod (6 çekirdek araç)
uv run gemini-omni-mcp --list-tools

# Swarm ve research setlerini de ekle (+4 -> 10 araç)
uv run gemini-omni-mcp --toolsets core,swarm,research --list-tools

# Tüm 13 aracı aç (3D/CAD paketi dahil)
uv run gemini-omni-mcp --toolsets all --list-tools
```

### Seçenek C: `pip` ile Kurulum

```bash
pip install git+https://github.com/Remilya/gemini-omni-mcp.git
gemini-omni-mcp --version
```

---

## Yapay Zeka İstemcilerine Bağlama

Bu repo **4 büyük agent ekosistemi** için yerel eklenti manifestlerini (`plugin.json` Antigravity, `.claude-plugin/plugin.json` Claude Code, `.cursor-plugin/plugin.json` Cursor, `.codex-plugin/plugin.json` Codex) `mcp_config.json` ve `skills/gemini-omni/SKILL.md` ile birlikte içerir.

> Varsayılan 6 çekirdek araca ek modüller yüklemek için `args` listesine `"--toolsets", "core,swarm,research"` (veya `"--toolsets", "all"`) ekleyin ya da `env` içinde `"GEMINI_OMNI_TOOLSETS": "core,swarm,research"` tanımlayın.

<details open>
<summary><strong>Antigravity (Eklenti Paketi veya <code>mcp_config.json</code>)</strong></summary>

Doğrudan `~/.gemini/antigravity/mcp_config.json` dosyasına ekleyin:

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
        "GEMINI_OMNI_WORKSPACE": "/path/to/your/workspace",
        "OMNI_HARD_STOP_LIMIT_USD": "50.0",
        "GEMINI_OMNI_TOOLSETS": "core"
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
<summary><strong>Cursor / Claude Desktop / Windsurf (<code>mcp.json</code>)</strong></summary>

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
<summary><strong>Codex CLI (<code>~/.codex/config.toml</code>)</strong></summary>

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
<summary><strong>VS Code / GitHub Copilot (<code>.vscode/mcp.json</code>)</strong></summary>

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

## Gerçek Zamanlı USD Harcama Takibi & Güvenlik Kalkanları

### FinOps Bütçe Kilidi

Tüm token, görsel, video, ses ve önbellek kullanımları `<workspace>/.gemini-omni/usage_ledger.json` dosyasına kaydedilir:

- **Varsayılan limit:** `$50.00` USD (`OMNI_HARD_STOP_LIMIT_USD=50.0`)
- **Otomatik kilit:** Limit aşıldığında defter kilitlenir, bellek içi API anahtarları temizlenir ve yeni çağrılardan önce `HardBudgetStopError` fırlatılır.
- **Araç komutları:** `gemini_budget(action="summary")`, `live_models`, `estimate_batch`, `set_budget_limit` (`0` verilirse kilidi kapatır) ve `reset_ledger`.
- **Bulut fatura önerisi:** Yerel bütçe defterine ek olarak Google Cloud / Google AI Studio fatura panelinden de aylık harcama sınırı tanımlamanız önerilir.

### Dahili Güvenlik & SDK Sertleştirmesi

- **Çalışma Alanı Koruması:** `resolve_path()` varsayılan olarak dosya okuma ve yazma işlemlerini `GEMINI_OMNI_WORKSPACE` diziniyle sınırlar (`GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=false`), açıkça izin verilmedikçe `../` ve dış yolları engeller.
- **Alt Süreç Koruması (`3d` seti):** `gemini_3d_judge_and_autopatch` Blender'ı `shell=False` argüman listesiyle çalıştırır; özel `render_command` çalıştırmak `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD=true` verilmedikçe kapalıdır.
- **`google-genai >= 3.2.0` (`3.6.1+`) Uyumluluğu:** `interactions` ve `voices` uç noktalarını açıkça `api_version="v1beta"` üzerinden yönlendirir ve `thinking_level` değerlerini modele göre normalize eder (Gemini 4'te `minimal` -> `low`; Carbon/Argon/3.x'te `xhigh` -> `high`; Gemma 4'te `ThinkingConfig` otomatik atlanır).

---

## Yapılandırma & CLI Bayrakları

[`.env.example`](.env.example) dosyasını çalışma dizininize `.env` olarak kopyalayın (veya MCP istemcinizin `env` bloğunda verin):

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `GEMINI_API_KEY` | — | Gemini Developer API anahtarı (veya `GOOGLE_API_KEY`) |
| `OMNI_HARD_STOP_LIMIT_USD` | `50.0` | Sert USD sınırı; kapatmak için `0` |
| `GEMINI_OMNI_TOOLSETS` | `core` | Virgülle ayrılmış araç setleri: `core`, `swarm`, `research`, `3d`, `all` |
| `GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE` | `false` | Çalışma alanı dışına okuma/yazma izni için `true` |
| `GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD` | `false` | `gemini_3d_judge_and_autopatch` içinde özel `render_command` izni için `true` |
| `GEMINI_OMNI_WORKSPACE` | Mevcut çalışma dizini | Göreli yollar, önbellek demetleri ve harcama defteri dizini |
| `GEMINI_OMNI_LEDGER_PATH` | `<workspace>/.gemini-omni/usage_ledger.json` | Harcama defteri JSON dosyası için özel yol |
| `GEMINI_OMNI_ENABLE_3D_TOOLS` | `false` | Eski uyumluluk bayrağı (`GEMINI_OMNI_TOOLSETS` bunun yerini alır) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `false` | Çağrıları Google Cloud Vertex AI üzerinden yönlendirir |
| `GOOGLE_CLOUD_PROJECT` | — | Vertex AI modu için GCP Proje Kimliği |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI modu için GCP Bölgesi |
| `BLENDER_PATH` | Otomatik algılanır | `gemini_3d_judge_and_autopatch` için Blender çalıştırılabilir dosya yolu |

```bash
gemini-omni-mcp --list-tools
gemini-omni-mcp --toolsets core,swarm,research --list-tools
gemini-omni-mcp --toolsets all --list-tools
gemini-omni-mcp --workspace /path/to/project --budget-limit 25.0
gemini-omni-mcp --allow-outside-workspace --transport streamable-http
```

---

## Geliştirme & Testler

```bash
git clone https://github.com/Remilya/gemini-omni-mcp.git
cd gemini-omni-mcp
uv sync --extra dev

# Çevrimdışı birim testleri (tüm ağ/API çağrıları mocklanmıştır; API anahtarı gerekmez)
uv run --extra dev pytest -v

# Araç kaydını doğrula
uv run gemini-omni-mcp --list-tools
```

---

## Lisans

MIT Lisansı — [LICENSE](LICENSE).
